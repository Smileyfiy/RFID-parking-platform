from datetime import timedelta

import pytest
from sqlalchemy import select

from gatelock.models import Alert, Tag
from gatelock.schemas import VisitorCreate
from gatelock.services import visitors as svc
from gatelock.services.access import process_read
from gatelock.services.maintenance import run_maintenance
from tests.conftest import at

TEMP = "04FF000001"


def visitor(**kw):
    data = {
        "full_name": "Jane Doe",
        "national_id": "12345678",
        "plate": "kbz 123x",
        "purpose": "Delivery",
        "expected_departure": at(12),
        "tag_uid": TEMP,
    }
    return VisitorCreate(**(data | kw))


async def test_full_visit_lifecycle(session):
    v = await svc.register_visitor(session, [], visitor(), 1, at(10))
    await session.commit()
    out = svc.visitor_out(v)
    assert out.plate == "KBZ123X" and out.national_id_masked == "*****678"
    assert v.national_id_enc != b"12345678"  # stored encrypted

    d = await process_read(session, [], "registration", TEMP, at(10, 2))
    assert d.granted and d.lot_id == "C1"
    d = await process_read(session, [], "express", TEMP, at(11))
    assert d.granted and d.direction == "out"
    await session.commit()

    await run_maintenance(session, [], at(11, 11))
    await session.commit()
    assert (
        len(
            (
                await session.scalars(select(Alert).where(Alert.kind == "temp_tag_not_returned"))
            ).all()
        )
        == 1
    )

    returned = await svc.return_tag(session, [], TEMP, 1, at(11, 15))
    await session.commit()
    assert returned.returned_at is not None
    tag = await session.get(Tag, TEMP)
    assert not tag.active and tag.vehicle_id is None


async def test_visitor_outside_hours_denied(session):
    await svc.register_visitor(session, [], visitor(), 1, at(7))
    await session.commit()
    d = await process_read(session, [], "registration", TEMP, at(7, 30))
    assert not d.granted and d.reason == "outside_hours"


async def test_overstay_alert(session):
    await svc.register_visitor(session, [], visitor(), 1, at(10))
    await process_read(session, [], "registration", TEMP, at(10, 1))
    await session.commit()
    await run_maintenance(session, [], at(12, 31))
    await session.commit()
    assert await session.scalar(select(Alert).where(Alert.kind == "visitor_overstay"))


async def test_registered_vehicle_cannot_take_visitor_tag(session):
    with pytest.raises(svc.VisitorError) as e:
        await svc.register_visitor(session, [], visitor(plate="KCC 101C"), 1, at(10))
    assert e.value.status == 409


async def test_permanent_or_issued_tag_rejected(session):
    with pytest.raises(svc.VisitorError):
        await svc.register_visitor(session, [], visitor(tag_uid="04A1B2C301"), 1, at(10))
    await svc.register_visitor(session, [], visitor(), 1, at(10))
    await session.commit()
    with pytest.raises(svc.VisitorError):
        await svc.register_visitor(session, [], visitor(plate="KBY999Y"), 1, at(10))


async def test_tag_expires_at_end_of_day(session):
    await svc.register_visitor(session, [], visitor(), 1, at(10))
    await session.commit()
    d = await process_read(session, [], "registration", TEMP, at(9, day=20) + timedelta(0))
    assert not d.granted and d.reason == "pass_expired"
