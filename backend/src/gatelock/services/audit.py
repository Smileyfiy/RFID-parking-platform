from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from gatelock.models import AuditLog


def audit(
    session: AsyncSession, user_id: int | None, action: str, now: datetime, /, **detail
) -> None:
    """Record an action. Positional-only, so detail may itself contain a user_id key."""
    session.add(AuditLog(ts=now, user_id=user_id, action=action, detail=detail))
