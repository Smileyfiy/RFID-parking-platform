from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from gatelock.hub import Message
from gatelock.models import Alert, Severity
from gatelock.schemas import AlertOut


async def raise_alert(
    session: AsyncSession,
    out: list[Message],
    *,
    kind: str,
    severity: Severity,
    message: str,
    now: datetime,
    dedupe_key: str | None = None,
    gate_id: str | None = None,
    tag_uid: str | None = None,
    vehicle_id: int | None = None,
    lot_id: str | None = None,
) -> Alert | None:
    """Record an alert unless an unacknowledged one with the same dedupe key is open."""
    if dedupe_key:
        open_alert = await session.scalar(
            select(Alert.id)
            .where(Alert.dedupe_key == dedupe_key, Alert.acknowledged_at.is_(None))
            .limit(1)
        )
        if open_alert is not None:
            return None
    alert = Alert(
        ts=now,
        kind=kind,
        severity=severity,
        message=message,
        dedupe_key=dedupe_key,
        gate_id=gate_id,
        tag_uid=tag_uid,
        vehicle_id=vehicle_id,
        lot_id=lot_id,
    )
    session.add(alert)
    await session.flush()
    out.append(("alert", AlertOut.model_validate(alert).model_dump(mode="json")))
    return alert


async def resolve_alerts(
    session: AsyncSession, out: list[Message], dedupe_key: str, now: datetime
) -> None:
    """Close open alerts whose condition has cleared (acknowledged by the system, no user)."""
    alerts = await session.scalars(
        update(Alert)
        .where(Alert.dedupe_key == dedupe_key, Alert.acknowledged_at.is_(None))
        .values(acknowledged_at=now)
        .returning(Alert),
        execution_options={"synchronize_session": False},
    )
    for alert in alerts:
        out.append(("alert", AlertOut.model_validate(alert).model_dump(mode="json")))
