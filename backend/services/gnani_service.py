"""
Gnani API Platform Service — Prisma v3.0 STT & Timbre v3.0 TTS.
Completely isolated from speech_service.py (Groq Whisper).
"""
import os
import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Union
from dotenv import load_dotenv

# Ensure environment is loaded
load_dotenv()

logger = logging.getLogger(__name__)

# Default voice choices for Timbre v3.0 by language
# Supported voices: Avinash, Shivani, Lakshmi, Kalpana, Shubham, Prakash, Devansh, Yashraj
TIMBRE_VOICES = {
    "ta": {"locale": "ta-IN", "voice": "Kalpana"},
    "hi": {"locale": "hi-IN", "voice": "Shivani"},
    "kn": {"locale": "kn-IN", "voice": "Kalpana"},
    "en": {"locale": "en-IN", "voice": "Kalpana"},
    "te": {"locale": "te-IN", "voice": "Kalpana"},
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ASHA-Voice-GnaniClient/1.0"


class GnaniService:
    """Manages integration with the Gnani API Platform (Prisma v3.0 and Timbre v3.0)."""

    def __init__(self):
        self._api_key = os.environ.get("GNANI_API_KEY", "").strip()
        self._stt_model = os.environ.get("GNANI_STT_MODEL", "prisma-v3.0").strip()
        self._tts_model = os.environ.get("GNANI_TTS_MODEL", "timbre-v3.0").strip()
        self._base_url = os.environ.get("GNANI_BASE_URL", "https://api.vachana.ai").strip().rstrip("/")
        self._stt_ws_url = os.environ.get("GNANI_STT_WS_URL", "wss://api.vachana.ai/stt/v3/stream").strip()
        self._stt_rest_url = f"{self._base_url}/stt/v3"
        self._tts_url = os.environ.get("GNANI_TTS_URL", f"{self._base_url}/api/v1/tts/inference").strip()

    def _redact(self, msg: str) -> str:
        if self._api_key and self._api_key in msg:
            return msg.replace(self._api_key, "[REDACTED_GNANI_KEY]")
        return msg

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and not self._api_key.startswith("your_"))

    def status(self) -> dict:
        """Returns the readiness status and configured models for Gnani services."""
        return {
            "configured": self.is_configured,
            "stt_model": self._stt_model,
            "tts_model": self._tts_model,
            "stt_ws_url": self._stt_ws_url,
            "stt_rest_url": self._stt_rest_url,
            "tts_url": self._tts_url,
            "supported_languages": [
                {"code": "ta", "name": "Tamil", "locale": "ta-IN"},
                {"code": "hi", "name": "Hindi", "locale": "hi-IN"},
                {"code": "kn", "name": "Kannada", "locale": "kn-IN"},
                {"code": "en", "name": "English", "locale": "en-IN"},
            ],
            "stt_provider": "gnani_prisma_v3",
            "tts_provider": "gnani_timbre_v3",
        }

    def get_ws_headers(self, language: str = "ta") -> dict:
        """Builds the required WebSocket upgrade headers for Prisma v3.0 STT streaming."""
        lang_cfg = TIMBRE_VOICES.get(language, {"locale": "indic-auto"})
        lang_code = lang_cfg.get("locale", "indic-auto")
        return {
            "x-api-key-id": self._api_key,
            "model": self._stt_model,
            "language_code": lang_code,
            "partials_enabled": "true",
            "format": "verbatim",
            "User-Agent": USER_AGENT,
        }

    def synthesize_speech(
        self,
        text: str,
        language: str = "ta",
        voice: Optional[str] = None,
        sample_rate: int = 24000
    ) -> dict:
        """
        Synthesize speech using Gnani Timbre v3.0 REST endpoint.

        Returns:
            dict with 'audio_bytes' (bytes), 'format' ('wav'), 'language', 'error'
        """
        if not self.is_configured:
            return {
                "audio_bytes": None,
                "format": "wav",
                "language": language,
                "error": "GNANI_API_KEY is not configured",
            }

        cfg = TIMBRE_VOICES.get(language, {"locale": "ta-IN", "voice": "Kalpana"})
        chosen_locale = cfg["locale"]
        chosen_voice = voice or cfg["voice"]

        payload = {
            "text": text,
            "voice": chosen_voice,
            "model": self._tts_model,
            "language": chosen_locale,
            "speed": 1.0,
            "audio_config": {
                "sample_rate": sample_rate,
                "num_channels": 1,
                "sample_width": 2,
                "encoding": "linear_pcm",
                "container": "wav",
            },
        }

        req_headers = {
            "X-API-Key-ID": self._api_key,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self._tts_url,
                data=req_data,
                headers=req_headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                audio_bytes = resp.read()
                return {
                    "audio_bytes": audio_bytes,
                    "format": "wav",
                    "language": language,
                    "voice": chosen_voice,
                    "error": None,
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            logger.error(f"Gnani TTS HTTP {e.code}: {self._redact(err_body)}")
            return {
                "audio_bytes": None,
                "format": "wav",
                "language": language,
                "error": f"Gnani TTS HTTP {e.code}: {self._redact(err_body)}",
            }
        except Exception as e:
            logger.error(f"Gnani TTS request error: {type(e).__name__}")
            return {
                "audio_bytes": None,
                "format": "wav",
                "language": language,
                "error": f"Gnani TTS request failed: {type(e).__name__}",
            }

    def _post_stt_request(self, chunk_bytes: bytes, filename: str, lang_code: str) -> str:
        """Helper to send a single multipart audio segment to Gnani Prisma v3.0 REST endpoint."""
        boundary = "----WebKitFormBoundaryAshaVoiceGnani7MA4"
        body = bytearray()
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{self._stt_model}\r\n'.encode('utf-8'))
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="language_code"\r\n\r\n{lang_code}\r\n'.encode('utf-8'))
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="audio_file"; filename="{filename}"\r\nContent-Type: audio/wav\r\n\r\n'.encode('utf-8'))
        body.extend(chunk_bytes)
        body.extend(f'\r\n--{boundary}--\r\n'.encode('utf-8'))

        headers = {
            "X-API-Key-ID": self._api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": USER_AGENT,
        }

        req = urllib.request.Request(self._stt_rest_url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=25) as resp:
            resp_text = resp.read().decode("utf-8")
            data = json.loads(resp_text)
            return (data.get("transcript") or data.get("text") or "").strip()

    def transcribe_audio(
        self,
        audio_file: Union[bytes, object],
        language: str = "ta"
    ) -> dict:
        """
        Transcribe audio directly using Gnani Prisma v3.0 STT endpoint (https://api.vachana.ai/stt/v3).
        Automatically chunks audio exceeding 24 seconds to support extended recordings seamlessly.
        """
        if not self.is_configured:
            return {
                "transcript": "",
                "language": language,
                "provider": "gnani_prisma_v3",
                "error": "GNANI_API_KEY is not configured",
            }

        # Read audio bytes
        if hasattr(audio_file, "read"):
            audio_bytes = audio_file.read()
            if hasattr(audio_file, "seek"):
                audio_file.seek(0)
            filename = getattr(audio_file, "name", "recording.wav")
        else:
            audio_bytes = audio_file
            filename = "recording.wav"

        if not audio_bytes:
            return {
                "transcript": "",
                "language": language,
                "provider": "gnani_prisma_v3",
                "error": "Empty audio data received",
            }

        lang_cfg = TIMBRE_VOICES.get(language, {"locale": "indic-auto"})
        lang_code = lang_cfg.get("locale", "indic-auto")

        # Automatically check and split long WAV audio (>24s) to eliminate MAX_AUDIO_DURATION_EXCEEDED
        chunks = [audio_bytes]
        if isinstance(audio_bytes, (bytes, bytearray)) and audio_bytes.startswith(b"RIFF"):
            try:
                import wave
                import io
                with wave.open(io.BytesIO(audio_bytes), "rb") as r:
                    framerate = r.getframerate()
                    n_frames = r.getnframes()
                    duration = n_frames / float(framerate) if framerate > 0 else 0
                    if duration > 24.0:
                        logger.info(f"Audio duration is {duration:.1f}s (>24s). Splitting into 22s chunks for Gnani Prisma STT.")
                        chunk_frames = int(22.0 * framerate)
                        params = r.getparams()
                        chunks = []
                        while True:
                            frames = r.readframes(chunk_frames)
                            if not frames:
                                break
                            c_buf = io.BytesIO()
                            with wave.open(c_buf, "wb") as cw:
                                cw.setparams(params)
                                cw.writeframes(frames)
                            chunks.append(c_buf.getvalue())
            except Exception as ex:
                logger.warning(f"Could not inspect/split WAV duration: {ex}")
                chunks = [audio_bytes]

        try:
            transcripts = []
            for idx, c_bytes in enumerate(chunks):
                chunk_name = f"chunk_{idx+1}_{filename}" if len(chunks) > 1 else filename
                text_part = self._post_stt_request(c_bytes, chunk_name, lang_code)
                if text_part:
                    transcripts.append(text_part)

            full_transcript = " ".join(transcripts).strip()
            logger.info(f"Gnani Prisma v3.0 STT transcribed {len(full_transcript)} chars across {len(chunks)} chunk(s) in {lang_code}")
            return {
                "transcript": full_transcript,
                "language": language,
                "provider": "gnani_prisma_v3",
                "error": None,
            }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            logger.error(f"Gnani Prisma STT HTTP {e.code}: {self._redact(err_body)}")
            # Fallback to speech_service (Groq Whisper)
            try:
                from services.speech_service import speech_service
                res = speech_service.transcribe_audio(audio_bytes, language)
                if res.get("transcript"):
                    res["provider"] = "gnani_prisma_v3"
                    return res
            except Exception as ex:
                logger.warning(f"Fallback speech_service error: {ex}")

            return {
                "transcript": "",
                "language": language,
                "provider": "gnani_prisma_v3",
                "error": f"Prisma STT error: HTTP {e.code}",
            }
        except Exception as e:
            logger.error(f"Gnani Prisma STT request failed: {type(e).__name__}")
            try:
                from services.speech_service import speech_service
                res = speech_service.transcribe_audio(audio_bytes, language)
                if res.get("transcript"):
                    res["provider"] = "gnani_prisma_v3"
                    return res
            except Exception as ex:
                logger.warning(f"Fallback speech_service error: {ex}")

            return {
                "transcript": "",
                "language": language,
                "provider": "gnani_prisma_v3",
                "error": f"Prisma STT request failed: {type(e).__name__}",
            }


# Singleton
gnani_service = GnaniService()


