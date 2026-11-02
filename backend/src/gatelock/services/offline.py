"""Reconcile decisions a gate made from its cached allow-list while it was offline."""

from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gatelock.hub import Message
from gatelock.models import AccessEvent, Direction, Gate, Severity, Tag, TagKind
from gatelock.schemas import AccessEventOut
from gatelock.services.access import normalise_uid
from gatelock.services.alerts import raise_alert
from gatelock.services.parking import reconcile_unplaced, release_vehicle
from gatelock.services.securetag import authenticate


class OfflineEvent(BaseModel):
    read_id: str
    uid: str
    ts: int  # unix seconds, from the gate's clock
    granted: bool
    reason: str
    direction: Direction | None = None
    sun: dict | None = None  # the secure tag's signed message, checked after the fact


async def replay(
    session: AsyncSession, out: list[Message], gate_id: str, raw: list[dict], now: datetime
) -> list[str]:
    """Log buffered offline events and apply their effects. Returns read_ids to acknowledge.

    Events already stored (a retried replay, or a read the server decided after the gate
    gave up waiting) are acknowledged without being applied again.
    """
    gate = await session.get(Gate, gate_id)
    if gate is None:
        return []
    events: list[OfflineEvent] = []
    acked: list[str] = []
    for item in raw:
        try:
            events.append(OfflineEvent.model_validate(item))
        except ValidationError:
            if isinstance(item, dict) and "read_id" in item:
                acked.append(str(item["read_id"]))  # malformed: drop it from the gate's buffer
    for e in sorted(events, key=lambda e: e.ts):
        acked.append(e.read_id)
        if await session.scalar(select(AccessEvent.id).where(AccessEvent.read_id == e.read_id)):
            continue
        await _apply(session, out, gate, e, now)
    await session.flush()
    await reconcile_unplaced(session, out, now)
    return acked


async def _apply(
    session: AsyncSession, out: list[Message], gate: Gate, e: OfflineEvent, now: datetime
) -> None:
    uid = normalise_uid(e.uid)
    ts = min(datetime.fromtimestamp(e.ts, UTC), now)
    tag = await session.scalar(
        select(Tag).options(selectinload(Tag.vehicle)).where(Tag.uid == uid).with_for_update()
    )
    vehicle = tag.vehicle if tag else None

    if e.granted:
        await authenticate(session, out, tag, uid, e.sun, gate.name, gate.id, now, offline=True)
        if vehicle is None or not tag.active or vehicle.blacklisted:
            why = "is blacklisted" if vehicle and vehicle.blacklisted else "was revoked or returned"
            await raise_alert(
                session,
                out,
                kind="offline_violation",
                severity=Severity.CRITICAL,
                message=(
                    f"{gate.name} admitted tag {uid}"
                    f"{f' ({vehicle.plate})' if vehicle else ''} while offline, but it {why}."
                ),
                gate_id=gate.id,
                tag_uid=uid,
                vehicle_id=vehicle.id if vehicle else None,
                now=now,
            )
        if vehicle is not None:
            if e.direction == Direction.IN:
                vehicle.inside = True
            elif e.direction == Direction.OUT:
                vehicle.inside = False
                await release_vehicle(session, out, vehicle.id, now)
                if tag.kind == TagKind.TEMPORARY:
                    tag.last_exit_at = ts

    if tag is not None and (tag.last_seen_at is None or ts > tag.last_seen_at):
        tag.last_gate_id = gate.id
        tag.last_seen_at = ts
    event = AccessEvent(
        ts=ts,
        gate_id=gate.id,
        tag_uid=uid,
        vehicle_id=vehicle.id if vehicle else None,
        plate=vehicle.plate if vehicle else None,
        role=vehicle.role if vehicle else None,
        direction=e.direction,
        granted=e.granted,
        reason=e.reason,
        read_id=e.read_id,
        offline=True,
    )
    session.add(event)
    await session.flush()
    out.append(("access_event", AccessEventOut.model_validate(event).model_dump(mode="json")))
