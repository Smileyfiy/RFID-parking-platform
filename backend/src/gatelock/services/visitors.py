"""Registration-lane workflow: issue a temporary tag to a visitor and take it back."""

from datetime import datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gatelock.config import get_settings
from gatelock.hub import Message
from gatelock.models import Role, Severity, Tag, TagKind, Vehicle, Visitor
from gatelock.schemas import VisitorCreate, VisitorOut
from gatelock.security import decrypt_pii, encrypt_pii, mask_id
from gatelock.services.access import normalise_uid
from gatelock.services.alerts import raise_alert
from gatelock.services.audit import audit
from gatelock.services.parking import release_vehicle


class VisitorError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def normalise_plate(plate: str) -> str:
    return "".join(plate.split()).upper()


def end_of_local_day(now: datetime) -> datetime:
    tz = get_settings().tz
    return datetime.combine(now.astimezone(tz).date() + timedelta(days=1), time.min, tz)


async def register_visitor(
    session: AsyncSession, out: list[Message], data: VisitorCreate, user_id: int, now: datetime
) -> Visitor:
    uid = normalise_uid(data.tag_uid)
    tag = await session.scalar(select(Tag).where(Tag.uid == uid).with_for_update())
    if tag is None:
        raise VisitorError(404, f"Tag {uid} is not registered.")
    if tag.kind != TagKind.TEMPORARY:
        raise VisitorError(409, f"Tag {uid} is a permanent tag, not a visitor tag.")
    if tag.active:
        raise VisitorError(409, f"Tag {uid} is already issued.")

    plate = normalise_plate(data.plate)
    vehicle = await session.scalar(
        select(Vehicle).options(selectinload(Vehicle.tags)).where(Vehicle.plate == plate)
    )
    if vehicle is not None:
        if vehicle.role != Role.VISITOR:
            raise VisitorError(409, f"{plate} is a registered {vehicle.role} vehicle.")
        if vehicle.blacklisted:
            await raise_alert(
                session,
                out,
                kind="blacklisted",
                severity=Severity.CRITICAL,
                message=f"Blacklisted vehicle {plate} tried to register at the registration lane.",
                vehicle_id=vehicle.id,
                now=now,
            )
            await session.commit()
            raise VisitorError(403, f"{plate} is blacklisted. {vehicle.blacklist_reason}")
        if any(t.active for t in vehicle.tags):
            raise VisitorError(409, f"{plate} already holds an active visitor tag.")
    else:
        vehicle = Vehicle(plate=plate, role=Role.VISITOR, created_at=now)
        session.add(vehicle)
        await session.flush()

    tag.vehicle_id = vehicle.id
    tag.active = True
    tag.valid_from = now
    tag.valid_until = end_of_local_day(now)
    tag.last_exit_at = None

    visitor = Visitor(
        vehicle_id=vehicle.id,
        tag_uid=uid,
        full_name_enc=encrypt_pii(data.full_name.strip()),
        national_id_enc=encrypt_pii(data.national_id.strip()),
        purpose=data.purpose,
        checked_in_at=now,
        expected_departure=data.expected_departure,
        registered_by=user_id,
    )
    session.add(visitor)
    await session.flush()
    audit(session, user_id, "visitor.register", now, visitor_id=visitor.id, tag=uid, plate=plate)
    visitor.vehicle = vehicle
    return visitor


async def return_tag(
    session: AsyncSession, out: list[Message], uid: str, user_id: int, now: datetime
) -> Visitor | None:
    """Deactivate a returned visitor tag and close the visit. Returns the visit, if any."""
    uid = normalise_uid(uid)
    tag = await session.scalar(
        select(Tag).options(selectinload(Tag.vehicle)).where(Tag.uid == uid).with_for_update()
    )
    if tag is None or tag.kind != TagKind.TEMPORARY or not tag.active:
        raise VisitorError(409, f"Tag {uid} is not an issued visitor tag.")
    visitor = await session.scalar(
        select(Visitor)
        .options(selectinload(Visitor.vehicle))
        .where(Visitor.tag_uid == uid, Visitor.returned_at.is_(None))
        .order_by(Visitor.checked_in_at.desc())
        .limit(1)
    )
    if tag.vehicle is not None and tag.vehicle.inside:
        # Handed back before the exit read: treat the return as the exit.
        tag.vehicle.inside = False
        await release_vehicle(session, out, tag.vehicle.id, now)
    tag.active = False
    tag.vehicle_id = None
    tag.valid_from = tag.valid_until = tag.last_exit_at = None
    if visitor is not None:
        visitor.returned_at = now
    audit(session, user_id, "visitor.return", now, visitor_id=visitor and visitor.id, tag=uid)
    return visitor


def visitor_out(v: Visitor) -> VisitorOut:
    return VisitorOut(
        id=v.id,
        full_name=decrypt_pii(v.full_name_enc),
        national_id_masked=mask_id(decrypt_pii(v.national_id_enc)),
        plate=v.vehicle.plate,
        purpose=v.purpose,
        tag_uid=v.tag_uid,
        checked_in_at=v.checked_in_at,
        expected_departure=v.expected_departure,
        returned_at=v.returned_at,
        inside=v.vehicle.inside,
    )


async def purge_expired_visitors(session: AsyncSession, now: datetime) -> int:
    cutoff = now - timedelta(days=get_settings().visitor_retention_days)
    result = await session.execute(
        delete(Visitor).where(Visitor.returned_at.is_not(None), Visitor.returned_at < cutoff)
    )
    return result.rowcount or 0
