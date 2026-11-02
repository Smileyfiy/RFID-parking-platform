"""Allow-list snapshot that gates cache so they can keep deciding while offline.

Published retained on "{prefix}/sync". Blacklisted vehicles and inactive tags are left
out, and tag UIDs are salted hashes so the snapshot does not hand out clonable UIDs.
"""

import hashlib
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gatelock.config import get_settings
from gatelock.models import Lot, RolePolicy, Tag, Vehicle


def tag_hash(uid: str, salt: str | None = None) -> str:
    salt = get_settings().sync_salt if salt is None else salt
    return hashlib.sha256(f"{salt}:{uid}".encode()).hexdigest()[:16]


def _epoch(dt: datetime | None) -> int | None:
    return int(dt.timestamp()) if dt else None


async def build_snapshot(session: AsyncSession, now: datetime) -> dict:
    """Everything a gate needs to decide alone. Times in the windows are local wall-clock."""
    policies = (await session.scalars(select(RolePolicy))).all()
    free_rows = await session.execute(
        select(Lot.zone_id, func.count())
        .where(
            Lot.enabled.is_(True),
            Lot.sensor_online.is_(True),
            Lot.occupied.is_(False),
            Lot.vehicle_id.is_(None),
        )
        .group_by(Lot.zone_id)
    )
    free = {p.zone_id: 0 for p in policies} | dict(free_rows.all())
    tags = await session.execute(
        select(Tag.uid, Tag.valid_from, Tag.valid_until, Vehicle.role, Vehicle.inside)
        .join(Vehicle, Tag.vehicle_id == Vehicle.id)
        .where(Tag.active.is_(True), Vehicle.blacklisted.is_(False))
        .order_by(Tag.uid)
    )
    offset = now.astimezone(get_settings().tz).utcoffset()
    return {
        "utc_offset_min": int(offset.total_seconds() // 60) if offset else 0,
        "windows": {
            p.role.value: [p.start_time.strftime("%H:%M"), p.end_time.strftime("%H:%M")]
            for p in policies
        },
        "role_zone": {p.role.value: p.zone_id for p in policies},
        "free": free,
        "tags": [
            {
                "h": tag_hash(uid),
                "r": role.value,
                "in": inside,
                "from": _epoch(valid_from),
                "until": _epoch(valid_until),
            }
            for uid, valid_from, valid_until, role, inside in tags.all()
        ],
    }
