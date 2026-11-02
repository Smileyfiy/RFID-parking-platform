from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gatelock.config import get_settings
from gatelock.hub import Message
from gatelock.models import Lot, LotStatus, RolePolicy, Severity, Vehicle, Zone
from gatelock.schemas import LotOut, ZoneOut, lot_out
from gatelock.services.alerts import raise_alert, resolve_alerts


async def _load_lot(session: AsyncSession, lot_id: str) -> Lot | None:
    return await session.scalar(
        select(Lot).options(selectinload(Lot.vehicle)).where(Lot.id == lot_id).with_for_update()
    )


async def allocate_lot(
    session: AsyncSession, zone_id: str, vehicle_id: int, now: datetime
) -> Lot | None:
    """Reserve the lowest-numbered open lot in the zone for the vehicle."""
    lot = await session.scalar(
        select(Lot)
        .where(
            Lot.zone_id == zone_id,
            Lot.enabled.is_(True),
            Lot.sensor_online.is_(True),
            Lot.occupied.is_(False),
            Lot.vehicle_id.is_(None),
        )
        .order_by(Lot.number)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if lot is None:
        return None
    lot.vehicle_id = vehicle_id
    lot.reserved_at = now
    lot.updated_at = now
    return lot


async def release_vehicle(
    session: AsyncSession, out: list[Message], vehicle_id: int, now: datetime
) -> None:
    """Detach a vehicle from any lot it holds. The sensor still decides occupancy."""
    lots = await session.scalars(
        select(Lot).options(selectinload(Lot.vehicle)).where(Lot.vehicle_id == vehicle_id)
    )
    for lot in lots:
        lot.vehicle_id = None
        lot.vehicle = None
        lot.reserved_at = None
        lot.updated_at = now
        out.append(("lot", lot_out(lot)))


async def apply_sensor_reading(
    session: AsyncSession, out: list[Message], lot_id: str, occupied: bool, now: datetime
) -> Lot | None:
    lot = await _load_lot(session, lot_id)
    if lot is None:
        return None
    lot.sensor_online = True
    if lot.occupied == occupied:
        return lot
    lot.occupied = occupied
    lot.updated_at = now
    if occupied:
        if lot.vehicle_id is None:
            await _unreserved_occupancy(session, out, lot, now)
        else:
            lot.reserved_at = None  # reservation fulfilled
    else:
        # The parked vehicle left the lot; it no longer holds it.
        lot.vehicle_id = None
        lot.vehicle = None
        lot.reserved_at = None
    out.append(("lot", lot_out(lot)))
    return lot


async def _unplaced_vehicles(session: AsyncSession, zone_id: str) -> list[Vehicle]:
    """Vehicles inside whose role parks in this zone but which hold no lot.

    These were admitted while the gate was offline, or let their reservation expire.
    """
    roles = select(RolePolicy.role).where(RolePolicy.zone_id == zone_id)
    held = select(Lot.vehicle_id).where(Lot.vehicle_id.is_not(None))
    return list(
        await session.scalars(
            select(Vehicle).where(
                Vehicle.inside.is_(True), Vehicle.role.in_(roles), Vehicle.id.not_in(held)
            )
        )
    )


async def _unreserved_occupancy(
    session: AsyncSession, out: list[Message], lot: Lot, now: datetime
) -> None:
    unplaced = await _unplaced_vehicles(session, lot.zone_id)
    if len(unplaced) == 1:
        # Only one candidate: assume it is that vehicle and attach it to the lot.
        lot.vehicle_id = unplaced[0].id
        lot.vehicle = unplaced[0]
        return
    if unplaced:
        await raise_alert(
            session,
            out,
            kind="unreserved_occupancy",
            severity=Severity.INFO,
            message=(
                f"Lot {lot.id} became occupied without a reservation; probably one of"
                f" {len(unplaced)} vehicles admitted without a lot."
            ),
            lot_id=lot.id,
            now=now,
        )
        return
    await raise_alert(
        session,
        out,
        kind="unreserved_occupancy",
        severity=Severity.WARNING,
        message=f"Lot {lot.id} became occupied without a reservation.",
        dedupe_key=f"unreserved:{lot.id}",
        lot_id=lot.id,
        now=now,
    )


async def reconcile_unplaced(session: AsyncSession, out: list[Message], now: datetime) -> None:
    """Pair occupied-but-unassigned lots with unplaced vehicles where only one pairing fits.

    Run after an offline replay, once the server knows which vehicles are really inside.
    """
    lots = await session.scalars(
        select(Lot)
        .options(selectinload(Lot.vehicle))
        .where(Lot.occupied.is_(True), Lot.vehicle_id.is_(None))
    )
    by_zone: dict[str, list[Lot]] = {}
    for lot in lots:
        by_zone.setdefault(lot.zone_id, []).append(lot)
    for zone_id, zone_lots in by_zone.items():
        unplaced = await _unplaced_vehicles(session, zone_id)
        if len(zone_lots) == 1 and len(unplaced) == 1:
            lot = zone_lots[0]
            lot.vehicle_id = unplaced[0].id
            lot.vehicle = unplaced[0]
            lot.updated_at = now
            out.append(("lot", lot_out(lot)))


async def set_node_online(
    session: AsyncSession, out: list[Message], node_id: str, online: bool, now: datetime
) -> None:
    lots = await session.scalars(
        select(Lot).options(selectinload(Lot.vehicle)).where(Lot.node_id == node_id)
    )
    changed = False
    for lot in lots:
        if lot.sensor_online != online:
            lot.sensor_online = online
            lot.updated_at = now
            out.append(("lot", lot_out(lot)))
            changed = True
    if online:
        await resolve_alerts(session, out, f"node_offline:{node_id}", now)
    elif changed:
        await raise_alert(
            session,
            out,
            kind="sensor_offline",
            severity=Severity.WARNING,
            message=f"Parking sensor node {node_id} went offline; its lots are inactive.",
            dedupe_key=f"node_offline:{node_id}",
            now=now,
        )


async def expire_reservations(session: AsyncSession, out: list[Message], now: datetime) -> None:
    cutoff = now - timedelta(seconds=get_settings().reservation_timeout_seconds)
    lots = await session.scalars(
        select(Lot)
        .options(selectinload(Lot.vehicle))
        .where(Lot.reserved_at.is_not(None), Lot.reserved_at < cutoff, Lot.occupied.is_(False))
        .with_for_update(skip_locked=True)
    )
    for lot in lots:
        plate = lot.vehicle.plate if lot.vehicle else "?"
        vehicle_id = lot.vehicle_id
        lot.vehicle_id = None
        lot.vehicle = None
        lot.reserved_at = None
        lot.updated_at = now
        out.append(("lot", lot_out(lot)))
        await raise_alert(
            session,
            out,
            kind="reservation_expired",
            severity=Severity.INFO,
            message=f"{plate} did not park in {lot.id}; the reservation was released.",
            vehicle_id=vehicle_id,
            lot_id=lot.id,
            now=now,
        )


async def zone_summaries(session: AsyncSession) -> list[ZoneOut]:
    zones = await session.scalars(
        select(Zone).options(selectinload(Zone.lots).selectinload(Lot.vehicle)).order_by(Zone.id)
    )
    roles = {p.zone_id: p.role for p in await session.scalars(select(RolePolicy))}
    result = []
    for z in zones:
        lots = [LotOut.model_validate(lot_out(lot)) for lot in z.lots]
        result.append(
            ZoneOut(
                id=z.id,
                name=z.name,
                role=roles.get(z.id),
                total=len(lots),
                free=sum(1 for lot in lots if lot.status == LotStatus.OPEN),
                lots=lots,
            )
        )
    return result


async def set_lot_enabled(
    session: AsyncSession, out: list[Message], lot_id: str, enabled: bool, now: datetime
) -> Lot | None:
    lot = await _load_lot(session, lot_id)
    if lot is None:
        return None
    lot.enabled = enabled
    lot.updated_at = now
    out.append(("lot", lot_out(lot)))
    return lot
