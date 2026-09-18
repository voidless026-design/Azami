"""WebSocket endpoint streaming live job events (stdout/stderr/state) to the UI."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from azami.auth.tokens import TokenError, decode_token
from azami.jobs.events import bus
from azami.persistence.db import SessionLocal
from azami.persistence.models import Job
from azami.runners.base import TERMINAL_STATES

router = APIRouter()


@router.websocket("/api/ws/jobs/{job_id}")
async def stream_job(websocket: WebSocket, job_id: str, token: str = "") -> None:
    # Authenticate via ?token= query param.
    try:
        decode_token(token)
    except TokenError:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    queue = bus.subscribe(job_id)

    # Send the current snapshot first so late subscribers catch up.
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            await websocket.send_json({"job_id": job_id, "type": "error", "data": "not found"})
            await websocket.close()
            return
        await websocket.send_json({"job_id": job_id, "type": "state", "data": job.state})
        already_terminal = job.state in {s.value for s in TERMINAL_STATES}
    finally:
        db.close()

    if already_terminal:
        bus.unsubscribe(job_id, queue)
        await websocket.close()
        return

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"job_id": job_id, "type": "ping", "data": ""})
                continue
            await websocket.send_json(event)
            if event.get("type") == "state" and event.get("data") in {
                s.value for s in TERMINAL_STATES
            }:
                break
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(job_id, queue)
        try:
            await websocket.close()
        except RuntimeError:
            pass
