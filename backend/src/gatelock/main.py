import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gatelock.api import auth, monitor, vehicles, visitors, ws
from gatelock.config import get_settings
from gatelock.db import SessionLocal
from gatelock.hub import Message, hub
from gatelock.models import utcnow
from gatelock.mqtt_bridge import MqttBridge
from gatelock.services.maintenance import run_maintenance

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("gatelock")


async def maintenance_loop() -> None:
    interval = get_settings().maintenance_interval_seconds
    while True:
        try:
            out: list[Message] = []
            async with SessionLocal() as session:
                await run_maintenance(session, out, utcnow())
                await session.commit()
            hub.publish(out)
        except Exception:
            log.exception("Maintenance run failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bridge = MqttBridge()
    tasks = [
        asyncio.create_task(app.state.bridge.run()),
        asyncio.create_task(app.state.bridge.sync_loop()),
        asyncio.create_task(maintenance_loop()),
    ]
    yield
    for t in tasks:
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t


app = FastAPI(title="Gatelock", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
for r in (auth.router, vehicles.router, visitors.router, monitor.router):
    app.include_router(r, prefix="/api")
app.include_router(ws.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "mqtt": app.state.bridge.connected}
