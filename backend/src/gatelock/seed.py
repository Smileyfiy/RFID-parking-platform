"""Seed reference data (zones, lots, gates, policies, admin) and optional demo data.

uv run gatelock-seed --admin-password secret123 --demo
"""

import argparse
import asyncio
from datetime import time

from sqlalchemy import select

from gatelock.db import SessionLocal
from gatelock.models import (
    Gate,
    Lot,
    Role,
    RolePolicy,
    Tag,
    TagKind,
    User,
    UserRole,
    Vehicle,
    Zone,
)
from gatelock.security import hash_password

ZONES = [
    ("A", "VIP", Role.VIP),
    ("B", "Staff", Role.STAFF),
    ("C", "Visitors & deliveries", Role.VISITOR),
]
LOTS_PER_ZONE = 4
PARKING_NODE = "park1"
WINDOWS = {
    Role.VIP: (time(0), time(0)),  # all day
    Role.STAFF: (time(6), time(22)),
    Role.VISITOR: (time(8), time(18)),
}
GATES = [
    ("express", "Main gate: express lane", "main"),
    ("registration", "Main gate: registration lane", "main"),
    ("north", "North gate", "north"),
]
DEMO_VEHICLES = [
    ("KDA001A", "Prof. Wanjiku Kamau", Role.VIP, "04A1B2C301"),
    ("KDB002B", "Dr. Ali Hassan", Role.VIP, "04A1B2C302"),
    ("KCC101C", "Grace Achieng", Role.STAFF, "04A1B2C311"),
    ("KCD102D", "Peter Mwangi", Role.STAFF, "04A1B2C312"),
    ("KCE103E", "Mary Njeri", Role.STAFF, "04A1B2C313"),
    ("KCF104F", "James Otieno", Role.STAFF, "04A1B2C314"),
    ("KCG105G", "Susan Wairimu", Role.STAFF, "04A1B2C315"),
]
DEMO_TEMP_TAGS = [f"04FF00000{i}" for i in range(1, 6)]


async def seed(admin_password: str, demo: bool) -> None:
    async with SessionLocal() as s:
        for zone_id, name, role in ZONES:
            if await s.get(Zone, zone_id) is None:
                s.add(Zone(id=zone_id, name=name))
                for n in range(1, LOTS_PER_ZONE + 1):
                    s.add(Lot(id=f"{zone_id}{n}", zone_id=zone_id, number=n, node_id=PARKING_NODE))
            await s.flush()
            if await s.get(RolePolicy, role) is None:
                start, end = WINDOWS[role]
                s.add(RolePolicy(role=role, zone_id=zone_id, start_time=start, end_time=end))
        for gate_id, name, location in GATES:
            if await s.get(Gate, gate_id) is None:
                s.add(Gate(id=gate_id, name=name, location=location))
        if await s.scalar(select(User).where(User.username == "admin")) is None:
            s.add(
                User(
                    username="admin",
                    full_name="Administrator",
                    role=UserRole.ADMIN,
                    password_hash=hash_password(admin_password),
                )
            )

        if demo:
            if await s.scalar(select(User).where(User.username == "guard")) is None:
                s.add(
                    User(
                        username="guard",
                        full_name="Gate Guard",
                        role=UserRole.GUARD,
                        password_hash=hash_password(admin_password),
                    )
                )
            for plate, owner, role, uid in DEMO_VEHICLES:
                if await s.scalar(select(Vehicle).where(Vehicle.plate == plate)):
                    continue
                v = Vehicle(plate=plate, owner_name=owner, role=role)
                s.add(v)
                await s.flush()
                s.add(Tag(uid=uid, kind=TagKind.PERMANENT, vehicle_id=v.id, active=True))
            for uid in DEMO_TEMP_TAGS:
                if await s.get(Tag, uid) is None:
                    s.add(Tag(uid=uid, kind=TagKind.TEMPORARY))
        await s.commit()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--admin-password", required=True)
    p.add_argument("--demo", action="store_true", help="add demo vehicles, tags and a guard user")
    args = p.parse_args()
    asyncio.run(seed(args.admin_password, args.demo))
    print("Seeded.")


if __name__ == "__main__":
    main()
