import pytest
from httpx import ASGITransport, AsyncClient

from gatelock.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def token(client, user="admin"):
    r = await client.post("/api/auth/login", data={"username": user, "password": "admin12345"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_requires_auth(client):
    assert (await client.get("/api/parking/zones")).status_code == 401


async def test_bad_password(client):
    r = await client.post("/api/auth/login", data={"username": "admin", "password": "nope"})
    assert r.status_code == 401


async def test_zones(client):
    r = await client.get("/api/parking/zones", headers=await token(client))
    zones = r.json()
    assert [z["id"] for z in zones] == ["A", "B", "C"]
    assert all(z["total"] == 4 and z["free"] == 4 for z in zones)


async def test_guard_cannot_change_policies(client):
    r = await client.patch(
        "/api/policies/staff", json={"start_time": "05:00:00"}, headers=await token(client, "guard")
    )
    assert r.status_code == 403


async def test_admin_registers_vehicle_and_tag(client):
    h = await token(client)
    r = await client.post(
        "/api/vehicles",
        json={"plate": "kcx 555z", "role": "staff", "owner_name": "New Staff"},
        headers=h,
    )
    assert r.status_code == 201
    vid = r.json()["id"]
    r = await client.post("/api/tags", json={"uid": "0A0B0C0D", "kind": "permanent"}, headers=h)
    assert r.status_code == 201
    r = await client.patch("/api/tags/0A0B0C0D", json={"vehicle_id": vid}, headers=h)
    assert r.json()["active"] is True
    r = await client.get(f"/api/vehicles/{vid}", headers=h)
    assert r.json()["plate"] == "KCX555Z" and r.json()["tags"][0]["uid"] == "0A0B0C0D"


async def test_visitor_registration_and_list(client):
    h = await token(client, "guard")
    r = await client.post(
        "/api/visitors",
        headers=h,
        json={
            "full_name": "Jane Doe",
            "national_id": "12345678",
            "plate": "KBZ123X",
            "purpose": "Meeting",
            "expected_departure": "2030-01-01T12:00:00Z",
            "tag_uid": "04FF000001",
        },
    )
    assert r.status_code == 201, r.text
    r = await client.get("/api/visitors", headers=h)
    assert r.json()[0]["national_id_masked"] == "*****678"


async def test_report_summary(client):
    r = await client.get("/api/reports/summary", headers=await token(client))
    assert r.status_code == 200 and r.json()["inside_now"] == 0
