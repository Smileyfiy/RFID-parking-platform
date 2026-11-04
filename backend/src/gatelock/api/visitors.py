from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from gatelock.api.deps import CurrentUser, Session, commit_and_publish
from gatelock.hub import Message
from gatelock.models import Visitor, utcnow
from gatelock.schemas import VisitorCreate, VisitorOut
from gatelock.services import visitors as svc

router = APIRouter(tags=["visitors"])


class TagReturn(BaseModel):
    tag_uid: str


@router.get("/visitors", response_model=list[VisitorOut])
async def list_visitors(session: Session, _: CurrentUser, open: bool = True, limit: int = 100):
    stmt = (
        select(Visitor)
        .options(selectinload(Visitor.vehicle))
        .order_by(Visitor.checked_in_at.desc())
        .limit(limit)
    )
    if open:
        stmt = stmt.where(Visitor.returned_at.is_(None))
    return [svc.visitor_out(v) for v in await session.scalars(stmt)]


@router.post("/visitors", response_model=VisitorOut, status_code=201)
async def register(data: VisitorCreate, session: Session, user: CurrentUser):
    out: list[Message] = []
    try:
        visitor = await svc.register_visitor(session, out, data, user.id, utcnow())
    except svc.VisitorError as e:
        raise HTTPException(e.status, e.detail) from e
    await commit_and_publish(session, out + [("visitor", None)])
    return svc.visitor_out(visitor)


@router.post("/visitors/return", response_model=VisitorOut | None)
async def return_tag(data: TagReturn, session: Session, user: CurrentUser):
    out: list[Message] = []
    try:
        visitor = await svc.return_tag(session, out, data.tag_uid, user.id, utcnow())
    except svc.VisitorError as e:
        raise HTTPException(e.status, e.detail) from e
    await commit_and_publish(session, out + [("visitor", None)])
    return svc.visitor_out(visitor) if visitor else None
