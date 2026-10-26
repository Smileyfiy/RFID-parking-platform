from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field

from gatelock.models import Direction, LotStatus, Role, Severity, TagKind, UserRole


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LotOut(ORM):
    id: str
    zone_id: str
    number: int
    status: LotStatus
    enabled: bool
    sensor_online: bool
    occupied: bool
    vehicle_id: int | None
    reserved_at: datetime | None
    plate: str | None = None


class ZoneOut(BaseModel):
    id: str
    name: str
    role: Role | None
    total: int
    free: int
    lots: list[LotOut]


class AccessEventOut(ORM):
    id: int
    ts: datetime
    gate_id: str
    tag_uid: str
    vehicle_id: int | None
    plate: str | None
    role: Role | None
    direction: Direction | None
    granted: bool
    reason: str
    lot_id: str | None
    offline: bool


class AlertOut(ORM):
    id: int
    ts: datetime
    kind: str
    severity: Severity
    message: str
    gate_id: str | None
    tag_uid: str | None
    vehicle_id: int | None
    lot_id: str | None
    acknowledged_at: datetime | None


class GateOut(ORM):
    id: str
    name: str
    location: str
    online: bool
    last_seen_at: datetime | None


class TagOut(ORM):
    uid: str
    kind: TagKind
    vehicle_id: int | None
    active: bool
    valid_from: datetime | None
    valid_until: datetime | None
    last_seen_at: datetime | None


class TagCreate(BaseModel):
    uid: str = Field(pattern=r"^[0-9A-Fa-f]{8,32}$")
    kind: TagKind


class TagAssign(BaseModel):
    vehicle_id: int | None
    active: bool = True
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class VehicleOut(ORM):
    id: int
    plate: str
    owner_name: str
    role: Role
    blacklisted: bool
    blacklist_reason: str
    inside: bool
    created_at: datetime
    tags: list[TagOut] = []


class VehicleCreate(BaseModel):
    plate: str = Field(min_length=2, max_length=16)
    owner_name: str = ""
    role: Role


class VehicleUpdate(BaseModel):
    owner_name: str | None = None
    role: Role | None = None
    blacklisted: bool | None = None
    blacklist_reason: str | None = None


class PolicyOut(ORM):
    role: Role
    zone_id: str
    start_time: time
    end_time: time


class PolicyUpdate(BaseModel):
    zone_id: str | None = None
    start_time: time | None = None
    end_time: time | None = None


class VisitorCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=128)
    national_id: str = Field(pattern=r"^[0-9A-Za-z]{5,20}$")
    plate: str = Field(min_length=2, max_length=16)
    purpose: str = Field(default="", max_length=256)
    expected_departure: datetime
    tag_uid: str


class VisitorOut(BaseModel):
    id: int
    full_name: str
    national_id_masked: str
    plate: str
    purpose: str
    tag_uid: str
    checked_in_at: datetime
    expected_departure: datetime
    returned_at: datetime | None
    inside: bool


class UserOut(ORM):
    id: int
    username: str
    full_name: str
    role: UserRole
    active: bool


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    full_name: str = ""
    password: str = Field(min_length=8)
    role: UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def lot_out(lot) -> dict:
    data = LotOut.model_validate(lot)
    data.plate = lot.vehicle.plate if lot.vehicle_id and lot.vehicle else None
    return data.model_dump(mode="json")
