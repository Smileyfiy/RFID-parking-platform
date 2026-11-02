from datetime import timedelta

from sqlalchemy import select, update

from gatelock.models import Alert, Lot, LotStatus, Tag, Vehicle
from gatelock.services import access
from gatelock.services.access import process_read
from gatelock.services.maintenance import run_maintenance
from gatelock.services.parking import apply_sensor_reading
from tests.conftest import at

VIP = "04A1B2C301"
VIP2 = "04A1B2C302"
STAFF = "04A1B2C311"


async def read(session, uid, now, gate="express"):
    out = []
    decision = await process_read(session, out, gate, uid, now)
    await session.commit()
    return decision, out


async def alerts(session, kind):
    return (await session.scalars(select(Alert).where(Alert.kind == kind))).all()


async def test_vip_entry_reserves_lowest_lot_then_exit_releases_it(session):
    d, out = await read(session, VIP, at(9))
    assert d.granted and d.direction == "in" and d.lot_id == "A1"
    assert d.display == "Welcome\nGo to lot A1"
    assert {k for k, _ in out} == {"lot", "access_event"}
    lot = await session.get(Lot, "A1")
    assert lot.status == LotStatus.RESERVED

    d2, _ = await read(session, VIP2, at(9, 1))
    assert d2.lot_id == "A2"

    d, _ = await read(session, VIP, at(17))
    assert d.granted and d.direction == "out" and d.reason == access.GRANTED_OUT
    await session.refresh(lot)
    assert lot.status == LotStatus.OPEN


async def test_uid_formats_are_normalised(session):
    d, _ = await read(session, "04:a1:b2:c3:01", at(9))
    assert d.granted and d.uid == VIP


async def test_unknown_tag_denied_and_burst_alert_raised_once(session):
    for i in range(4):
        d, _ = await read(session, "DEADBEEF", at(9, 0, i * 10))
        assert not d.granted and d.reason == access.UNKNOWN_TAG
    assert len(await alerts(session, "denied_burst")) == 1


async def test_staff_outside_hours_denied(session):
    d, _ = await read(session, STAFF, at(5, 59))
    assert not d.granted and d.reason == access.OUTSIDE_HOURS
    d, _ = await read(session, STAFF, at(6))
    assert d.granted and d.lot_id == "B1"


async def test_vip_allowed_at_night(session):
    d, _ = await read(session, VIP, at(2))
    assert d.granted


async def test_zone_full_refuses_entry_with_alert(session):
    for n in range(1, 5):
        await apply_sensor_reading(session, [], f"A{n}", True, at(8))
    await session.commit()
    assert len(await alerts(session, "unreserved_occupancy")) == 4

    d, _ = await read(session, VIP, at(9))
    assert not d.granted and d.reason == access.ZONE_FULL
    assert d.display == "Zone A full\nSee guard"
    assert len(await alerts(session, "zone_full")) == 1
    vehicle = await session.scalar(select(Vehicle).where(Vehicle.plate == "KDA001A"))
    assert not vehicle.inside


async def test_inactive_lot_is_never_assigned(session):
    await session.execute(update(Lot).where(Lot.id == "A1").values(enabled=False))
    await session.commit()
    d, _ = await read(session, VIP, at(9))
    assert d.lot_id == "A2"


async def test_blacklisted_vehicle_denied_with_critical_alert(session):
    await session.execute(
        update(Vehicle).where(Vehicle.plate == "KCC101C").values(blacklisted=True)
    )
    await session.commit()
    d, _ = await read(session, STAFF, at(9))
    assert not d.granted and d.reason == access.BLACKLISTED
    [alert] = await alerts(session, "blacklisted")
    assert alert.severity == "critical"


async def test_expired_pass_denied(session):
    await session.execute(update(Tag).where(Tag.uid == STAFF).values(valid_until=at(8)))
    await session.commit()
    d, _ = await read(session, STAFF, at(9))
    assert not d.granted and d.reason == access.EXPIRED


async def test_impossible_travel_between_sites(session):
    await read(session, VIP, at(9))
    d, _ = await read(session, VIP, at(9, 0, 30), gate="north")
    assert not d.granted and d.reason == access.IMPOSSIBLE_TRAVEL
    assert len(await alerts(session, "impossible_travel")) == 1


async def test_same_site_lanes_are_not_impossible_travel(session):
    await read(session, VIP, at(9))
    d, _ = await read(session, VIP, at(9, 0, 30), gate="registration")
    assert d.granted and d.direction == "out"


async def test_parking_fulfils_reservation_and_leaving_frees_lot(session):
    await read(session, VIP, at(9))
    lot = await apply_sensor_reading(session, [], "A1", True, at(9, 1))
    await session.commit()
    assert lot.status == LotStatus.OCCUPIED and lot.reserved_at is None
    assert await alerts(session, "unreserved_occupancy") == []

    lot = await apply_sensor_reading(session, [], "A1", False, at(16))
    await session.commit()
    assert lot.status == LotStatus.OPEN


async def test_unclaimed_reservation_expires(session):
    await read(session, VIP, at(9))
    await run_maintenance(session, [], at(9) + timedelta(minutes=2))
    assert (await session.get(Lot, "A1")).status == LotStatus.RESERVED
    await run_maintenance(session, [], at(9) + timedelta(minutes=4))
    await session.commit()
    assert (await session.get(Lot, "A1")).status == LotStatus.OPEN
    assert len(await alerts(session, "reservation_expired")) == 1


async def test_sensor_node_back_online_resolves_offline_alert(session):
    from gatelock.services.parking import set_node_online

    await set_node_online(session, [], "park1", False, at(9))
    await session.commit()
    [alert] = await alerts(session, "sensor_offline")
    assert alert.acknowledged_at is None
    out = []
    await set_node_online(session, out, "park1", True, at(9, 5))
    await session.commit()
    await session.refresh(alert)
    assert alert.acknowledged_at is not None
    assert ("alert", alert.id) in [(k, d["id"]) for k, d in out if k == "alert"]
