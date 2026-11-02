from sqlalchemy import func, select, update

from gatelock.models import AccessEvent, Alert, Lot, Tag, Vehicle
from gatelock.services.access import process_read
from gatelock.services.offline import replay
from gatelock.services.parking import apply_sensor_reading
from gatelock.services.sync import build_snapshot, tag_hash
from tests.conftest import at

VIP = "04A1B2C301"
STAFF = "04A1B2C311"
STAFF2 = "04A1B2C312"


def ev(read_id, uid, when, granted=True, direction="in", reason="granted"):
    return {
        "read_id": read_id,
        "uid": uid,
        "ts": int(when.timestamp()),
        "granted": granted,
        "direction": direction,
        "reason": reason,
    }


async def plate_inside(session, plate):
    return await session.scalar(select(Vehicle.inside).where(Vehicle.plate == plate))


async def test_snapshot_hashes_uids_and_omits_blacklisted(session):
    await session.execute(
        update(Vehicle).where(Vehicle.plate == "KCC101C").values(blacklisted=True)
    )
    await session.commit()
    snap = await build_snapshot(session, at(9))
    hashes = {t["h"] for t in snap["tags"]}
    assert tag_hash(VIP) in hashes and tag_hash(STAFF) not in hashes
    assert all(VIP not in str(t) for t in snap["tags"])
    assert snap["windows"]["staff"] == ["06:00", "22:00"]
    assert snap["role_zone"] == {"vip": "A", "staff": "B", "visitor": "C"}
    assert snap["free"] == {"A": 4, "B": 4, "C": 4}
    assert snap["utc_offset_min"] == 180
    # The 8 permanent demo tags less the blacklisted one; temporary tags not yet issued
    # are not in the allow-list.
    assert len(snap["tags"]) == 7


async def test_redelivered_read_returns_stored_decision(session):
    d1 = await process_read(session, [], "express", VIP, at(9), read_id="express-1")
    await session.commit()
    d2 = await process_read(session, [], "express", VIP, at(9, 0, 1), read_id="express-1")
    assert d2.granted and d2.direction == "in" and d2.lot_id == d1.lot_id
    assert await session.scalar(select(func.count()).select_from(AccessEvent)) == 1


async def test_replay_applies_events_once(session):
    events = [ev("g-2", STAFF, at(9, 30), direction="out", reason="exit"), ev("g-1", STAFF, at(9))]
    acked = await replay(session, [], "express", events, at(10))
    await session.commit()
    assert acked == ["g-1", "g-2"]  # applied in time order
    assert await plate_inside(session, "KCC101C") is False
    rows = (await session.scalars(select(AccessEvent).order_by(AccessEvent.ts))).all()
    assert [r.direction for r in rows] == ["in", "out"] and all(r.offline for r in rows)

    acked = await replay(session, [], "express", events, at(10, 1))
    await session.commit()
    assert sorted(acked) == ["g-1", "g-2"]
    assert await session.scalar(select(func.count()).select_from(AccessEvent)) == 2


async def test_replay_skips_read_the_server_already_decided(session):
    await process_read(session, [], "express", VIP, at(9), read_id="express-7")
    await session.commit()
    acked = await replay(session, [], "express", [ev("express-7", VIP, at(9))], at(9, 5))
    await session.commit()
    assert acked == ["express-7"]
    assert await session.scalar(select(func.count()).select_from(AccessEvent)) == 1


async def test_replay_flags_vehicle_blacklisted_after_last_sync(session):
    await session.execute(
        update(Vehicle).where(Vehicle.plate == "KCC101C").values(blacklisted=True)
    )
    await session.commit()
    await replay(session, [], "express", [ev("g-1", STAFF, at(9))], at(10))
    await session.commit()
    alert = await session.scalar(select(Alert).where(Alert.kind == "offline_violation"))
    assert alert.severity == "critical" and "KCC101C" in alert.message


async def test_replay_flags_returned_visitor_tag(session):
    await session.execute(update(Tag).where(Tag.uid == STAFF).values(active=False))
    await session.commit()
    await replay(session, [], "express", [ev("g-1", STAFF, at(9))], at(10))
    await session.commit()
    assert await session.scalar(select(Alert).where(Alert.kind == "offline_violation"))


async def test_offline_admitted_car_is_matched_to_the_lot_it_parks_in(session):
    await replay(session, [], "express", [ev("g-1", STAFF, at(9))], at(10))
    lot = await apply_sensor_reading(session, [], "B3", True, at(10, 1))
    await session.commit()
    assert lot.status == "occupied" and lot.vehicle.plate == "KCC101C"
    assert await session.scalar(select(func.count()).select_from(Alert)) == 0


async def test_several_unplaced_cars_give_info_alert_not_warning(session):
    await replay(
        session, [], "express", [ev("g-1", STAFF, at(9)), ev("g-2", STAFF2, at(9, 1))], at(10)
    )
    lot = await apply_sensor_reading(session, [], "B3", True, at(10, 1))
    await session.commit()
    assert lot.vehicle_id is None
    alert = await session.scalar(select(Alert).where(Alert.kind == "unreserved_occupancy"))
    assert alert.severity == "info"
    assert await session.get(Lot, "B3")


async def test_replay_corrects_a_wrong_lot_guess(session):
    # Online: VIP parks in A1.
    await process_read(session, [], "express", VIP, at(9))
    await apply_sensor_reading(session, [], "A1", True, at(9, 1))
    # Outage: VIP leaves (A1 frees), second VIP enters and parks in A2. The server guesses
    # A2 belongs to the first VIP, the only unplaced VIP it knows is inside.
    await apply_sensor_reading(session, [], "A1", False, at(10))
    lot = await apply_sensor_reading(session, [], "A2", True, at(10, 1))
    assert lot.vehicle.plate == "KDA001A"
    await session.commit()

    await replay(
        session,
        [],
        "express",
        [ev("g-1", VIP, at(10), direction="out", reason="exit"), ev("g-2", "04A1B2C302", at(10))],
        at(10, 5),
    )
    await session.commit()
    lot = await session.get(Lot, "A2")
    await session.refresh(lot, ["vehicle"])
    assert lot.vehicle.plate == "KDB002B"
