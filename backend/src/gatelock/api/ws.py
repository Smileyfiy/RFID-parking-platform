import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from gatelock.api.deps import user_from_token
from gatelock.db import SessionLocal
from gatelock.hub import hub

router = APIRouter()


@router.websocket("/ws")
async def live(ws: WebSocket, token: str = ""):
    """Live feed for the dashboard: access events, lot changes, alerts, gate status."""
    async with SessionLocal() as session:
        user = await user_from_token(session, token)
    if user is None:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await ws.accept()
    queue = hub.subscribe()
    try:
        receiver = asyncio.create_task(ws.receive_text())  # detects client disconnects
        while True:
            getter = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait({getter, receiver}, return_when=asyncio.FIRST_COMPLETED)
            if receiver in done:
                getter.cancel()
                receiver.result()  # raises WebSocketDisconnect
                receiver = asyncio.create_task(ws.receive_text())
                continue
            await ws.send_json(getter.result())
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(queue)
        receiver.cancel()
