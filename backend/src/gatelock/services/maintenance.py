"""Time-driven event-processing rules, run periodically by the backend."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gatelock.config import get_settings
from gatelock.hub import Message
from gatelock.models import Severity, Tag, TagKind, Vehicle, Visitor
from gatelock.services.alerts import raise_alert
from gatelock.services.parking import expire_reservations
from gatelock.services.visitors import purge_expired_visitors


async def run_maintenance(session: AsyncSession, out: list[Message], now: datetime) -> None:
    s = get_settings()
    await expire_reservations(session, out, now)

    # Temporary tag read at the exit but not handed back.
    cutoff = now - timedelta(minutes=s.temp_tag_return_minutes)
    tags = await session.scalars(
        select(Tag)
        .options(selectinload(Tag.vehicle))
        .join(Vehicle)
        .where(
            Tag.kind == TagKind.TEMPORARY,
            Tag.active.is_(True),
            Tag.last_exit_at.is_not(None),
            Tag.last_exit_at < cutoff,
            Vehicle.inside.is_(False),
        )
    )
    for tag in tags:
        await raise_alert(
            session,
            out,
            kind="temp_tag_not_returned",
            severity=Severity.WARNING,
            message=f"Visitor {tag.vehicle.plate} left without returning tag {tag.uid}.",
            dedupe_key=f"temp_not_returned:{tag.uid}",
            tag_uid=tag.uid,
            vehicle_id=tag.vehicle_id,
            now=now,
        )

    # Visitor still on site well after their expected departure.
    overdue = now - timedelta(minutes=s.visitor_overstay_grace_minutes)
    visitors = await session.scalars(
        select(Visitor)
        .options(selectinload(Visitor.vehicle))
        .join(Vehicle)
        .where(
            Visitor.returned_at.is_(None),
            Visitor.expected_departure < overdue,
            Vehicle.inside.is_(True),
        )
    )
    for v in visitors:
        await raise_alert(
            session,
            out,
            kind="visitor_overstay",
            severity=Severity.WARNING,
            message=f"Visitor {v.vehicle.plate} is still on site past their expected departure.",
            dedupe_key=f"overstay:{v.id}",
            tag_uid=v.tag_uid,
            vehicle_id=v.vehicle_id,
            now=now,
        )

    await purge_expired_visitors(session, now)
