"""
Gnani Prisma v3.0 Streaming STT Consumer for Django Channels.
Bridges client microphone PCM audio streams to Gnani's WebSocket (wss://api.vachana.ai/stt/v3/stream)
and streams real-time partial & final transcripts back to the client.
"""
import asyncio
import json
import logging
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from services.gnani_service import gnani_service, TIMBRE_VOICES, USER_AGENT

logger = logging.getLogger(__name__)


class GnaniStreamConsumer(AsyncWebsocketConsumer):
    """Real-time audio streaming proxy between browser mic and Gnani Prisma v3.0 STT."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gnani_ws = None
        self.listen_task = None
        self.language = "ta"
        self.accumulated_text = []

    async def connect(self):
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(query_string)
        self.language = params.get("language", ["ta"])[0]

        if not gnani_service.is_configured:
            await self.accept()
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "GNANI_API_KEY is not configured in backend .env",
            }))
            await self.close(code=4001)
            return

        await self.accept()

        # Connect to Gnani Prisma STT WebSocket
        ws_url = gnani_service._stt_ws_url
        headers = gnani_service.get_ws_headers(self.language)

        try:
            import websockets
            try:
                self.gnani_ws = await websockets.connect(
                    ws_url,
                    additional_headers=headers,
                    open_timeout=10,
                )
            except TypeError:
                self.gnani_ws = await websockets.connect(
                    ws_url,
                    extra_headers=headers,
                    open_timeout=10,
                )

            # Start background reader task for Gnani stream
            self.listen_task = asyncio.create_task(self._listen_gnani())

            await self.send(text_data=json.dumps({
                "type": "gnani_connected",
                "stt_model": gnani_service._stt_model,
                "language": self.language,
                "message": "Connected to Gnani Prisma v3.0 STT streaming service",
            }))
            logger.info("Gnani Prisma v3.0 WebSocket connected successfully.")

        except Exception as e:
            logger.error(f"Failed to connect to Gnani STT WebSocket: {type(e).__name__}")
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": f"Could not connect to Gnani STT WebSocket: {type(e).__name__}",
            }))
            await self.close(code=4002)

    async def disconnect(self, close_code):
        if self.listen_task and not self.listen_task.done():
            self.listen_task.cancel()
        if self.gnani_ws:
            try:
                await self.gnani_ws.close()
            except Exception:
                pass
        logger.info(f"GnaniStreamConsumer disconnected (code={close_code})")

    async def receive(self, text_data=None, bytes_data=None):
        # 1. Forward raw audio PCM frames from browser microphone to Gnani STT
        if bytes_data and self.gnani_ws:
            try:
                await self.gnani_ws.send(bytes_data)
            except Exception as e:
                logger.error(f"Error forwarding audio chunk to Gnani: {type(e).__name__}")
            return

        # 2. Control messages from frontend (e.g. stop recording)
        if text_data:
            try:
                msg = json.loads(text_data)
                action = msg.get("action") or msg.get("type")
                if action == "stop":
                    # Give Gnani a moment to return final frames
                    await asyncio.sleep(0.3)
                    final_full = " ".join([t for t in self.accumulated_text if t]).strip()
                    await self.send(text_data=json.dumps({
                        "type": "gnani_complete",
                        "final_transcript": final_full,
                    }))
                elif action == "ping":
                    await self.send(text_data=json.dumps({"type": "pong"}))
            except Exception as e:
                logger.warning(f"Error handling text control message: {e}")

    async def _listen_gnani(self):
        """Asynchronously listens for transcript events from Gnani Prisma STT."""
        try:
            while self.gnani_ws:
                raw_msg = await self.gnani_ws.recv()
                if isinstance(raw_msg, bytes):
                    raw_msg = raw_msg.decode("utf-8", errors="replace")

                try:
                    data = json.loads(raw_msg)
                except Exception:
                    data = {"type": "transcript", "text": str(raw_msg)}

                msg_type = data.get("type", "")
                text = (
                    data.get("transcript")
                    or data.get("text")
                    or data.get("data", {}).get("transcript")
                    or ""
                )

                if text:
                    is_final = data.get("is_final", False) or msg_type in ("final", "transcript", "speech_final")
                    if is_final:
                        self.accumulated_text.append(text)

                    # Stream back to frontend
                    await self.send(text_data=json.dumps({
                        "type": "gnani_transcript",
                        "partial": not is_final,
                        "text": text,
                        "raw": data,
                    }))

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Gnani WebSocket read loop exited: {type(e).__name__}")
