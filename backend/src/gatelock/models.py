from datetime import UTC, datetime, time
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gatelock.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def _enum(cls: type[StrEnum]) -> Enum:
    return Enum(cls, name=cls.__name__.lower(), values_callable=lambda e: [m.value for m in e])


class Role(StrEnum):
    VIP = "vip"
    STAFF = "staff"
    VISITOR = "visitor"


class TagKind(StrEnum):
    PERMANENT = "permanent"
    TEMPORARY = "temporary"


class Direction(StrEnum):
    IN = "in"
    OUT = "out"


class UserRole(StrEnum):
    ADMIN = "admin"
    GUARD = "guard"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class LotStatus(StrEnum):
    OPEN = "open"
    RESERVED = "reserved"
    OCCUPIED = "occupied"
    INACTIVE = "inactive"


TZ = DateTime(timezone=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[UserRole] = mapped_column(_enum(UserRole))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TZ, default=utcnow)


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)  # "A"
    name: Mapped[str] = mapped_column(String(64))
    lots: Mapped[list["Lot"]] = relationship(back_populates="zone", order_by="Lot.number")


class RolePolicy(Base):
    """Time window and parking zone for a role (TRBAC-style periodic enabling).

    The window is [start_time, end_time) in local time. start == end means all day;
    start > end means the window crosses midnight.
    """

    __tablename__ = "role_policies"

    role: Mapped[Role] = mapped_column(_enum(Role), primary_key=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class Gate(Base):
    __tablename__ = "gates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # MQTT device id
    name: Mapped[str] = mapped_column(String(64))
    # Physical site. Reads at different locations closer together than
    # impossible_travel_seconds raise an alert.
    location: Mapped[str] = mapped_column(String(64))
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(TZ)


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    plate: Mapped[str] = mapped_column(String(16), unique=True)
    owner_name: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[Role] = mapped_column(_enum(Role))
    blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)
    blacklist_reason: Mapped[str] = mapped_column(String(256), default="")
    inside: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TZ, default=utcnow)

    tags: Mapped[list["Tag"]] = relationship(back_populates="vehicle")


class Tag(Base):
    __tablename__ = "tags"

    uid: Mapped[str] = mapped_column(String(32), primary_key=True)  # uppercase hex
    kind: Mapped[TagKind] = mapped_column(_enum(TagKind))
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_from: Mapped[datetime | None] = mapped_column(TZ)
    valid_until: Mapped[datetime | None] = mapped_column(TZ)
    last_gate_id: Mapped[str | None] = mapped_column(ForeignKey("gates.id"))
    last_seen_at: Mapped[datetime | None] = mapped_column(TZ)
    last_exit_at: Mapped[datetime | None] = mapped_column(TZ)

    vehicle: Mapped[Vehicle | None] = relationship(back_populates="tags")


class Lot(Base):
    __tablename__ = "lots"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)  # "A1"
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    number: Mapped[int] = mapped_column(Integer)
    node_id: Mapped[str] = mapped_column(String(32))  # parking sensor node reporting this lot
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sensor_online: Mapped[bool] = mapped_column(Boolean, default=False)
    occupied: Mapped[bool] = mapped_column(Boolean, default=False)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"))
    reserved_at: Mapped[datetime | None] = mapped_column(TZ)
    updated_at: Mapped[datetime] = mapped_column(TZ, default=utcnow)

    zone: Mapped[Zone] = relationship(back_populates="lots")
    vehicle: Mapped[Vehicle | None] = relationship()

    @property
    def status(self) -> LotStatus:
        if not self.enabled or not self.sensor_online:
            return LotStatus.INACTIVE
        if self.occupied:
            return LotStatus.OCCUPIED
        if self.vehicle_id is not None:
            return LotStatus.RESERVED
        return LotStatus.OPEN


class Visitor(Base):
    __tablename__ = "visitors"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    tag_uid: Mapped[str] = mapped_column(ForeignKey("tags.uid"))
    # Personal data, Fernet-encrypted (Data Protection Act, 2019).
    full_name_enc: Mapped[bytes] = mapped_column(LargeBinary)
    national_id_enc: Mapped[bytes] = mapped_column(LargeBinary)
    purpose: Mapped[str] = mapped_column(String(256), default="")
    checked_in_at: Mapped[datetime] = mapped_column(TZ, default=utcnow)
    expected_departure: Mapped[datetime] = mapped_column(TZ)
    returned_at: Mapped[datetime | None] = mapped_column(TZ)
    registered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    vehicle: Mapped[Vehicle] = relationship()


class AccessEvent(Base):
    __tablename__ = "access_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(TZ, default=utcnow, index=True)
    gate_id: Mapped[str] = mapped_column(ForeignKey("gates.id"))
    tag_uid: Mapped[str] = mapped_column(String(32), index=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"))
    plate: Mapped[str | None] = mapped_column(String(16))
    role: Mapped[Role | None] = mapped_column(_enum(Role))
    direction: Mapped[Direction | None] = mapped_column(_enum(Direction))
    granted: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String(32))
    lot_id: Mapped[str | None] = mapped_column(String(8))
    # Gate-generated id; makes replayed offline events idempotent.
    read_id: Mapped[str | None] = mapped_column(String(48), unique=True)
    # Decided by the gate from its cached allow-list while it could not reach the server.
    offline: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(TZ, default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    severity: Mapped[Severity] = mapped_column(_enum(Severity))
    message: Mapped[str] = mapped_column(Text)
    # While an unacknowledged alert with this key exists, the same alert is not raised again.
    dedupe_key: Mapped[str | None] = mapped_column(String(96), index=True)
    gate_id: Mapped[str | None] = mapped_column(String(32))
    tag_uid: Mapped[str | None] = mapped_column(String(32))
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"))
    lot_id: Mapped[str | None] = mapped_column(String(8))
    acknowledged_at: Mapped[datetime | None] = mapped_column(TZ)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(TZ, default=utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
