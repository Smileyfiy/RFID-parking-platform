import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import Integer, func, select

from gatelock.api.deps import AdminUser, Bridge, CurrentUser, Session, commit_and_publish
from gatelock.config import get_settings
from gatelock.hub import Message
from gatelock.models import (
    AccessEvent,
    Alert,
    AuditLog,
    Direction,
    Gate,
    RolePolicy,
    Vehicle,
    Zone,
    utcnow,
)
from gatelock.schemas import AccessEventOut, AlertOut, GateOut, PolicyOut, PolicyUpdate, ZoneOut
from gatelock.services.audit import audit
from gatelock.services.parking import set_lot_enabled, zone_summaries

router = APIRouter(tags=["monitoring"])


@router.get("/parking/zones", response_model=list[ZoneOut])
async def zones(session: Session, _: CurrentUser):
    return await zone_summaries(session)


@router.patch("/parking/lots/{lot_id}")
async def toggle_lot(lot_id: str, enabled: bool, session: Session, admin: AdminUser):
    out: list[Message] = []
    if await set_lot_enabled(session, out, lot_id, enabled, utcnow()) is None:
        raise HTTPException(404, "Lot not found")
    audit(session, admin.id, "lot.enabled", utcnow(), lot=lot_id, enabled=enabled)
    await commit_and_publish(session, out)
    return out[0][1]


@router.get("/gates", response_model=list[GateOut])
async def gates(session: Session, _: CurrentUser):
    return (await session.scalars(select(Gate).order_by(Gate.id))).all()


@router.post("/gates/{gate_id}/open", status_code=202)
async def open_gate(gate_id: str, session: Session, user: CurrentUser, mqtt: Bridge):
    """Manual override: the guard opens the barrier from the dashboard."""
    if await session.get(Gate, gate_id) is None:
        raise HTTPException(404, "Gate not found")
    if not await mqtt.publish(f"gate/{gate_id}/command", {"action": "open", "by": user.username}):
        raise HTTPException(503, "Message broker unavailable")
    audit(session, user.id, "gate.manual_open", utcnow(), gate=gate_id)
    await session.commit()
    return {"status": "sent"}


def _event_query(gate: str | None, granted: bool | None, plate: str, since, until):
    stmt = select(AccessEvent).order_by(AccessEvent.ts.desc())
    if gate:
        stmt = stmt.where(AccessEvent.gate_id == gate)
    if granted is not None:
        stmt = stmt.where(AccessEvent.granted.is_(granted))
    if plate:
        stmt = stmt.where(AccessEvent.plate.ilike(f"%{plate}%"))
    if since:
        stmt = stmt.where(AccessEvent.ts >= since)
    if until:
        stmt = stmt.where(AccessEvent.ts < until)
    return stmt


@router.get("/events", response_model=list[AccessEventOut])
async def events(
    session: Session,
    _: CurrentUser,
    gate: str | None = None,
    granted: bool | None = None,
    plate: str = "",
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
):
    stmt = _event_query(gate, granted, plate, since, until).limit(min(limit, 1000)).offset(offset)
    return (await session.scalars(stmt)).all()


@router.get("/events.csv")
async def events_csv(
    session: Session,
    _: CurrentUser,
    gate: str | None = None,
    granted: bool | None = None,
    plate: str = "",
    since: datetime | None = None,
    until: datetime | None = None,
):
    tz = get_settings().tz
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["time", "gate", "tag", "plate", "role", "direction", "granted", "reason", "lot"])
    for e in await session.scalars(_event_query(gate, granted, plate, since, until).limit(50000)):
        w.writerow(
            [
                e.ts.astimezone(tz).isoformat(timespec="seconds"),
                e.gate_id,
                e.tag_uid,
                e.plate or "",
                e.role or "",
                e.direction or "",
                e.granted,
                e.reason,
                e.lot_id or "",
            ]
        )
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=access-events.csv"},
    )


@router.get("/alerts", response_model=list[AlertOut])
async def alerts(session: Session, _: CurrentUser, open: bool | None = None, limit: int = 100):
    stmt = select(Alert).order_by(Alert.ts.desc()).limit(min(limit, 1000))
    if open is not None:
        cond = Alert.acknowledged_at.is_(None)
        stmt = stmt.where(cond if open else ~cond)
    return (await session.scalars(stmt)).all()


@router.post("/alerts/{alert_id}/ack", response_model=AlertOut)
async def ack_alert(alert_id: int, session: Session, user: CurrentUser):
    alert = await session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "Alert not found")
    if alert.acknowledged_at is None:
        alert.acknowledged_at = utcnow()
        alert.acknowledged_by = user.id
        audit(session, user.id, "alert.ack", utcnow(), alert_id=alert.id)
    data = AlertOut.model_validate(alert)
    await commit_and_publish(session, [("alert", data.model_dump(mode="json"))])
    return data


@router.get("/policies", response_model=list[PolicyOut])
async def policies(session: Session, _: CurrentUser):
    return (await session.scalars(select(RolePolicy).order_by(RolePolicy.role))).all()


@router.patch("/policies/{role}", response_model=PolicyOut)
async def update_policy(role: str, data: PolicyUpdate, session: Session, admin: AdminUser):
    policy = await session.get(RolePolicy, role)
    if policy is None:
        raise HTTPException(404, "Policy not found")
    changes = data.model_dump(exclude_unset=True)
    if "zone_id" in changes and await session.get(Zone, changes["zone_id"]) is None:
        raise HTTPException(400, "Unknown zone")
    for field, value in changes.items():
        setattr(policy, field, value)
    audit(
        session,
        admin.id,
        "policy.update",
        utcnow(),
        role=role,
        **{k: str(v) for k, v in changes.items()},
    )
    await session.commit()
    return policy


@router.get("/reports/summary")
async def summary(
    session: Session, _: CurrentUser, since: datetime | None = None, until: datetime | None = None
):
    until = until or utcnow()
    since = since or until - timedelta(days=7)
    tz = get_settings().timezone
    in_range = (AccessEvent.ts >= since, AccessEvent.ts < until)
    entry = (AccessEvent.granted.is_(True), AccessEvent.direction == Direction.IN)

    async def grouped(col, *where):
        rows = await session.execute(
            select(col, func.count()).where(*in_range, *where).group_by(col).order_by(col)
        )
        return {str(k): n for k, n in rows.all()}

    local_ts = func.timezone(tz, AccessEvent.ts)
    hour = func.extract("hour", local_ts).cast(Integer)
    day = func.date(local_ts)
    alerts_by_kind = await session.execute(
        select(Alert.kind, func.count())
        .where(Alert.ts >= since, Alert.ts < until)
        .group_by(Alert.kind)
    )
    return {
        "since": since,
        "until": until,
        "entries": sum((await grouped(AccessEvent.role, *entry)).values()),
        "exits": sum(
            (
                await grouped(
                    AccessEvent.role,
                    AccessEvent.direction == Direction.OUT,
                    AccessEvent.granted.is_(True),
                )
            ).values()
        ),
        "denied_by_reason": await grouped(AccessEvent.reason, AccessEvent.granted.is_(False)),
        "entries_by_role": await grouped(AccessEvent.role, *entry),
        "entries_by_hour": await grouped(hour, *entry),
        "entries_by_day": await grouped(day, *entry),
        "alerts_by_kind": dict(alerts_by_kind.all()),
        "inside_now": await session.scalar(
            select(func.count()).select_from(Vehicle).where(Vehicle.inside.is_(True))
        ),
    }


@router.get("/audit")
async def audit_log(session: Session, _: AdminUser, limit: int = 200):
    rows = await session.scalars(select(AuditLog).order_by(AuditLog.ts.desc()).limit(limit))
    return [
        {"id": r.id, "ts": r.ts, "user_id": r.user_id, "action": r.action, "detail": r.detail}
        for r in rows
    ]
