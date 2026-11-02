import os

os.environ["GATELOCK_DATABASE_URL"] = (
    "postgresql+asyncpg://gatelock:gatelock@127.0.0.1:5433/gatelock_test?ssl=disable"
)

from datetime import UTC, datetime

import pytest
from sqlalchemy import update

from gatelock.config import get_settings
from gatelock.db import Base, SessionLocal, engine
from gatelock.models import Lot
from gatelock.seed import seed


def at(hour: int, minute: int = 0, second: int = 0, day: int = 19) -> datetime:
    """A UTC instant for the given local (Nairobi) wall-clock time on a Monday."""
    local = datetime(2026, 10, day, hour, minute, second, tzinfo=get_settings().tz)
    return local.astimezone(UTC)


@pytest.fixture(scope="session", autouse=True)
async def schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def data(schema):
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.exec_driver_sql(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
    await seed("admin12345", demo=True)
    # Sensors start offline until the parking node reports; bring them up for tests.
    async with SessionLocal() as s:
        await s.execute(update(Lot).values(sensor_online=True))
        await s.commit()


@pytest.fixture
async def session():
    async with SessionLocal() as s:
        yield s
