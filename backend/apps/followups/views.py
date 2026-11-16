"""Followup views."""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from services.mongodb_service import mongodb_service
from services.followup_service import followup_service

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def followup_list(request):
    status_filter = request.query_params.get("status")
    query = {}
    if status_filter:
        query["status"] = status_filter
    followups = mongodb_service.find_all("followups", query, limit=100)
    
    overdue = followup_service.get_overdue()
    overdue_ids = {f.get("_id") for f in overdue}
    
    for f in followups:
        f["is_overdue"] = f.get("_id") in overdue_ids
    
    return Response({
        "results": followups,
        "count": len(followups),
        "overdue_count": len(overdue),
    })


@api_view(["PATCH"])
@permission_classes([AllowAny])
def followup_update(request, followup_id):
    new_status = request.data.get("status")
    notes = request.data.get("notes", "")

    if new_status == "completed":
        success = followup_service.mark_complete(followup_id, notes)
    else:
        success = mongodb_service.update_one(
            "followups",
            {"_id": followup_id},
            {"$set": {"status": new_status}},
        )

    if not success:
        return Response({"error": "Followup not found"}, status=status.HTTP_404_NOT_FOUND)

    updated = mongodb_service.find_one("followups", {"_id": followup_id})
    return Response(updated or {"message": "Updated"})
