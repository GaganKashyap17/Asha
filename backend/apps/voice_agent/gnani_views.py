"""
Gnani API Platform Views — Status, Timbre v3.0 TTS, and Translation endpoints.
Isolated from speech_service.py and existing voice endpoints.
"""
import logging
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from services.gnani_service import gnani_service
from services.groq_service import groq_service

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def gnani_status(request):
    """Check Gnani API Platform configuration and model readiness."""
    return Response(gnani_service.status())


@api_view(["POST"])
@permission_classes([AllowAny])
def gnani_tts(request):
    """
    Synthesize text into speech using Gnani Timbre v3.0.
    Returns binary audio/wav.
    """
    data = request.data
    text = (data.get("text") or "").strip()
    language = data.get("language", "ta").strip()
    voice = data.get("voice")

    if not text:
        return Response(
            {"error": "Text is required for TTS synthesis"},
            status=status.HTTP_400_BAD_REQUEST
        )

    res = gnani_service.synthesize_speech(text=text, language=language, voice=voice)
    if res.get("error") or not res.get("audio_bytes"):
        logger.info(f"Gnani Timbre TTS unavailable ({res.get('error')}); returning fallback flag")
        return Response(
            {
                "error": res.get("error", "TTS synthesis unavailable"),
                "fallback_to_browser": True,
            },
            status=status.HTTP_200_OK
        )

    response = HttpResponse(res["audio_bytes"], content_type="audio/wav")
    response["Content-Disposition"] = 'inline; filename="gnani_guidance.wav"'
    return response


@api_view(["POST"])
@permission_classes([AllowAny])
def gnani_translate(request):
    """
    Translate vernacular transcript into English using Groq LLM
    (for review and record consistency).
    """
    data = request.data
    text = (data.get("text") or "").strip()
    source_language = data.get("source_language", "ta")

    if not text:
        return Response(
            {"error": "Text is required for translation"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        translated = groq_service.translate_to_english(text, source_language)
        return Response({
            "original_text": text,
            "translated_text": translated.strip(),
            "source_language": source_language,
        })
    except Exception as e:
        logger.warning(f"Translation failed: {e}")
        return Response({
            "original_text": text,
            "translated_text": text,
            "error": "Translation service unavailable",
        })


@api_view(["POST"])
@permission_classes([AllowAny])
def gnani_transcribe(request):
    """
    Transcribe audio file via Gnani Prisma v3.0 pipeline.
    Accepts multipart/form-data with 'audio_file' and optional 'language'.
    """
    audio_file = request.FILES.get("audio_file") or request.FILES.get("audio")
    language = request.data.get("language", "ta").strip()

    if not audio_file:
        return Response(
            {"error": "No audio file provided"},
            status=status.HTTP_400_BAD_REQUEST
        )

    result = gnani_service.transcribe_audio(audio_file, language=language)
    if result.get("error") and not result.get("transcript"):
        return Response(
            {"error": result["error"]},
            status=status.HTTP_502_BAD_GATEWAY
        )

    return Response({
        "transcript": result.get("transcript", ""),
        "language": result.get("language", language),
        "provider": result.get("provider", "gnani_prisma_v3"),
    })


