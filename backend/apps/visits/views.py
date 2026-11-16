"""Visit views — CRUD, extraction, correction, confirmation."""
import uuid
import logging
from datetime import datetime, timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from services.mongodb_service import mongodb_service
from services.extraction_service import extraction_service
from services.followup_service import followup_service
from services.danger_detection_service import detect_danger_signs, summarize_danger_results

logger = logging.getLogger(__name__)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def visit_list_create(request):
    if request.method == "GET":
        query = {}
        bene_id = request.query_params.get("beneficiary_id")
        visit_type = request.query_params.get("visit_type")
        confirmation = request.query_params.get("confirmation_status")
        if bene_id:
            query["beneficiary_id"] = bene_id
        if visit_type:
            query["visit_type"] = visit_type
        if confirmation:
            query["confirmation_status"] = confirmation
        visits = mongodb_service.find_all("visits", query, limit=100)
        return Response({"results": visits, "count": len(visits)})

    if request.method == "POST":
        data = request.data.copy()
        data["_id"] = str(uuid.uuid4())
        data["confirmation_status"] = data.get("confirmation_status", "pending")
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        saved = mongodb_service.insert("visits", data)
        return Response(saved, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def extract_visit(request):
    """Extract structured data from transcript using Groq AI + danger detection."""
    transcript = request.data.get("transcript", "")
    visit_type = request.data.get("visit_type", "household")

    if not transcript:
        return Response(
            {"error": "transcript is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = extraction_service.extract_from_transcript(transcript, visit_type)
    
    # Add raw transcript reference
    result["raw_transcript"] = transcript
    
    # Save as pending visit
    result["_id"] = str(uuid.uuid4())
    result["id"] = result["_id"]
    result["created_at"] = datetime.now(timezone.utc).isoformat()
    mongodb_service.insert("visits", result)

    # If danger signs detected, create alert immediately
    if result.get("danger_flag"):
        alert = {
            "visit_id": result["_id"],
            "beneficiary_id": result.get("beneficiary_id"),
            "beneficiary_name": result.get("beneficiary_name"),
            "danger_signs": result.get("danger_signs", []),
            "danger_details": result.get("danger_detection_results", []),
            "referral_status": "pending",
            "resolved": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        mongodb_service.insert("danger_alerts", alert)
        logger.warning(f"DANGER ALERT created for visit {result['_id']}")

    return Response(result)


@api_view(["GET"])
@permission_classes([AllowAny])
def visit_detail(request, visit_id):
    visit = mongodb_service.find_one("visits", {"_id": visit_id})
    if not visit:
        visit = mongodb_service.find_one("visits", {"id": visit_id})
    if not visit:
        return Response({"error": "Visit not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(visit)


@api_view(["PATCH"])
@permission_classes([AllowAny])
def visit_correct(request, visit_id):
    """Correct a specific field in a pending visit."""
    visit = mongodb_service.find_one("visits", {"_id": visit_id})
    if not visit:
        visit = mongodb_service.find_one("visits", {"id": visit_id})
    if not visit:
        return Response({"error": "Visit not found"}, status=status.HTTP_404_NOT_FOUND)

    if visit.get("confirmation_status") == "confirmed":
        return Response(
            {"error": "Cannot correct a confirmed visit. Create a new visit instead."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    field = request.data.get("field")
    value = request.data.get("value")

    if not field:
        return Response(
            {"error": "field name is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    allowed_fields = [
        "beneficiary_name", "beneficiary_id", "visit_type", "visit_date",
        "pregnancy_month", "weight_kg", "anc_completed", "ifa_given",
        "vaccinations", "next_visit_date", "pending_actions",
    ]
    if field not in allowed_fields:
        return Response(
            {"error": f"Field '{field}' cannot be corrected"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Audit the correction
    correction_log = {
        "visit_id": visit_id,
        "field": field,
        "old_value": visit.get(field),
        "new_value": value,
        "corrected_at": datetime.now(timezone.utc).isoformat(),
    }
    mongodb_service.insert("audit_logs", correction_log)

    # Apply correction
    update_key = "_id" if "_id" in visit else "id"
    mongodb_service.update_one("visits", {update_key: visit_id}, {"$set": {field: value}})

    updated = mongodb_service.find_one("visits", {update_key: visit_id})
    return Response(updated)


@api_view(["POST"])
@permission_classes([AllowAny])
def visit_confirm(request, visit_id):
    """Confirm a visit — only after explicit worker confirmation."""
    visit = mongodb_service.find_one("visits", {"_id": visit_id})
    if not visit:
        visit = mongodb_service.find_one("visits", {"id": visit_id})
    if not visit:
        return Response({"error": "Visit not found"}, status=status.HTTP_404_NOT_FOUND)

    if visit.get("confirmation_status") == "confirmed":
        return Response({"message": "Already confirmed", "visit": visit})

    update_key = "_id" if "_id" in visit else "id"
    mongodb_service.update_one(
        "visits",
        {update_key: visit_id},
        {"$set": {
            "confirmation_status": "confirmed",
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    confirmed = mongodb_service.find_one("visits", {update_key: visit_id})

    # Generate followups from confirmed visit
    try:
        followup = followup_service.create_followup_from_visit(confirmed)
    except Exception as e:
        logger.error(f"Followup generation failed: {type(e).__name__}")
        followup = None

    return Response({
        "message": "Visit confirmed and saved",
        "visit": confirmed,
        "followup": followup,
    })
