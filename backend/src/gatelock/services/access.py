"""Access-control decision engine: one RFID read at a gate in, one decision out.

A vehicle's presence toggles: if it is inside, the next accepted read is an exit.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gatelock.config import get_settings
from gatelock.hub import Message
from gatelock.models import (
    AccessEvent,
    Direction,
    Gate,
    RolePolicy,
    Severity,
    Tag,
    TagKind,
)
from gatelock.schemas import AccessEventOut, lot_out
from gatelock.services.alerts import raise_alert
from gatelock.services.parking import allocate_lot, release_vehicle
from gatelock.services.policy import in_window

# Decision reasons, stored on each access event.
GRANTED_IN = "granted"
GRANTED_OUT = "exit"
UNKNOWN_TAG = "unknown_tag"
TAG_INACTIVE = "tag_inactive"
BLACKLISTED = "blacklisted"
NOT_YET_VALID = "pass_not_yet_valid"
EXPIRED = "pass_expired"
OUTSIDE_HOURS = "outside_hours"
IMPOSSIBLE_TRAVEL = "impossible_travel"
ZONE_FULL = "zone_full"

# Two short lines for the gate's OLED.
DISPLAY = {
    UNKNOWN_TAG: "Unknown tag\nUse reg. lane",
    TAG_INACTIVE: "Tag inactive\nSee guard",
    BLACKLISTED: "Access denied\nSee guard",
    NOT_YET_VALID: "Pass not valid\nyet",
    EXPIRED: "Pass expired\nSee guard",
    OUTSIDE_HOURS: "Outside access\nhours",
    IMPOSSIBLE_TRAVEL: "Access denied\nSee guard",
    GRANTED_OUT: "Goodbye",
}


@dataclass
class Decision:
    gate_id: str
    uid: str
    granted: bool
    reason: str
    direction: Direction | None = None
    lot_id: str | None = None
    zone_id: str | None = None
    read_id: str | None = None

    @property
    def display(self) -> str:
        if self.reason == GRANTED_IN:
            return f"Welcome\nGo to lot {self.lot_id}"
        if self.reason == ZONE_FULL:
            zone = f"Zone {self.zone_id}" if self.zone_id else "Zone"
            return f"{zone} full\nSee guard"
        return DISPLAY[self.reason]

    def to_gate(self) -> dict:
        return {
            "read_id": self.read_id,
            "uid": self.uid,
            "granted": self.granted,
            "direction": self.direction,
            "lot": self.lot_id,
            "reason": self.reason,
            "display": self.display,
        }


class Debouncer:
    """Drops repeat reads of the same tag at the same gate (raw RFID duplicates).

    Without this, a tag held in the field would toggle in/out on every read.
    """

    def __init__(self, seconds: int) -> None:
        self.window = timedelta(seconds=seconds)
        self._last: dict[tuple[str, str], datetime] = {}

    def accept(self, gate_id: str, uid: str, now: datetime) -> bool:
        key = (gate_id, uid)
        last = self._last.get(key)
        self._last[key] = now
        return last is None or now - last >= self.window


def normalise_uid(uid: str) -> str:
    return uid.replace(":", "").replace(" ", "").upper()


async def process_read(
    session: AsyncSession,
    out: list[Message],
    gate_id: str,
    uid: str,
    now: datetime,
    read_id: str | None = None,
) -> Decision | None:
    """Decide on one tag read, log it and raise any alerts. Returns None for unknown gates.

    A read_id already decided (a redelivered message) gets the stored decision back.
    """
    uid = normalise_uid(uid)
    gate = await session.get(Gate, gate_id)
    if gate is None:
        return None
    if read_id is not None:
        prev = await session.scalar(select(AccessEvent).where(AccessEvent.read_id == read_id))
        if prev is not None:
            return Decision(
                prev.gate_id,
                prev.tag_uid,
                prev.granted,
                prev.reason,
                prev.direction,
                prev.lot_id,
                read_id=read_id,
            )
    gate.online = True
    gate.last_seen_at = now

    tag = await session.scalar(
        select(Tag).options(selectinload(Tag.vehicle)).where(Tag.uid == uid).with_for_update()
    )
    decision = await _decide(session, out, gate, tag, uid, now)
    decision.read_id = read_id

    vehicle = tag.vehicle if tag else None
    if tag is not None:
        tag.last_gate_id = gate.id
        tag.last_seen_at = now
    event = AccessEvent(
        ts=now,
        gate_id=gate.id,
        tag_uid=uid,
        vehicle_id=vehicle.id if vehicle else None,
        plate=vehicle.plate if vehicle else None,
        role=vehicle.role if vehicle else None,
        direction=decision.direction,
        granted=decision.granted,
        reason=decision.reason,
        lot_id=decision.lot_id,
        read_id=read_id,
    )
    session.add(event)
    await session.flush()
    out.append(("access_event", AccessEventOut.model_validate(event).model_dump(mode="json")))

    if not decision.granted:
        await _check_denied_burst(session, out, gate.id, uid, now)
    return decision


async def _decide(
    session: AsyncSession,
    out: list[Message],
    gate: Gate,
    tag: Tag | None,
    uid: str,
    now: datetime,
) -> Decision:
    s = get_settings()

    def deny(reason: str, direction: Direction | None = None, **kw) -> Decision:
        return Decision(gate.id, uid, False, reason, direction, **kw)

    if tag is None:
        return deny(UNKNOWN_TAG)
    vehicle = tag.vehicle
    if not tag.active or vehicle is None:
        return deny(TAG_INACTIVE)

    direction = Direction.OUT if vehicle.inside else Direction.IN

    if vehicle.blacklisted:
        await raise_alert(
            session,
            out,
            kind="blacklisted",
            severity=Severity.CRITICAL,
            message=f"Blacklisted vehicle {vehicle.plate} at {gate.name}. {vehicle.blacklist_reason}",
            gate_id=gate.id,
            tag_uid=uid,
            vehicle_id=vehicle.id,
            now=now,
        )
        return deny(BLACKLISTED, direction)

    # A tag seen at another site too recently to have travelled: likely a clone.
    if tag.last_seen_at is not None and tag.last_gate_id and tag.last_gate_id != gate.id:
        last_gate = await session.get(Gate, tag.last_gate_id)
        gap = now - tag.last_seen_at
        if (
            last_gate is not None
            and last_gate.location != gate.location
            and gap < timedelta(seconds=s.impossible_travel_seconds)
        ):
            await raise_alert(
                session,
                out,
                kind="impossible_travel",
                severity=Severity.CRITICAL,
                message=(
                    f"Tag {uid} ({vehicle.plate}) read at {gate.name} {int(gap.total_seconds())}s"
                    f" after {last_gate.name}. Possible cloned tag."
                ),
                gate_id=gate.id,
                tag_uid=uid,
                vehicle_id=vehicle.id,
                now=now,
            )
            return deny(IMPOSSIBLE_TRAVEL, direction)

    if direction == Direction.OUT:
        vehicle.inside = False
        await release_vehicle(session, out, vehicle.id, now)
        if tag.kind == TagKind.TEMPORARY:
            tag.last_exit_at = now
        return Decision(gate.id, uid, True, GRANTED_OUT, Direction.OUT)

    if tag.valid_from and now < tag.valid_from:
        return deny(NOT_YET_VALID, direction)
    if tag.valid_until and now >= tag.valid_until:
        return deny(EXPIRED, direction)

    policy = await session.get(RolePolicy, vehicle.role)
    if policy is None:
        return deny(TAG_INACTIVE, direction)
    local = now.astimezone(s.tz).time()
    if not in_window(local, policy.start_time, policy.end_time):
        return deny(OUTSIDE_HOURS, direction)

    lot = await allocate_lot(session, policy.zone_id, vehicle.id, now)
    if lot is None:
        await raise_alert(
            session,
            out,
            kind="zone_full",
            severity=Severity.WARNING,
            message=f"Zone {policy.zone_id} is full; {vehicle.plate} was refused at {gate.name}.",
            dedupe_key=f"zone_full:{policy.zone_id}",
            gate_id=gate.id,
            tag_uid=uid,
            vehicle_id=vehicle.id,
            now=now,
        )
        return deny(ZONE_FULL, direction, zone_id=policy.zone_id)

    vehicle.inside = True
    await session.refresh(lot, ["vehicle"])
    out.append(("lot", lot_out(lot)))
    return Decision(gate.id, uid, True, GRANTED_IN, Direction.IN, lot.id, policy.zone_id)


async def _check_denied_burst(
    session: AsyncSession, out: list[Message], gate_id: str, uid: str, now: datetime
) -> None:
    s = get_settings()
    since = now - timedelta(seconds=s.denied_burst_window_seconds)
    count = await session.scalar(
        select(func.count())
        .select_from(AccessEvent)
        .where(
            AccessEvent.gate_id == gate_id,
            AccessEvent.tag_uid == uid,
            AccessEvent.granted.is_(False),
            AccessEvent.ts >= since,
        )
    )
    if count >= s.denied_burst_count:
        await raise_alert(
            session,
            out,
            kind="denied_burst",
            severity=Severity.WARNING,
            message=f"Tag {uid} was denied {count} times at gate {gate_id} within a minute.",
            dedupe_key=f"denied_burst:{gate_id}:{uid}",
            gate_id=gate_id,
            tag_uid=uid,
            now=now,
        )
