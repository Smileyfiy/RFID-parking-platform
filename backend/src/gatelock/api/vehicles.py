from fastapi import APIRouter, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from gatelock.api.deps import AdminUser, CurrentUser, Session
from gatelock.models import Role, Tag, TagKind, Vehicle, utcnow
from gatelock.schemas import TagAssign, TagCreate, TagOut, VehicleCreate, VehicleOut, VehicleUpdate
from gatelock.services.access import normalise_uid
from gatelock.services.audit import audit
from gatelock.services.visitors import normalise_plate

router = APIRouter(tags=["vehicles"])


async def _vehicle(session, vehicle_id: int) -> Vehicle:
    v = await session.scalar(
        select(Vehicle).options(selectinload(Vehicle.tags)).where(Vehicle.id == vehicle_id)
    )
    if v is None:
        raise HTTPException(404, "Vehicle not found")
    return v


@router.get("/vehicles", response_model=list[VehicleOut])
async def list_vehicles(
    session: Session,
    _: CurrentUser,
    q: str = "",
    role: Role | None = None,
    inside: bool | None = None,
    limit: int = 200,
):
    stmt = select(Vehicle).options(selectinload(Vehicle.tags)).order_by(Vehicle.plate)
    if q:
        stmt = stmt.where(or_(Vehicle.plate.ilike(f"%{q}%"), Vehicle.owner_name.ilike(f"%{q}%")))
    if role:
        stmt = stmt.where(Vehicle.role == role)
    if inside is not None:
        stmt = stmt.where(Vehicle.inside.is_(inside))
    return (await session.scalars(stmt.limit(limit))).all()


@router.post("/vehicles", response_model=VehicleOut, status_code=201)
async def create_vehicle(data: VehicleCreate, session: Session, admin: AdminUser):
    plate = normalise_plate(data.plate)
    if await session.scalar(select(Vehicle).where(Vehicle.plate == plate)):
        raise HTTPException(409, f"{plate} is already registered")
    v = Vehicle(plate=plate, owner_name=data.owner_name, role=data.role)
    session.add(v)
    await session.flush()
    audit(session, admin.id, "vehicle.create", utcnow(), vehicle_id=v.id, plate=plate)
    await session.commit()
    return await _vehicle(session, v.id)


@router.get("/vehicles/{vehicle_id}", response_model=VehicleOut)
async def get_vehicle(vehicle_id: int, session: Session, _: CurrentUser):
    return await _vehicle(session, vehicle_id)


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleOut)
async def update_vehicle(vehicle_id: int, data: VehicleUpdate, session: Session, admin: AdminUser):
    v = await _vehicle(session, vehicle_id)
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(v, field, value)
    audit(
        session,
        admin.id,
        "vehicle.update",
        utcnow(),
        vehicle_id=v.id,
        **{k: str(val) for k, val in changes.items()},
    )
    await session.commit()
    return await _vehicle(session, v.id)


@router.get("/tags", response_model=list[TagOut])
async def list_tags(
    session: Session, _: CurrentUser, kind: TagKind | None = None, available: bool | None = None
):
    stmt = select(Tag).order_by(Tag.uid)
    if kind:
        stmt = stmt.where(Tag.kind == kind)
    if available is not None:
        stmt = stmt.where(Tag.active.is_(not available))
    return (await session.scalars(stmt)).all()


@router.post("/tags", response_model=TagOut, status_code=201)
async def create_tag(data: TagCreate, session: Session, admin: AdminUser):
    uid = normalise_uid(data.uid)
    if await session.get(Tag, uid):
        raise HTTPException(409, f"Tag {uid} already exists")
    if data.secure and len(uid) != 14:
        raise HTTPException(422, "Secure (NTAG 424 DNA) tags have a 7-byte UID: 14 hex characters")
    tag = Tag(uid=uid, kind=data.kind, secure=data.secure)
    session.add(tag)
    audit(session, admin.id, "tag.create", utcnow(), tag=uid, kind=data.kind, secure=data.secure)
    await session.commit()
    return tag


@router.patch("/tags/{uid}", response_model=TagOut)
async def assign_tag(uid: str, data: TagAssign, session: Session, admin: AdminUser):
    """Link a permanent tag to a vehicle (or unlink it with vehicle_id null)."""
    tag = await session.get(Tag, normalise_uid(uid))
    if tag is None:
        raise HTTPException(404, "Tag not found")
    if tag.kind != TagKind.PERMANENT:
        raise HTTPException(409, "Visitor tags are issued at the registration lane")
    if data.vehicle_id is not None:
        vehicle = await _vehicle(session, data.vehicle_id)
        if vehicle.role == Role.VISITOR:
            raise HTTPException(409, "Visitor vehicles use temporary tags")
        if any(t.active and t.uid != tag.uid for t in vehicle.tags):
            raise HTTPException(409, f"{vehicle.plate} already has an active tag")
    tag.vehicle_id = data.vehicle_id
    tag.active = data.active and data.vehicle_id is not None
    tag.valid_from = data.valid_from
    tag.valid_until = data.valid_until
    audit(
        session,
        admin.id,
        "tag.assign",
        utcnow(),
        tag=tag.uid,
        vehicle_id=data.vehicle_id,
        active=tag.active,
    )
    await session.commit()
    return tag
