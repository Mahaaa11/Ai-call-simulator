#!/usr/bin/env python3
"""
FastAPI avatar + TTS server with WebSocket streaming.

Replaces stdlib tts_server.py for low-latency avatar pipelines:
  HTML/JS  ←WebSocket→  FastAPI  →  edge-tts  →  MuseTalk  →  LivePortrait (idle)

Env:
  AVATAR_PORT=8767
  AVATAR_BACKEND=stub|musetalk|musetalk+liveportrait
  MUSETALK_URL=http://127.0.0.1:8780
  LIVEPORTRAIT_URL=http://127.0.0.1:8781
"""

from __future__ import annotations

import os
import urllib.parse

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from avatar_server.backends.factory import get_avatar_backend, get_idle_backend
from avatar_server.pipeline import run_idle_pipeline, run_speak_pipeline
from avatar_server.tts import synthesize_sync

PORT = int(os.getenv("AVATAR_PORT", "8767"))
BIND_HOST = os.getenv("BIND_HOST", "127.0.0.1")

app = FastAPI(title="AI Call Simulator Avatar API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    try:
        synthesize_sync("ok")
        tts_ok = True
        tts_error = None
    except Exception as exc:
        tts_ok = False
        tts_error = str(exc)

    return {
        "ok": tts_ok,
        "tts": tts_ok,
        "tts_error": tts_error,
        "avatar_backend": get_avatar_backend().name,
        "idle_backend": get_idle_backend().name,
        "websocket": True,
        "ws_path": "/ws/avatar",
    }


@app.get("/tts")
def tts_http(
    text: str = Query("", max_length=500),
    voice: str | None = Query(None),
    tone: str = Query("calm"),
):
    """Drop-in replacement for legacy GET /tts on port 8765."""
    if not text.strip():
        return Response(status_code=400, content=b"Missing text")
    try:
        audio = synthesize_sync(text.strip(), voice, tone)
    except Exception as exc:
        return Response(status_code=500, content=str(exc).encode())
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-cache"},
    )


@app.websocket("/ws/avatar")
async def ws_avatar(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")

            if kind == "ping":
                await ws.send_json({"type": "pong"})
                continue

            if kind == "speak":
                async for event in run_speak_pipeline(
                    text=str(msg.get("text") or ""),
                    voice=msg.get("voice"),
                    tone=str(msg.get("tone") or "calm"),
                    gender=msg.get("portrait") or msg.get("gender"),
                    session_id=msg.get("session_id"),
                ):
                    await ws.send_json(event)
                continue

            if kind == "idle":
                async for event in run_idle_pipeline(
                    gender=msg.get("portrait") or msg.get("gender"),
                    session_id=msg.get("session_id"),
                ):
                    await ws.send_json(event)
                continue

            await ws.send_json({"type": "error", "message": f"Unknown type: {kind}"})
    except WebSocketDisconnect:
        return
    except Exception as exc:
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass


def main() -> None:
    import uvicorn

    print(f"Avatar API  : http://{BIND_HOST}:{PORT}/health")
    print(f"WebSocket   : ws://{BIND_HOST}:{PORT}/ws/avatar")
    print(f"TTS (HTTP)  : http://{BIND_HOST}:{PORT}/tts?text=Bonjour")
    print(f"Backend     : {get_avatar_backend().name} + idle {get_idle_backend().name}")
    uvicorn.run(app, host=BIND_HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
