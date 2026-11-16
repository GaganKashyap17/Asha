"""Analytics dashboard views."""
import logging
from datetime import datetime, timezone, timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from services.mongodb_service import mongodb_service
from services.groq_service import groq_service

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def dashboard_view(request):
    """Aggregate dashboard statistics from MongoDB."""
    stats = mongodb_service.aggregate_dashboard_stats()
    
    # Visit type breakdown
    all_visits = mongodb_service.find_all("visits", limit=500)
    type_counts = {}
    daily_counts = {}
    for v in all_visits:
        vt = v.get("visit_type", "household")
        type_counts[vt] = type_counts.get(vt, 0) + 1
        vdate = v.get("visit_date") or v.get("created_at", "")[:10]
        daily_counts[vdate] = daily_counts.get(vdate, 0) + 1

    stats["visit_type_breakdown"] = type_counts
    stats["daily_visit_counts"] = daily_counts

    # Recent visits
    recent = sorted(all_visits, key=lambda x: x.get("created_at", ""), reverse=True)[:10]
    stats["recent_visits"] = recent

    # Followup stats
    all_followups = mongodb_service.find_all("followups", limit=500)
    pending_fu = [f for f in all_followups if f.get("status") == "pending"]
    completed_fu = [f for f in all_followups if f.get("status") == "completed"]
    stats["followup_total"] = len(all_followups)
    stats["followup_completed"] = len(completed_fu)
    stats["followup_pending"] = len(pending_fu)
    stats["upcoming_followups"] = sorted(
        pending_fu, key=lambda x: x.get("due_date", "9999")
    )[:5]

    # Active danger alerts
    active_alerts = mongodb_service.find_all("danger_alerts", {"resolved": False})
    stats["active_alerts"] = active_alerts
    stats["active_danger_alerts"] = len(active_alerts)

    # Weekly data
    today = datetime.now(timezone.utc).date()
    weekly = []
    for i in range(6, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        weekly.append({"date": d, "count": daily_counts.get(d, 0)})
    stats["weekly_visits"] = weekly

    return Response(stats)


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """API health check — includes Groq and MongoDB status."""
    groq_status = groq_service.validate_connection()
    mongo_status = mongodb_service.status()
    return Response({
        "status": "healthy",
        "groq": {
            "connected": groq_status.get("success", False),
            "model": groq_status.get("model"),
            "latency_ms": groq_status.get("latency_ms"),
            "error": groq_status.get("error"),
        },
        "mongodb": mongo_status,
    })
