from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import exists, or_, select

from gatelock.api.deps import AdminUser, CurrentUser, Session
from gatelock.models import Alert, AuditLog, User, UserRole, Visitor, utcnow
from gatelock.schemas import (
    PasswordChange,
    PasswordReset,
    Token,
    UserCreate,
    UserOut,
    UserUpdate,
)
from gatelock.security import create_token, hash_password, verify_password
from gatelock.services.audit import audit

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=Token)
async def login(session: Session, form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = await session.scalar(select(User).where(User.username == form.username))
    if user is None or not user.active or not verify_password(form.password, user.password_hash):
        audit(session, None, "auth.failed", utcnow(), username=form.username)
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password")
    audit(session, user.id, "auth.login", utcnow())
    await session.commit()
    return _token(user)


def _token(user: User) -> Token:
    return Token(
        access_token=create_token(user.id, user.role, user.token_version),
        user=UserOut.model_validate(user),
    )


@router.get("/auth/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.post("/auth/password", response_model=Token)
async def change_own_password(data: PasswordChange, session: Session, user: CurrentUser):
    """Change your own password. Other sessions are signed out; this one gets a new token."""
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    _set_password(user, data.new_password)
    audit(session, user.id, "auth.password_change", utcnow())
    await session.commit()
    return _token(user)


def _set_password(user: User, password: str) -> None:
    user.password_hash = hash_password(password)
    user.token_version += 1


@router.get("/users", response_model=list[UserOut])
async def list_users(session: Session, _: AdminUser):
    return (await session.scalars(select(User).order_by(User.username))).all()


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(data: UserCreate, session: Session, admin: AdminUser):
    if await session.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(409, "Username already taken")
    user = User(
        username=data.username,
        full_name=data.full_name,
        role=data.role,
        password_hash=hash_password(data.password),
    )
    session.add(user)
    await session.flush()
    audit(session, admin.id, "user.create", utcnow(), user_id=user.id, role=data.role)
    await session.commit()
    return user


async def _user(session, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, data: UserUpdate, session: Session, admin: AdminUser):
    user = await _user(session, user_id)
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    # Admins cannot remove their own role, so at least one active admin always remains.
    if user.id == admin.id and changes.get("role", UserRole.ADMIN) != UserRole.ADMIN:
        raise HTTPException(400, "You cannot remove your own administrator role")
    for key, value in changes.items():
        setattr(user, key, value)
    audit(session, admin.id, "user.update", utcnow(), user_id=user.id, **changes)
    await session.commit()
    return user


@router.post("/users/{user_id}/password", status_code=204)
async def reset_password(user_id: int, data: PasswordReset, session: Session, admin: AdminUser):
    """Set a new password for another user and sign them out everywhere."""
    user = await _user(session, user_id)
    if user.id == admin.id:
        raise HTTPException(400, "Use change password for your own account")
    _set_password(user, data.password)
    audit(session, admin.id, "user.password_reset", utcnow(), user_id=user.id)
    await session.commit()


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int, session: Session, admin: AdminUser):
    """Delete a user who has never acted in the system (for example, created by mistake).

    Anyone with recorded actions can only be disabled, so the audit trail stays complete.
    """
    user = await _user(session, user_id)
    if user.id == admin.id:
        raise HTTPException(400, "You cannot delete yourself")
    has_history = await session.scalar(
        select(
            or_(
                exists().where(AuditLog.user_id == user.id),
                exists().where(Visitor.registered_by == user.id),
                exists().where(Alert.acknowledged_by == user.id),
            )
        )
    )
    if has_history:
        raise HTTPException(
            409, f"{user.username} has recorded actions; disable the account instead"
        )
    await session.delete(user)
    audit(session, admin.id, "user.delete", utcnow(), user_id=user.id, username=user.username)
    await session.commit()


@router.patch("/users/{user_id}/active", response_model=UserOut)
async def set_user_active(user_id: int, active: bool, session: Session, admin: AdminUser):
    user = await _user(session, user_id)
    if user.id == admin.id and not active:
        raise HTTPException(400, "You cannot deactivate yourself")
    user.active = active
    audit(session, admin.id, "user.active", utcnow(), user_id=user.id, active=active)
    await session.commit()
    return user
