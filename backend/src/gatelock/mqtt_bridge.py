"""Bridges MQTT device traffic (gates, parking nodes, desk readers) to the services.

Topics, under the configured prefix (default "gatelock"):
  gate/{id}/read        in   {"uid": "04A1B2C3", "read_id": "express-1734-42"}, plus
                              "sun": {"picc", "cmac"} from a secure tag (services/sun.py)
  gate/{id}/decision    out  {"read_id", "uid", "granted", "direction", "lot", "reason",
                              "display"}, or {"read_id", "uid", "ignored": true} for a
                              duplicate read inside the debounce window
  gate/{id}/command     out  {"action": "open"}
  gate/{id}/status      in   "online" | "offline" (retained; "offline" is the device's LWT)
  gate/{id}/offline     in   {"events": [{"read_id", "uid", "ts", "granted", "reason",
                              "direction", "sun"?}]}: decisions made from the cache while offline
  gate/{id}/ack         out  {"read_ids": [...]}: replayed events the gate may now discard
  sync                  out  allow-list snapshot (retained), see services/sync.py
  parking/{id}/lot      in   {"lot": "A1", "occupied": true}
  parking/{id}/status   in   "online" | "offline"
  desk/{id}/read        in   {"uid": "04A1B2C3"}
"""

import asyncio
import hashlib
import json
import logging
import time

import aiomqtt

from gatelock.config import get_settings
from gatelock.db import SessionLocal
from gatelock.hub import Message, hub
from gatelock.models import Gate, Severity, utcnow
from gatelock.mqtt_client import connect
from gatelock.schemas import GateOut
from gatelock.services.access import Debouncer, normalise_uid, process_read
from gatelock.services.alerts import raise_alert, resolve_alerts
from gatelock.services.offline import replay
from gatelock.services.parking import apply_sensor_reading, set_node_online
from gatelock.services.sync import build_snapshot

log = logging.getLogger("gatelock.mqtt")


class MqttBridge:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.prefix = self.settings.mqtt_topic_prefix
        self.debouncer = Debouncer(self.settings.debounce_seconds)
        self.client: aiomqtt.Client | None = None
        self._snapshot_digest: str | None = None

    @property
    def connected(self) -> bool:
        return self.client is not None

    async def run(self) -> None:
        while True:
            try:
                async with connect(
                    f"{self.prefix}-backend",
                    self.settings.mqtt_username,
                    self.settings.mqtt_password,
                ) as client:
                    self.client = client
                    self._snapshot_digest = None  # republish on every (re)connect
                    for topic in (
                        "gate/+/read",
                        "gate/+/status",
                        "gate/+/offline",
                        "parking/+/lot",
                        "parking/+/status",
                        "desk/+/read",
                    ):
                        await client.subscribe(f"{self.prefix}/{topic}", qos=1)
                    log.info("MQTT connected to %s", self.settings.mqtt_host)
                    async for msg in client.messages:
                        try:
                            await self.handle(str(msg.topic), msg.payload)
                        except Exception:
                            log.exception("Failed to handle %s", msg.topic)
            except aiomqtt.MqttError as exc:
                self.client = None
                log.warning("MQTT unavailable (%s); retrying in 3s", exc)
                await asyncio.sleep(3)

    async def publish(self, topic: str, payload: dict, retain: bool = False) -> bool:
        if self.client is None:
            return False
        await self.client.publish(
            f"{self.prefix}/{topic}", json.dumps(payload), qos=1, retain=retain
        )
        return True

    async def sync_loop(self) -> None:
        """Keep the retained allow-list snapshot current for gates to cache."""
        while True:
            try:
                await self.publish_snapshot()
            except Exception:
                log.exception("Snapshot publish failed")
            await asyncio.sleep(self.settings.sync_interval_seconds)

    async def publish_snapshot(self) -> None:
        if self.client is None:
            return
        async with SessionLocal() as session:
            snapshot = await build_snapshot(session, utcnow())
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        if digest == self._snapshot_digest:
            return
        snapshot["version"] = time.time_ns() // 1_000_000
        if await self.publish("sync", snapshot, retain=True):
            self._snapshot_digest = digest

    async def handle(self, topic: str, payload: bytes) -> None:
        parts = topic.split("/")
        if len(parts) != 4:
            return
        _, kind, device, leaf = parts
        text = payload.decode(errors="replace").strip()
        if leaf == "status":
            await self._status(kind, device, text == "online")
            return
        data = json.loads(text)
        if kind == "gate" and leaf == "read":
            await self._gate_read(device, data["uid"], data.get("read_id"), data.get("sun"))
        elif kind == "gate" and leaf == "offline":
            await self._offline(device, data.get("events", []))
        elif kind == "parking" and leaf == "lot":
            await self._lot(data["lot"], bool(data["occupied"]))
        elif kind == "desk" and leaf == "read":
            hub.publish([("desk_read", {"desk": device, "uid": normalise_uid(data["uid"])})])

    async def _gate_read(
        self, gate_id: str, uid: str, read_id: str | None, sun: dict | None = None
    ) -> None:
        started = time.perf_counter()
        now = utcnow()
        uid = normalise_uid(uid)
        if not self.debouncer.accept(gate_id, uid, now):
            # Answer anyway so the gate does not time out and decide from its cache.
            await self.publish(
                f"gate/{gate_id}/decision", {"read_id": read_id, "uid": uid, "ignored": True}
            )
            return
        out: list[Message] = []
        async with SessionLocal() as session:
            decision = await process_read(session, out, gate_id, uid, now, read_id, sun)
            await session.commit()
        if decision is None:
            log.warning("Read from unknown gate %s ignored", gate_id)
            return
        await self.publish(f"gate/{gate_id}/decision", decision.to_gate())
        log.info(
            "gate=%s uid=%s %s (%s) in %.0f ms",
            gate_id,
            decision.uid,
            "GRANT" if decision.granted else "DENY",
            decision.reason,
            (time.perf_counter() - started) * 1000,
        )
        hub.publish(out)

    async def _offline(self, gate_id: str, events: list[dict]) -> None:
        out: list[Message] = []
        async with SessionLocal() as session:
            acked = await replay(session, out, gate_id, events, utcnow())
            await session.commit()
        await self.publish(f"gate/{gate_id}/ack", {"read_ids": acked})
        log.info("gate=%s replayed %d offline events", gate_id, len(acked))
        hub.publish(out)
        await self.publish_snapshot()

    async def _lot(self, lot_id: str, occupied: bool) -> None:
        out: list[Message] = []
        async with SessionLocal() as session:
            await apply_sensor_reading(session, out, lot_id, occupied, utcnow())
            await session.commit()
        hub.publish(out)

    async def _status(self, kind: str, device: str, online: bool) -> None:
        out: list[Message] = []
        now = utcnow()
        async with SessionLocal() as session:
            if kind == "parking":
                await set_node_online(session, out, device, online, now)
            elif kind == "gate":
                gate = await session.get(Gate, device)
                if gate is None:
                    return
                was_online, gate.online = gate.online, online
                gate.last_seen_at = now
                out.append(("gate", GateOut.model_validate(gate).model_dump(mode="json")))
                if was_online and not online:
                    await raise_alert(
                        session,
                        out,
                        kind="gate_offline",
                        severity=Severity.WARNING,
                        message=f"{gate.name} lost its connection to the server.",
                        dedupe_key=f"gate_offline:{gate.id}",
                        gate_id=gate.id,
                        now=now,
                    )
                elif online:
                    await resolve_alerts(session, out, f"gate_offline:{gate.id}", now)
            await session.commit()
        hub.publish(out)
