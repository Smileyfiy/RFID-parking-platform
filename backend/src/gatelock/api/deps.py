from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from gatelock.db import get_session
from gatelock.hub import Message, hub
from gatelock.models import User, UserRole
from gatelock.mqtt_bridge import MqttBridge
from gatelock.security import decode_token

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

Session = Annotated[AsyncSession, Depends(get_session)]


async def user_from_token(session: AsyncSession, token: str) -> User | None:
    try:
        claims = decode_token(token)
    except jwt.PyJWTError:
        return None
    user = await session.get(User, int(claims["sub"]))
    if user is None or not user.active or claims.get("ver", 0) != user.token_version:
        return None
    return user


async def current_user(session: Session, token: Annotated[str, Depends(oauth2)]) -> User:
    user = await user_from_token(session, token)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
AdminUser = Annotated[User, Depends(admin_user)]


async def commit_and_publish(session: AsyncSession, out: list[Message]) -> None:
    await session.commit()
    hub.publish(out)


def _bridge(request: Request):
    return request.app.state.bridge


Bridge = Annotated[MqttBridge, Depends(_bridge)]
