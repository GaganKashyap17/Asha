"""
Text-to-Speech service stub for ASHA Voice.
Currently returns placeholder; real implementation uses gTTS or cloud TTS.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TTSService:
    """Convert text to speech audio bytes."""

    SUPPORTED_LANGUAGES = {
        "ta": "Tamil",
        "hi": "Hindi",
        "en": "English",
        "te": "Telugu",
        "kn": "Kannada",
        "ml": "Malayalam",
    }

    def synthesize(self, text: str, language: str = "ta") -> dict:
        """
        Convert text to speech.

        Returns:
            dict with 'audio_bytes', 'format', 'language', 'error'
        """
        logger.info(f"TTS synthesis requested: lang={language}, chars={len(text)}")
        # Stub — real implementation uses gTTS, Azure TTS, or Google TTS
        return {
            "audio_bytes": None,
            "format": "mp3",
            "language": language,
            "language_name": self.SUPPORTED_LANGUAGES.get(language, language),
            "error": "TTS not configured — stub response",
        }

    def get_referral_audio(self, message: str, language: str = "ta") -> dict:
        """Synthesize a referral/danger alert message."""
        return self.synthesize(message, language)


# Singleton
tts_service = TTSService()
