"""
Standalone Pure-Asyncio Streaming WebSocket Server for Gnani Prisma v3.0.
Listens on ws://0.0.0.0:8001/ws/gnani/stream/
Directly uses Python's pure-asyncio `websockets` library (version 17.4).
Bypasses Twisted/Daphne entirely to guarantee 100% reliability on Python 3.14 Windows.
"""
import asyncio
import json
import logging
import os
import sys
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# Setup environment from .env
BASE_DIR = Path(__file__).resolve().parent
env_file = BASE_DIR / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("gnani_ws_server")

GNANI_API_KEY = os.environ.get("GNANI_API_KEY", "")
GNANI_STT_WS_URL = os.environ.get("GNANI_STT_WS_URL", "wss://api.vachana.ai/stt/v3/stream")
GNANI_STT_MODEL = os.environ.get("GNANI_STT_MODEL", "prisma-v3.0")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ASHA-Voice-GnaniClient/1.0"

LANG_MAP = {
    "ta": "ta-IN",
    "hi": "hi-IN",
    "kn": "kn-IN",
    "en": "en-IN",
}


async def handler(websocket):
    raw_path = websocket.request.path if hasattr(websocket, "request") else getattr(websocket, "path", "/")
    parsed = urlparse(raw_path)
    params = parse_qs(parsed.query)
    lang = params.get("language", ["ta"])[0]
    lang_code = LANG_MAP.get(lang, "indic-auto")

    logger.info(f"Client connected for language: {lang} ({lang_code}) from {websocket.remote_address}")

    if not GNANI_API_KEY or GNANI_API_KEY.startswith("your_"):
        await websocket.send(json.dumps({
            "type": "error",
            "message": "GNANI_API_KEY is not configured in backend/.env"
        }))
        await websocket.close(4001, "GNANI_API_KEY not configured")
        return

    # Connect to Gnani Prisma v3.0 STT WebSocket
    ws_headers = {
        "x-api-key-id": GNANI_API_KEY,
        "model": GNANI_STT_MODEL,
        "language_code": lang_code,
        "partials_enabled": "true",
        "format": "verbatim",
        "User-Agent": USER_AGENT,
    }

    try:
        try:
            gnani_ws = await websockets.connect(
                GNANI_STT_WS_URL,
                additional_headers=ws_headers,
                open_timeout=10,
            )
        except TypeError:
            gnani_ws = await websockets.connect(
                GNANI_STT_WS_URL,
                extra_headers=ws_headers,
                open_timeout=10,
            )

        await websocket.send(json.dumps({
            "type": "gnani_connected",
            "stt_model": GNANI_STT_MODEL,
            "language": lang,
            "message": "Connected to Gnani Prisma v3.0 STT streaming service",
        }))
        logger.info("Connected to Gnani Prisma upstream WebSocket")
    except Exception as e:
        logger.error(f"Failed to connect to Gnani upstream: {e}")
        await websocket.send(json.dumps({
            "type": "error",
            "message": f"Could not connect to Gnani STT: {type(e).__name__}"
        }))
        await websocket.close(4002, "Gnani upstream connection failed")
        return

    accumulated = []

    async def forward_gnani_to_client():
        try:
            async for raw in gnani_ws:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                try:
                    data = json.loads(raw)
                except Exception:
                    data = {"transcript": str(raw)}

                text = (
                    data.get("transcript")
                    or data.get("text")
                    or data.get("data", {}).get("transcript")
                    or ""
                )

                if text:
                    is_final = data.get("is_final", False) or data.get("type") in ("final", "transcript", "speech_final")
                    if is_final:
                        accumulated.append(text)

                    await websocket.send(json.dumps({
                        "type": "gnani_transcript",
                        "partial": not is_final,
                        "text": text,
                        "raw": data,
                    }))
        except asyncio.CancelledError:
            pass
        except Exception as err:
            logger.warning(f"Gnani read loop ended: {err}")

    reader_task = asyncio.create_task(forward_gnani_to_client())

    try:
        async for msg in websocket:
            if isinstance(msg, bytes):
                # Raw audio PCM bytes -> Forward to Gnani
                await gnani_ws.send(msg)
            elif isinstance(msg, str):
                try:
                    ctrl = json.loads(msg)
                    if ctrl.get("action") == "stop" or ctrl.get("type") == "stop":
                        await asyncio.sleep(0.3)
                        final_text = " ".join([t for t in accumulated if t]).strip()
                        await websocket.send(json.dumps({
                            "type": "gnani_complete",
                            "final_transcript": final_text,
                        }))
                    elif ctrl.get("action") == "ping":
                        await websocket.send(json.dumps({"type": "pong"}))
                except Exception as e:
                    logger.warning(f"Error handling control message: {e}")
    except websockets.exceptions.ConnectionClosed:
        logger.info("Client closed connection")
    finally:
        reader_task.cancel()
        await gnani_ws.close()
        logger.info("Gnani WebSocket session closed cleanly")


async def main():
    port = 8001
    logger.info(f"Starting standalone Gnani Prisma v3.0 Streaming WebSocket Server on port {port}...")
    async with websockets.serve(handler, "0.0.0.0", port):
        logger.info(f"Gnani Prisma v3.0 WebSocket Server running at ws://0.0.0.0:{port}/ws/gnani/stream/")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
