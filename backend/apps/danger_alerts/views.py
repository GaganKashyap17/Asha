"""Danger alert views."""
import logging
from datetime import datetime, timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from services.mongodb_service import mongodb_service

logger = logging.getLogger(__name__)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def alert_list_create(request):
    if request.method == "GET":
        resolved = request.query_params.get("resolved")
        query = {}
        if resolved is not None:
            query["resolved"] = resolved.lower() == "true"
        alerts = mongodb_service.find_all("danger_alerts", query, limit=100)
        return Response({"results": alerts, "count": len(alerts)})

    if request.method == "POST":
        data = request.data.copy()
        data["resolved"] = False
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        saved = mongodb_service.insert("danger_alerts", data)
        return Response(saved, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes([AllowAny])
def alert_update(request, alert_id):
    update_data = {}
    if "referral_status" in request.data:
        update_data["referral_status"] = request.data["referral_status"]
    if "resolved" in request.data:
        update_data["resolved"] = request.data["resolved"]
        if update_data["resolved"]:
            update_data["resolved_at"] = datetime.now(timezone.utc).isoformat()

    if not update_data:
        return Response(
            {"error": "No update fields provided"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    success = mongodb_service.update_one("danger_alerts", {"_id": alert_id}, {"$set": update_data})
    if not success:
        return Response({"error": "Alert not found"}, status=status.HTTP_404_NOT_FOUND)

    updated = mongodb_service.find_one("danger_alerts", {"_id": alert_id})
    return Response(updated or {"message": "Updated"})
