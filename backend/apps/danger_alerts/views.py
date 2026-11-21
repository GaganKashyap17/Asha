"""Danger alert views."""
import logging
import uuid
from datetime import datetime, timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from services.mongodb_service import mongodb_service

logger = logging.getLogger(__name__)


def _enrich_alert_with_beneficiary_details(alert: dict) -> dict:
    """Ensure every alert document has full beneficiary details populated."""
    b_id = alert.get("beneficiary_id")
    b_name = alert.get("beneficiary_name")
    phone = alert.get("phone") or alert.get("mobile_number")
    village = alert.get("village")
    household = alert.get("household")

    # If any crucial details are missing, look up the beneficiary in the beneficiaries collection
    bene = None
    if b_id:
        bene = mongodb_service.find_one("beneficiaries", {"beneficiary_id": b_id})
    if not bene and b_name:
        bene = mongodb_service.find_one("beneficiaries", {"name": {"$regex": f"^{b_name}$", "$options": "i"}})
    if not bene and phone:
        bene = mongodb_service.find_one("beneficiaries", {"phone": phone})

    if bene:
        alert["beneficiary_id"] = alert.get("beneficiary_id") or bene.get("beneficiary_id")
        alert["beneficiary_name"] = alert.get("beneficiary_name") or bene.get("name")
        alert["phone"] = alert.get("phone") or bene.get("phone")
        alert["village"] = alert.get("village") or bene.get("village")
        alert["household"] = alert.get("household") or bene.get("household")
        alert["pregnancy_status"] = alert.get("pregnancy_status") or bene.get("pregnancy_status")

    # If visit_id is present and visit details missing, populate from visits collection
    v_id = alert.get("visit_id")
    if v_id and (not alert.get("danger_signs") or not alert.get("visit_type")):
        visit = mongodb_service.find_one("visits", {"_id": v_id}) or mongodb_service.find_one("visits", {"id": v_id})
        if visit:
            alert["visit_type"] = alert.get("visit_type") or visit.get("visit_type")
            alert["danger_signs"] = alert.get("danger_signs") or visit.get("danger_signs", [])
            alert["beneficiary_name"] = alert.get("beneficiary_name") or visit.get("beneficiary_name")
            alert["beneficiary_id"] = alert.get("beneficiary_id") or visit.get("beneficiary_id")

    return alert


def _sync_danger_visits_to_alerts():
    """
    Scans the visits collection for any visits flagged as emergency (danger_flag=True),
    and ensures an emergency alert exists in danger_alerts with all beneficiary details.
    """
    try:
        danger_visits = mongodb_service.find_all("visits", {"danger_flag": True}, limit=200)
        existing_alerts = mongodb_service.find_all("danger_alerts", {}, limit=500)
        
        linked_visit_ids = {str(a.get("visit_id")) for a in existing_alerts if a.get("visit_id")}
        linked_draft_ids = {str(a.get("draft_id")) for a in existing_alerts if a.get("draft_id")}

        for v in danger_visits:
            v_id = str(v.get("_id") or v.get("id") or "")
            d_id = str(v.get("draft_id") or "")

            if (v_id and v_id in linked_visit_ids) or (d_id and d_id in linked_draft_ids):
                continue

            # Need to create emergency alert for this danger visit
            b_id = v.get("beneficiary_id")
            b_name = v.get("beneficiary_name")
            bene = None
            if b_id:
                bene = mongodb_service.find_one("beneficiaries", {"beneficiary_id": b_id})
            if not bene and b_name:
                bene = mongodb_service.find_one("beneficiaries", {"name": {"$regex": f"^{b_name}$", "$options": "i"}})

            new_alert = {
                "_id": str(uuid.uuid4()),
                "visit_id": v_id,
                "draft_id": d_id or None,
                "beneficiary_id": b_id or (bene.get("beneficiary_id") if bene else None),
                "beneficiary_name": b_name or (bene.get("name") if bene else "Citizen Beneficiary"),
                "phone": (bene.get("phone") if bene else None) or v.get("phone"),
                "village": (bene.get("village") if bene else None) or v.get("village"),
                "household": (bene.get("household") if bene else None) or v.get("household"),
                "visit_type": v.get("visit_type") or v.get("revisit_category") or "Patient Revisit",
                "danger_signs": v.get("danger_signs") or ["Emergency Clinical Observation Flagged"],
                "danger_details": v.get("danger_details") or v.get("danger_detection_results") or [],
                "referral_status": v.get("referral_status", "pending"),
                "resolved": v.get("resolved", False),
                "created_at": v.get("created_at") or datetime.now(timezone.utc).isoformat(),
            }
            mongodb_service.insert("danger_alerts", new_alert)
            linked_visit_ids.add(v_id)
            logger.info(f"Auto-synced danger visit {v_id} to danger_alerts")
    except Exception as e:
        logger.error(f"Error syncing danger visits to alerts: {e}")


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def alert_list_create(request):
    if request.method == "GET":
        # 1. First sync any danger visits from visit history
        _sync_danger_visits_to_alerts()

        resolved_param = request.query_params.get("resolved")
        query = {}
        if resolved_param is not None:
            is_resolved = resolved_param.lower() == "true"
            if is_resolved:
                query["resolved"] = True
            else:
                query["resolved"] = {"$ne": True}

        raw_alerts = mongodb_service.find_all("danger_alerts", query, limit=100)

        # 2. Enrich all alerts with full beneficiary details
        enriched = [_enrich_alert_with_beneficiary_details(a) for a in raw_alerts]

        # Sort with newest alerts first
        enriched.sort(key=lambda a: a.get("created_at") or "", reverse=True)

        return Response({"results": enriched, "count": len(enriched)})

    if request.method == "POST":
        data = request.data.copy()
        if "_id" not in data:
            data["_id"] = str(uuid.uuid4())
        data["resolved"] = data.get("resolved", False)
        data["referral_status"] = data.get("referral_status", "pending")
        data["created_at"] = data.get("created_at") or datetime.now(timezone.utc).isoformat()
        
        # Enrich with full beneficiary details before saving
        data = _enrich_alert_with_beneficiary_details(data)
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

    # Try updating by _id or visit_id
    success = mongodb_service.update_one("danger_alerts", {"_id": alert_id}, {"$set": update_data})
    if not success:
        success = mongodb_service.update_one("danger_alerts", {"visit_id": alert_id}, {"$set": update_data})

    if not success:
        return Response({"error": "Alert not found"}, status=status.HTTP_404_NOT_FOUND)

    updated = mongodb_service.find_one("danger_alerts", {"_id": alert_id}) or mongodb_service.find_one("danger_alerts", {"visit_id": alert_id})
    if updated:
        updated = _enrich_alert_with_beneficiary_details(updated)

    return Response(updated or {"message": "Updated"})
