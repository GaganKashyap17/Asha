"""Voice agent views — session management and audio transcription."""
import uuid
import logging
from datetime import datetime, timezone
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from services.speech_service import speech_service
from services.mongodb_service import mongodb_service
from services.danger_detection_service import detect_danger_signs, summarize_danger_results

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([AllowAny])
def create_session(request):
    """Create a new voice session."""
    session = {
        "_id": str(uuid.uuid4()),
        "worker_id": request.data.get("worker_id", "unknown"),
        "language": request.data.get("language", "ta"),
        "visit_type": request.data.get("visit_type", "household"),
        "beneficiary_id": request.data.get("beneficiary_id"),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    mongodb_service.insert("voice_sessions", session)
    return Response({"session_id": session["_id"], "session": session}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def transcribe_audio(request):
    """Transcribe uploaded audio using Groq Whisper."""
    audio_file = request.FILES.get("audio")
    language = request.data.get("language", "ta")

    if not audio_file:
        return Response(
            {"error": "No audio file uploaded. Send as 'audio' in multipart form data."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = speech_service.transcribe_audio(audio_file, language=language)

    # Run danger detection on transcript immediately
    transcript = result.get("transcript", "")
    if transcript:
        visit_type = request.data.get("visit_type", "")
        danger_results = detect_danger_signs(transcript, visit_type)
        danger_summary = summarize_danger_results(danger_results)
        result["danger_detection"] = danger_summary

    return Response(result)
