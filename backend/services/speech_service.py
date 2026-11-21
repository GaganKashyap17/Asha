"""
Speech-to-text service for ASHA Voice — Groq Whisper transcription.
"""
import os
import tempfile
import logging
from typing import Union
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

logger = logging.getLogger(__name__)


class SpeechService:
    """Transcribes audio using Groq Whisper API."""

    def __init__(self):
        self._api_key = os.environ.get('GROQ_API_KEY', '')

    def _redact(self, msg: str) -> str:
        if self._api_key and self._api_key in msg:
            return msg.replace(self._api_key, "[REDACTED]")
        return msg

    def transcribe_audio(self, audio_file: Union[bytes, object], language: str = "ta") -> dict:
        """
        Transcribe audio using Groq Whisper API.

        Args:
            audio_file: Django uploaded file object or raw bytes
            language: ISO language code (ta=Tamil, hi=Hindi, en=English)

        Returns:
            dict with 'transcript', 'language', 'provider', 'error'
        """
        if not self._api_key:
            self._api_key = os.environ.get('GROQ_API_KEY', '')

        if not self._api_key or self._api_key == 'your_groq_api_key_here':
            return {
                "transcript": "",
                "language": language,
                "provider": "none",
                "error": "GROQ_API_KEY not configured",
            }

        from groq import Groq
        client = Groq(api_key=self._api_key)

        # Detect audio container format
        suffix = '.webm'
        if isinstance(audio_file, (bytes, bytearray)):
            if audio_file.startswith(b'RIFF'):
                suffix = '.wav'
            elif audio_file.startswith(b'OggS'):
                suffix = '.ogg'
        elif hasattr(audio_file, 'name'):
            ext = os.path.splitext(audio_file.name)[-1]
            if ext:
                suffix = ext

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            if hasattr(audio_file, 'read'):
                tmp.write(audio_file.read())
                if hasattr(audio_file, 'seek'):
                    audio_file.seek(0)
            else:
                tmp.write(audio_file)
            tmp_path = tmp.name

        try:
            with open(tmp_path, 'rb') as f:
                transcription = client.audio.transcriptions.create(
                    model="whisper-large-v3-turbo",
                    file=f,
                    language=language,
                    response_format="json",
                )
            return {
                "transcript": transcription.text,
                "language": language,
                "provider": "groq_whisper",
                "error": None,
            }
        except Exception as e:
            error_msg = self._redact(str(e))
            logger.error(f"Transcription failed: {type(e).__name__} - {error_msg}")
            return {
                "transcript": "",
                "language": language,
                "provider": "groq_whisper",
                "error": f"Transcription failed: {type(e).__name__}",
            }
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# Singleton
speech_service = SpeechService()
