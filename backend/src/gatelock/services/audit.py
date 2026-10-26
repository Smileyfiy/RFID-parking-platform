from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from gatelock.models import AuditLog


def audit(session: AsyncSession, user_id: int | None, action: str, now: datetime, **detail) -> None:
    session.add(AuditLog(ts=now, user_id=user_id, action=action, detail=detail))
