"""
IVR Reminder Service for ASHA Voice.
Unified backend logic for managing beneficiary reminder calls,
tracking call records in MongoDB, and updating follow-up schedules.
"""
import uuid
import random
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional

from services.mongodb_service import mongodb_service
from services.followup_service import followup_service

logger = logging.getLogger(__name__)

TOMORROW_DATE = "2026-11-23"

CALL_OUTCOMES = [
    ("completed", 0.70),
    ("busy", 0.15),
    ("no_answer", 0.10),
    ("failed", 0.05),
]

OUTCOME_MESSAGES = {
    "completed": "Reminder played successfully",
    "busy": "Line was busy — no connection established",
    "no_answer": "No answer after multiple rings",
    "failed": "Call could not be connected",
}

REMINDER_TEMPLATES = {
    "en": "Hello! {name_prefix}This is a reminder from your local ASHA worker. Your ASHA worker is scheduled to visit you on {date} for {visit_type}. Please be available at home. Thank you.",
    "hi": "नमस्ते! {name_prefix}यह आपके स्थानीय ASHA कार्यकर्ता की ओर से एक अनुस्मारक है। आपकी ASHA कार्यकर्ता {date} को {visit_type} के लिए आपसे मिलने आएंगी। कृपया घर पर उपलब्ध रहें। धन्यवाद।",
    "ta": "வணக்கம்! {name_prefix}இது உங்கள் உள்ளூர் ASHA பணியாளரிடமிருந்து ஒரு நினைவூட்டல். உங்கள் ASHA பணியாளர் {date} அன்று {visit_type} க்காக உங்களை சந்திக்க வருவார்கள். தயவுசெய்து வீட்டில் இருங்கள். நன்றி.",
    "kn": "ನಮಸ್ಕಾರ! {name_prefix}ಇದು ನಿಮ್ಮ ಸ್ಥಳೀಯ ASHA ಕಾರ್ಯಕರ್ತೆಯಿಂದ ಒಂದು ನೆನಪೋಲೆ. ನಿಮ್ಮ ASHA ಕಾರ್ಯಕರ್ತೆ {date} ರಂದು {visit_type} ಗಾಗಿ ನಿಮ್ಮನ್ನು ಭೇಟಿ ಮಾಡಲು ಬರುತ್ತಾರೆ. ದಯವಿಟ್ಟು ಮನೆಯಲ್ಲಿ ಇರಿ. ಧನ್ಯವಾದ.",
}

NAME_PREFIX_TEMPLATES = {
    "en": "{name}, ",
    "hi": "{name} जी, ",
    "ta": "{name} அவர்களே, ",
    "kn": "{name} ಅವರೇ, ",
}

DEFAULT_BENEFICIARIES = [
    {
        "_id": "PREG-2026-000001",
        "beneficiary_id": "PREG-2026-000001",
        "beneficiary_name": "Priya Rajan",
        "mobile_number": "7339223026",
        "visit_date": TOMORROW_DATE,
        "visit_type": "ANC Check-up / Maternal Vitals",
        "priority": "high",
        "notes": "Scheduled for ANC 3rd trimester revisit tomorrow — BP and Hb check",
        "village": "Gandhi Nagar",
        "household": "H-12",
    },
    {
        "_id": "PREG-2026-000002",
        "beneficiary_id": "PREG-2026-000002",
        "beneficiary_name": "Ananya Sharma",
        "mobile_number": "8056413568",
        "visit_date": TOMORROW_DATE,
        "visit_type": "High Risk ANC Follow-up",
        "priority": "emergency",
        "notes": "Scheduled for pre-eclampsia follow-up revisit tomorrow — blood pressure monitoring",
        "village": "Anna Nagar",
        "household": "H-05",
    },
    {
        "_id": "IMM-2026-000001",
        "beneficiary_id": "IMM-2026-000001",
        "beneficiary_name": "Kavitha Murugan",
        "mobile_number": "9876543210",
        "visit_date": TOMORROW_DATE,
        "visit_type": "Child Immunization Revisit",
        "priority": "high",
        "notes": "Child vaccination due tomorrow — Pentavalent-1 and OPV booster dose",
        "village": "Subhash Nagar",
        "household": "H-23",
    },
    {
        "_id": "NEWB-2026-000001",
        "beneficiary_id": "NEWB-2026-000001",
        "beneficiary_name": "Sumathi Devi",
        "mobile_number": "8765432109",
        "visit_date": TOMORROW_DATE,
        "visit_type": "Newborn Postnatal Revisit",
        "priority": "medium",
        "notes": "Scheduled for 14-day newborn health, breastfeeding & temperature revisit tomorrow",
        "village": "Nehru Street",
        "household": "H-18",
    },
    {
        "_id": "PREG-2026-000003",
        "beneficiary_id": "PREG-2026-000003",
        "beneficiary_name": "Meena Krishnan",
        "mobile_number": "7654321098",
        "visit_date": TOMORROW_DATE,
        "visit_type": "Maternal Nutrition & IFA Revisit",
        "priority": "medium",
        "notes": "Scheduled for gestational blood sugar review and IFA tablet replenishment revisit tomorrow",
        "village": "Ramanathapuram",
        "household": "H-09",
    },
]


class IVRService:
    """Service to handle IVR call simulation, persistence, and scheduling."""

    def get_beneficiaries(self, tomorrow_only: bool = True) -> List[Dict[str, Any]]:
        """
        Merge registered beneficiaries and pending follow-ups from MongoDB.
        Ensures phone numbers and scheduled revisit dates are accurately retrieved.
        """
        try:
            beneficiaries = mongodb_service.find_all("beneficiaries", limit=200)
            followups = mongodb_service.find_all("followups", {"status": "pending"}, limit=200)
        except Exception as e:
            logger.error(f"Error reading beneficiaries or followups from DB: {e}")
            beneficiaries = []
            followups = []

        followup_map: Dict[str, Dict[str, Any]] = {}
        for f in followups:
            bid = f.get("beneficiary_id")
            if bid:
                followup_map[bid] = f
            bname = (f.get("beneficiary_name") or "").lower()
            if bname:
                followup_map[bname] = f
            phone = f.get("mobile_number") or f.get("phone")
            if phone:
                followup_map[phone] = f

        combined: Dict[str, Dict[str, Any]] = {}

        # 1. Seed defaults
        for dbene in DEFAULT_BENEFICIARIES:
            key = dbene.get("beneficiary_id") or dbene.get("beneficiary_name")
            combined[key] = dict(dbene)

        # 2. Merge database records
        for b in beneficiaries:
            if b.get("is_deleted"):
                continue
            bid = b.get("beneficiary_id") or str(b.get("_id", ""))
            name = b.get("name") or "Citizen Beneficiary"
            key = bid or name

            matched_fu = (
                followup_map.get(bid)
                or followup_map.get(name.lower())
                or followup_map.get(b.get("phone"))
            )

            phone = b.get("phone") or (matched_fu.get("mobile_number") if matched_fu else None) or "8056413568"
            visit_date = (
                (matched_fu.get("due_date") if matched_fu else None)
                or b.get("next_visit_date")
                or TOMORROW_DATE
            )

            category = b.get("pregnancy_status", "")
            default_visit_type = (
                "ANC Check-up / Maternal Vitals"
                if category == "pregnant"
                else "Child Immunization Revisit"
                if category == "child"
                else "Newborn Postnatal Revisit"
                if category == "newborn"
                else "Health Revisit"
            )

            visit_type = (
                (matched_fu.get("visit_type") if matched_fu else None)
                or b.get("visit_type")
                or default_visit_type
            )

            priority = (
                (matched_fu.get("priority") if matched_fu else None)
                or b.get("priority")
                or ("high" if category == "pregnant" else "medium")
            )

            notes = (
                (matched_fu.get("notes") if matched_fu else None)
                or b.get("notes")
                or f"Scheduled revisit for {b.get('village', 'village')} ({b.get('household', 'household')})"
            )

            record = {
                "_id": bid,
                "beneficiary_id": bid,
                "beneficiary_name": name,
                "mobile_number": phone,
                "visit_date": visit_date,
                "visit_type": visit_type,
                "priority": priority,
                "notes": notes,
                "village": b.get("village", ""),
                "household": b.get("household", ""),
            }
            combined[key] = record

        results = list(combined.values())

        if tomorrow_only:
            tomorrow_list = [r for r in results if r.get("visit_date") == TOMORROW_DATE]
            return tomorrow_list if tomorrow_list else DEFAULT_BENEFICIARIES

        return results

    def initiate_call(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate placing an IVR reminder call to a beneficiary.
        Stores the resulting call record in MongoDB ('ivr_calls' collection).
        """
        beneficiary_name = validated_data.get("beneficiary_name", "Citizen Beneficiary")
        mobile_number = validated_data.get("mobile_number", "")
        visit_date = validated_data.get("visit_date", TOMORROW_DATE)
        visit_type = validated_data.get("visit_type", "Upcoming Revisit")
        language = validated_data.get("language", "en")
        followup_id = validated_data.get("followup_id", "")
        beneficiary_id = validated_data.get("beneficiary_id", "")

        # ── 1. Check duplicate within 24 hours ────────────────────────
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        existing_calls = mongodb_service.find_all("ivr_calls", limit=200)

        for call in existing_calls:
            matches_followup = followup_id and call.get("followup_id") == followup_id
            matches_mobile = call.get("mobile_number") == mobile_number
            if (matches_followup or matches_mobile) and call.get("status") == "completed":
                try:
                    init_time_str = call.get("initiated_at", "")
                    init_time = datetime.fromisoformat(init_time_str.replace("Z", "+00:00"))
                    if init_time > cutoff:
                        return {
                            "is_duplicate": True,
                            "error": "duplicate_call",
                            "message": "An IVR reminder was already completed for this beneficiary within the last 24 hours.",
                            "existing_call": call,
                        }
                except Exception:
                    pass

        # ── 2. Determine Call Outcome ─────────────────────────────────
        r = random.random()
        cumulative = 0.0
        outcome_status = "completed"
        for stat, prob in CALL_OUTCOMES:
            cumulative += prob
            if r <= cumulative:
                outcome_status = stat
                break

        # ── 3. Build Multilingual Reminder Message ────────────────────
        prefix_template = NAME_PREFIX_TEMPLATES.get(language, NAME_PREFIX_TEMPLATES["en"])
        name_prefix = prefix_template.format(name=beneficiary_name) if beneficiary_name and beneficiary_name != "Citizen Beneficiary" else ""

        msg_template = REMINDER_TEMPLATES.get(language, REMINDER_TEMPLATES["en"])
        reminder_message = msg_template.format(
            name_prefix=name_prefix,
            date=visit_date,
            visit_type=visit_type,
        )

        duration = random.randint(20, 45) if outcome_status == "completed" else 0
        now_iso = datetime.now(timezone.utc).isoformat()

        call_record = {
            "call_id": f"ivr-{uuid.uuid4().hex[:10]}",
            "beneficiary_id": beneficiary_id,
            "beneficiary_name": beneficiary_name,
            "mobile_number": mobile_number,
            "visit_date": visit_date,
            "visit_type": visit_type,
            "language": language,
            "reminder_message": reminder_message,
            "status": outcome_status,
            "outcome": OUTCOME_MESSAGES.get(outcome_status, "Call finished"),
            "initiated_at": now_iso,
            "completed_at": now_iso if outcome_status in ["completed", "busy", "no_answer", "failed"] else None,
            "duration_seconds": duration,
            "followup_id": followup_id,
            "is_demo": True,
        }

        # ── 4. Save to MongoDB ────────────────────────────────────────
        saved_doc = mongodb_service.insert("ivr_calls", call_record)
        if saved_doc and "_id" in saved_doc:
            call_record["_id"] = str(saved_doc["_id"])

        logger.info(
            f"[IVR Call] {call_record['call_id']} to {mobile_number[:5]}XXXXX "
            f"for {beneficiary_name} — status: {outcome_status}"
        )

        # ── 5. Auto-update followup if completed ──────────────────────
        if outcome_status == "completed" and followup_id:
            try:
                followup_service.mark_complete(
                    followup_id,
                    notes=f"Reminder call confirmed via IVR on {now_iso[:10]} ({language.upper()})"
                )
            except Exception as e:
                logger.warning(f"Could not auto-mark followup {followup_id} complete: {e}")

        return {
            "is_duplicate": False,
            "call": call_record,
            "demo": True,
            "note": "SIMULATED — No actual phone call was placed. Telephony engine in demo mode.",
            "disclaimer": "This is a prototype demonstration using synthetic voice synthesis and simulated telecommunications states.",
        }

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve IVR call records sorted from newest to oldest."""
        calls = mongodb_service.find_all("ivr_calls", limit=limit)
        calls.sort(key=lambda x: x.get("initiated_at", ""), reverse=True)
        return calls

    def get_status(self) -> Dict[str, Any]:
        """Return status and metadata for IVR service."""
        calls = mongodb_service.find_all("ivr_calls", limit=500)
        return {
            "service": "IVR Reminder Service",
            "status": "operational",
            "mode": "simulated",
            "telephony": "none",
            "note": "Browser Web Speech API + MongoDB integrated simulation. No external paid telephony provider.",
            "disclaimer": "DEMO PROTOTYPE — Simulated interactive voice response reminders.",
            "total_simulated_calls": len(calls),
            "supported_languages": ["en", "hi", "ta", "kn"],
        }


# Singleton instance
ivr_service = IVRService()
