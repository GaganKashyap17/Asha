"""
Visit views — CRUD, extraction, mandatory-field validation, and confirmation.

SAVE RULE: A visit record is written to MongoDB ONLY when:
  1. All mandatory fields are present and pass validation
  2. No duplicate: the record has not already been saved
  3. The ASHA worker explicitly confirms the final read-back

The /visits/extract/ endpoint now returns a draft (in-memory only).
Use /visits/draft/<draft_id>/ to inspect, update, and confirm the draft.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from services.mongodb_service import mongodb_service
from services.extraction_service import extraction_service
from services.followup_service import followup_service
from services.validation_service import validation_service, VALID_VISIT_TYPES
from services.visit_session_service import visit_session_service
from services.danger_detection_service import detect_danger_signs, summarize_danger_results

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Existing endpoints — unchanged behaviour
# ---------------------------------------------------------------------------

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

    correction_log = {
        "visit_id": visit_id,
        "field": field,
        "old_value": visit.get(field),
        "new_value": value,
        "corrected_at": datetime.now(timezone.utc).isoformat(),
    }
    mongodb_service.insert("audit_logs", correction_log)

    update_key = "_id" if "_id" in visit else "id"
    mongodb_service.update_one("visits", {update_key: visit_id}, {"$set": {field: value}})
    updated = mongodb_service.find_one("visits", {update_key: visit_id})
    return Response(updated)


@api_view(["POST"])
@permission_classes([AllowAny])
def visit_confirm(request, visit_id):
    """Confirm an already-saved visit record (legacy endpoint — kept intact)."""
    visit = mongodb_service.find_one("visits", {"_id": visit_id})
    if not visit:
        visit = mongodb_service.find_one("visits", {"id": visit_id})
    if not visit:
        return Response({"error": "Visit not found"}, status=status.HTTP_404_NOT_FOUND)

    if visit.get("confirmation_status") == "confirmed":
        return Response({"message": "Already confirmed", "visit": visit})

    # Synchronize / link beneficiary
    linked_bene = _ensure_beneficiary_exists_and_linked(
        beneficiary_name=visit.get("beneficiary_name"),
        beneficiary_id=visit.get("beneficiary_id"),
        visit_data=visit,
    )

    update_key = "_id" if "_id" in visit else "id"
    updates = {
        "confirmation_status": "confirmed",
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    if linked_bene:
        updates["beneficiary_id"] = linked_bene.get("beneficiary_id")
        updates["beneficiary_name"] = linked_bene.get("name", visit.get("beneficiary_name"))

    mongodb_service.update_one(
        "visits",
        {update_key: visit_id},
        {"$set": updates},
    )

    confirmed = mongodb_service.find_one("visits", {update_key: visit_id})

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


# ---------------------------------------------------------------------------
# New extraction endpoint — returns draft, does NOT save to MongoDB
# ---------------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([AllowAny])
def extract_visit(request):
    """
    Extract structured data from transcript using Groq AI + danger detection.

    v2 BEHAVIOUR:
    - Extracted data is stored as an in-memory DRAFT only.
    - NOT written to MongoDB at this stage.
    - Returns draft_id + extraction result + missing_fields + danger alerts.
    - Use POST /visits/draft/<draft_id>/confirm/ to save after validation.
    """
    transcript = request.data.get("transcript", "")
    visit_type = request.data.get("visit_type", "household")
    worker_id  = request.data.get("worker_id", "unknown")

    if not transcript:
        return Response(
            {"error": "transcript is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 1. AI extraction + Pydantic validation
    result = extraction_service.extract_from_transcript(transcript, visit_type)

    if request.data.get("beneficiary_name") and not result.get("beneficiary_name"):
        result["beneficiary_name"] = request.data["beneficiary_name"]
    if request.data.get("beneficiary_id") and not result.get("beneficiary_id"):
        result["beneficiary_id"] = request.data["beneficiary_id"]

    result["raw_transcript"] = transcript

    # 2. Identify missing mandatory fields
    missing = validation_service.get_missing_mandatory_fields(result)
    result["missing_fields"] = missing

    # 3. Full validation
    is_valid, validation_errors = validation_service.validate(result)
    result["validation_errors"] = validation_errors if not is_valid else []

    # 4. Create in-memory draft — NOT written to MongoDB
    draft_id = visit_session_service.create_draft(result, worker_id=worker_id)

    # 5. Danger alert fires IMMEDIATELY regardless of field completeness
    danger_alert_created = False
    if result.get("danger_flag"):
        alert = {
            "draft_id":        draft_id,
            "beneficiary_id":  result.get("beneficiary_id"),
            "beneficiary_name": result.get("beneficiary_name"),
            "danger_signs":    result.get("danger_signs", []),
            "danger_details":  result.get("danger_detection_results", []),
            "referral_status": "pending",
            "resolved":        False,
            "created_at":      datetime.now(timezone.utc).isoformat(),
        }
        mongodb_service.insert("danger_alerts", alert)
        logger.warning(f"DANGER ALERT created for draft {draft_id}")
        danger_alert_created = True

    # 6. Build voice prompt for the first missing field
    next_prompt = None
    if missing:
        next_prompt = validation_service.get_field_prompt(missing[0])

    # 7. Build readback text only when complete
    readback = validation_service.build_readback_text(result) if not missing else None

    # 8. Compute advisory Random Forest ML assessment (never overrides clinical danger alerts)
    from services.ml_prediction_service import ml_prediction_service
    ml_assessment = ml_prediction_service.predict(visit_type, result, existing_danger_alert=result.get("danger_flag", False))

    return Response({
        "draft_id":           draft_id,
        "record":             result,
        "missing_fields":     missing,
        "is_complete":        len(missing) == 0 and is_valid,
        "validation_errors":  result["validation_errors"],
        "next_prompt":        next_prompt,
        "readback_text":      readback,
        "danger_flag":        result.get("danger_flag", False),
        "danger_alert_created": danger_alert_created,
        "ml_risk_assessment": ml_assessment,
    })


# ---------------------------------------------------------------------------
# Draft management endpoints
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([AllowAny])
def draft_detail(request, draft_id):
    """Get current state of a draft visit record."""
    draft = visit_session_service.get_draft(draft_id)
    if draft is None:
        return Response({"error": "Draft not found"}, status=status.HTTP_404_NOT_FOUND)

    missing = validation_service.get_missing_mandatory_fields(draft)
    next_prompt = validation_service.get_field_prompt(missing[0]) if missing else None
    readback = validation_service.build_readback_text(draft) if not missing else None

    return Response({
        "draft_id":       draft_id,
        "record":         draft,
        "missing_fields": missing,
        "is_complete":    len(missing) == 0,
        "next_prompt":    next_prompt,
        "readback_text":  readback,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def draft_add_field(request, draft_id):
    """
    Add or correct a single field in a draft via voice response.

    Body:
        field      (str)  — field name to update
        value      (any)  — new value (direct)
        transcript (str)  — raw voice response (LLM extracts field if value not given)
    """
    draft = visit_session_service.get_draft(draft_id)
    if draft is None:
        return Response({"error": "Draft not found"}, status=status.HTTP_404_NOT_FOUND)

    if draft.get("is_saved"):
        return Response(
            {"error": "This record has already been saved. Create a new visit instead."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    field      = request.data.get("field")
    value      = request.data.get("value")
    transcript = request.data.get("transcript", "")
    category   = request.data.get("category") or draft.get("revisit_category") or draft.get("visit_type", "household")

    extra_updates = {}
    if transcript and field and value is None:
        from services.groq_service import groq_service
        extracted_info = groq_service.extract_single_visit_field(transcript, field, category)
        value = extracted_info.get("value")
        for k, v in extracted_info.items():
            if k not in ("field", "value", "raw_transcript"):
                extra_updates[k] = v

    if not field:
        return Response({"error": "field is required"}, status=status.HTTP_400_BAD_REQUEST)

    field_error = _validate_single_field(field, value)
    if field_error:
        next_prompt = f"The value I heard was not valid. {field_error} " + validation_service.get_field_prompt(field)
        return Response({
            "draft_id":    draft_id,
            "field":       field,
            "error":       field_error,
            "next_prompt": next_prompt,
            "is_complete": False,
        }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    old_value = draft.get(field)
    if old_value != value:
        audit = {
            "draft_id":   draft_id,
            "field":      field,
            "old_value":  old_value,
            "new_value":  value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source":     "draft_field_update",
        }
        mongodb_service.insert("audit_logs", audit)

    updates = {field: value, **extra_updates}
    updated = visit_session_service.update_draft(draft_id, updates)
    if updated is None:
        return Response({"error": "Draft not found"}, status=status.HTTP_404_NOT_FOUND)

    cat_to_check = updated.get("revisit_category") or category
    missing = validation_service.get_missing_mandatory_fields(updated, category=cat_to_check)
    next_prompt = validation_service.get_field_prompt(missing[0]) if missing else None
    readback = validation_service.build_readback_text(updated) if not missing else None

    return Response({
        "draft_id":       draft_id,
        "record":         updated,
        "field_updated":  field,
        "new_value":      value,
        "missing_fields": missing,
        "is_complete":    len(missing) == 0,
        "next_prompt":    next_prompt,
        "readback_text":  readback,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def draft_confirm(request, draft_id):
    """
    Confirm and save a completed draft to MongoDB.

    This is the ONLY place where a visit record is written to MongoDB.
    All save conditions are enforced here.
    """
    draft = visit_session_service.get_draft(draft_id)
    if draft is None:
        return Response({"error": "Draft not found"}, status=status.HTTP_404_NOT_FOUND)

    # Duplicate save guard
    if draft.get("is_saved"):
        saved_visit = None
        db_id = draft.get("db_id")
        if db_id:
            saved_visit = mongodb_service.find_one("visits", {"_id": db_id})
        return Response({
            "message":  "This record was already saved — no duplicate created.",
            "visit":    saved_visit,
            "draft_id": draft_id,
        })

    # Enforce ALL save conditions
    category = draft.get("revisit_category") or draft.get("beneficiary_type")
    ready, reasons = validation_service.is_ready_to_save(draft, category=category)
    if not ready:
        missing = validation_service.get_missing_mandatory_fields(draft, category=category)
        next_prompt = validation_service.get_field_prompt(missing[0]) if missing else None
        return Response(
            {
                "error":            "Record is not ready to save.",
                "blocking_reasons": reasons,
                "missing_fields":   missing,
                "next_prompt":      next_prompt,
                "draft_id":         draft_id,
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # All conditions met — write to MongoDB
    db_record = {k: v for k, v in draft.items()
                 if k not in {"draft_id", "is_saved", "db_id", "validation_errors"}}
    db_record["_id"]                 = str(uuid.uuid4())
    db_record["id"]                  = db_record["_id"]
    db_record["confirmation_status"] = "confirmed"
    db_record["confirmed_at"]        = datetime.now(timezone.utc).isoformat()
    db_record["created_at"]          = datetime.now(timezone.utc).isoformat()

    # Synchronize / link beneficiary in MongoDB Beneficiaries collection
    linked_bene = _ensure_beneficiary_exists_and_linked(
        beneficiary_name=draft.get("beneficiary_name"),
        beneficiary_id=draft.get("beneficiary_id"),
        visit_data=draft,
    )
    if linked_bene:
        db_record["beneficiary_id"] = linked_bene.get("beneficiary_id")
        db_record["beneficiary_name"] = linked_bene.get("name", draft.get("beneficiary_name"))

    saved = mongodb_service.insert("visits", db_record)
    visit_session_service.mark_saved(draft_id, db_record["_id"])

    if draft.get("danger_flag"):
        mongodb_service.update_one(
            "danger_alerts",
            {"draft_id": draft_id},
            {"$set": {"visit_id": db_record["_id"]}},
        )

    followup = None
    try:
        followup = followup_service.create_followup_from_visit(saved)
    except Exception as e:
        logger.error(f"Followup generation failed: {type(e).__name__}")

    logger.info(f"Visit saved to MongoDB: {db_record['_id']} (draft: {draft_id})")

    return Response({
        "message":  "Visit confirmed and saved to MongoDB.",
        "visit":    saved,
        "followup": followup,
        "draft_id": draft_id,
    }, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([AllowAny])
def draft_discard(request, draft_id):
    """Discard a draft (cancel workflow without saving)."""
    discarded = visit_session_service.discard_draft(draft_id)
    if not discarded:
        return Response({"error": "Draft not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response({"message": "Draft discarded.", "draft_id": draft_id})


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_field_value(transcript: str, field: str, visit_type: str):
    """Use GroqService to extract and normalize a single field value from speech."""
    from services.groq_service import groq_service
    res = groq_service.extract_single_visit_field(transcript, field, visit_type)
    return res.get("value")


def _validate_single_field(field: str, value) -> Optional[str]:
    """Validate a single field value. Returns error string or None if valid."""
    if value is None or str(value).strip() in ("", "None", "null", "none", "nan"):
        return None
    if field in ("weight_kg", "current_weight_kg") and value is not None:
        try:
            w = float(value)
            if not (0.5 <= w <= 200):
                return f"Weight {w} kg is outside valid range (0.5–200 kg)."
        except (ValueError, TypeError):
            return "Weight must be a number."

    if field == "temperature_celsius" and value is not None:
        try:
            temp = float(value)
            if not (30.0 <= temp <= 45.0):
                return f"Temperature {temp}°C is outside valid clinical range (30–45°C)."
        except (ValueError, TypeError):
            return "Temperature must be a valid number."

    if field == "respiratory_rate" and value is not None:
        try:
            rr = int(value)
            if not (10 <= rr <= 120):
                return f"Respiratory rate {rr} breaths/min is outside valid range (10–120)."
        except (ValueError, TypeError):
            return "Respiratory rate must be an integer."

    if field in ("hb_level", "haemoglobin") and value is not None:
        try:
            hb = float(value)
            if not (2.0 <= hb <= 25.0):
                return f"Haemoglobin {hb} g/dL is outside valid range (2–25 g/dL)."
        except (ValueError, TypeError):
            return "Haemoglobin must be a number."

    if field in ("blood_sugar_level", "blood_sugar") and value is not None:
        try:
            bs = float(value)
            if not (20.0 <= bs <= 600.0):
                return f"Blood sugar {bs} mg/dL is outside valid range (20–600 mg/dL)."
        except (ValueError, TypeError):
            return "Blood sugar must be a number."

    if field in ("height_cm", "length_cm") and value is not None:
        try:
            h = float(value)
            if not (20.0 <= h <= 200.0):
                return f"Height {h} cm is outside valid range (20–200 cm)."
        except (ValueError, TypeError):
            return "Height must be a number."

    if field in ("visit_date", "next_visit_date", "next_vaccination_due_date") and value is not None:
        try:
            datetime.strptime(str(value), "%Y-%m-%d")
        except ValueError:
            return f"Date must be in YYYY-MM-DD format, got: {value}"

    return None


def _ensure_beneficiary_exists_and_linked(
    beneficiary_name: Optional[str],
    beneficiary_id: Optional[str],
    visit_data: dict,
) -> Optional[dict]:
    """
    Ensure the beneficiary exists in the MongoDB 'beneficiaries' collection.
    - If beneficiary_id exists: updates visit dates/status on that beneficiary.
    - If beneficiary_id is missing: checks for an existing active beneficiary with matching name (case-insensitive) to prevent duplicates.
    - If no existing record exists: creates a new beneficiary in MongoDB and generates a BENxxx ID.
    - Preserves historical records and keeps Beneficiary and History modules perfectly in sync.
    """
    from apps.beneficiaries.views import generate_beneficiary_id

    bene = None
    if beneficiary_id:
        bene = mongodb_service.find_one("beneficiaries", {
            "beneficiary_id": beneficiary_id,
            "is_deleted": {"$ne": True}
        })

    if not bene and beneficiary_name:
        b_name_clean = beneficiary_name.strip()
        if mongodb_service.is_connected():
            bene = mongodb_service.find_one("beneficiaries", {
                "name": {"$regex": f"^{b_name_clean}$", "$options": "i"},
                "is_deleted": {"$ne": True}
            })
        if not bene:
            all_b = mongodb_service.find_all("beneficiaries", {"is_deleted": {"$ne": True}})
            for b in all_b:
                if b.get("name", "").strip().lower() == b_name_clean.lower():
                    bene = b
                    break

    now_iso = datetime.now(timezone.utc).isoformat()
    visit_type = visit_data.get("visit_type", "household")
    visit_date = visit_data.get("visit_date") or datetime.now(timezone.utc).date().isoformat()
    next_visit_date = visit_data.get("next_visit_date")
    pregnancy_month = visit_data.get("pregnancy_month")

    if bene:
        # Update existing beneficiary with latest visit info
        updates = {"last_visit_date": visit_date, "updated_at": now_iso}
        if next_visit_date:
            updates["next_visit_date"] = next_visit_date
        if pregnancy_month is not None:
            updates["pregnancy_month"] = pregnancy_month
            updates["pregnancy_status"] = "pregnant"
        elif visit_type in ("newborn", "postnatal") and bene.get("pregnancy_status") == "pregnant":
            updates["pregnancy_status"] = "postnatal"

        mongodb_service.update_one(
            "beneficiaries",
            {"beneficiary_id": bene["beneficiary_id"]},
            {"$set": updates}
        )
        bene.update(updates)
        logger.info(f"Synchronized visit dates for existing beneficiary: {bene['beneficiary_id']} ({bene.get('name')})")
        return bene
    elif beneficiary_name and beneficiary_name.strip():
        # Auto-create new beneficiary in MongoDB
        new_id = generate_beneficiary_id()
        preg_status = "pregnant" if visit_type == "pregnancy" else "postnatal" if visit_type in ("newborn", "postnatal") else "not_pregnant"
        new_bene = {
            "beneficiary_id": new_id,
            "name": beneficiary_name.strip(),
            "pregnancy_status": preg_status,
            "pregnancy_month": pregnancy_month,
            "last_visit_date": visit_date,
            "next_visit_date": next_visit_date,
            "is_deleted": False,
            "is_archived": False,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        saved_bene = mongodb_service.insert("beneficiaries", new_bene)
        logger.info(f"Created new beneficiary document from voice visit: {new_id} ({beneficiary_name})")
        return saved_bene

    return None


# ---------------------------------------------------------------------------
# Revisit Bar endpoints
# ---------------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([AllowAny])
def revisit_init(request):
    """
    Step 1 of Revisit workflow: Extract beneficiary ID + spoken name from initial speech.
    Looks up the beneficiary in MongoDB. Performs name matching.
    Does NOT save any visit record.
    """
    from services.groq_service import groq_service
    
    transcript = request.data.get("transcript", "").strip()
    language = request.data.get("language", "en")
    
    if not transcript:
        return Response({"error": "Transcript is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Translate if needed
    english_transcript = transcript
    if language != 'en':
        try:
            english_transcript = groq_service.translate_to_english(transcript, language)
        except Exception:
            pass  # Fallback to transcript
    
    # Extract identity from transcript
    try:
        identity = groq_service.extract_revisit_identity(english_transcript)
    except Exception as e:
        return Response({"error": f"Identity extraction failed: {type(e).__name__}: {str(e)}"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    spoken_id = identity.get("beneficiary_id")
    spoken_name = identity.get("spoken_name")
    
    if not spoken_id and not spoken_name:
        return Response({
            "found": False,
            "spoken_id": None,
            "spoken_name": None,
            "english_transcript": english_transcript,
            "warning_message": "Could not identify a Beneficiary ID or Name in the speech. Please speak the Beneficiary ID (e.g. 'PREG 001') or Name clearly.",
        })
    
    import re
    from services.mongodb_service import mongodb_service as mdb

    clean_id = (spoken_id or "").strip().upper().replace(" ", "")
    if clean_id:
        match = re.search(r"\b(PREG|NEWB|IMM|BEN)[-_ ]?((?:202[4-9]|203[0-9])[-_ ]?)?(\d+)\b", clean_id, re.I)
        if match:
            pfx = match.group(1).upper()
            yr = re.sub(r"\D", "", match.group(2) or "")
            digits = match.group(3)
            if yr:
                clean_id = f"{pfx}-{yr}-{digits.zfill(6)}"
            elif len(digits) >= 4:
                clean_id = f"{pfx}-{digits.zfill(6)}"
            else:
                clean_id = f"{pfx}{digits.zfill(3)}"

    beneficiary = None

    # 1. DB Lookup by ID if present
    if clean_id:
        beneficiary = mdb.find_one("beneficiaries", {
            "$or": [
                {"beneficiary_id": clean_id},
                {"beneficiary_id": {"$regex": f"^{re.escape(clean_id)}$", "$options": "i"}},
            ],
            "is_deleted": {"$ne": True},
        })

        if not beneficiary:
            # Check flexible digit suffix matching (e.g. spoken PREG 1 matching PREG-2026-000001 or PREG-000001)
            digits_match = re.search(r"(\d+)$", clean_id)
            pfx_match = re.search(r"^(PREG|NEWB|IMM|BEN)", clean_id, re.I)
            if digits_match and pfx_match:
                digs = digits_match.group(1).lstrip("0") or "0"
                pfx = pfx_match.group(1).upper()
                all_b = mdb.find_all("beneficiaries", {"is_deleted": {"$ne": True}}, limit=300)
                for b in all_b:
                    b_id = str(b.get("beneficiary_id") or "").upper()
                    if b_id.startswith(pfx) and (b_id.endswith(digs) or b_id.endswith(digs.zfill(6))):
                        beneficiary = b
                        clean_id = b["beneficiary_id"]
                        break

    # 2. DB Lookup by Name if ID not found or not provided
    if not beneficiary and spoken_name:
        clean_name = spoken_name.strip()
        beneficiary = mdb.find_one("beneficiaries", {
            "name": {"$regex": f"^{re.escape(clean_name)}$", "$options": "i"},
            "is_deleted": {"$ne": True},
        })
        if not beneficiary:
            # Substring / partial match on name
            beneficiary = mdb.find_one("beneficiaries", {
                "name": {"$regex": f"{re.escape(clean_name)}", "$options": "i"},
                "is_deleted": {"$ne": True},
            })
        if beneficiary:
            clean_id = beneficiary.get("beneficiary_id", "")

    # 3. Comprehensive partial scan
    if not beneficiary:
        all_b = mdb.find_all("beneficiaries", {"is_deleted": {"$ne": True}}, limit=300)
        for b in all_b:
            b_id = str(b.get("beneficiary_id") or "").upper()
            b_n = str(b.get("name") or "").lower()
            if (clean_id and clean_id in b_id) or (spoken_name and spoken_name.lower() in b_n):
                beneficiary = b
                clean_id = b["beneficiary_id"]
                break

    if not beneficiary:
        target_repr = clean_id or spoken_name or "spoken identity"
        return Response({
            "found": False,
            "spoken_id": clean_id,
            "spoken_name": spoken_name,
            "english_transcript": english_transcript,
            "warning_message": f"No active beneficiary found with ID or name '{target_repr}'. Please verify and try again.",
        })
    
    # Name matching (fuzzy, case-insensitive)
    name_match = False
    name_match_quality = "none"
    existing_name = beneficiary.get("name", "").lower().strip()
    
    if spoken_name:
        spoken_lower = spoken_name.lower().strip()
        if existing_name == spoken_lower:
            name_match = True
            name_match_quality = "exact"
        elif (len(existing_name) > 3 and existing_name in spoken_lower) or (len(spoken_lower) > 3 and spoken_lower in existing_name):
            name_match = True
            name_match_quality = "partial"
        else:
            existing_words = set(existing_name.split())
            spoken_words = set(spoken_lower.split())
            common = existing_words & spoken_words
            if len(common) >= 1:
                name_match = True
                name_match_quality = "word_overlap"
    else:
        name_match = True
        name_match_quality = "id_only"
    
    warning_message = None
    if not name_match and spoken_name:
        warning_message = f"Name mismatch: You said '{spoken_name}' but the record shows '{beneficiary.get('name')}'. Please confirm this is the correct beneficiary."
    
    return Response({
        "found": True,
        "beneficiary_id": beneficiary.get("beneficiary_id", clean_id),
        "spoken_id": clean_id,
        "spoken_name": spoken_name,
        "english_transcript": english_transcript,
        "name_match": name_match,
        "name_match_quality": name_match_quality,
        "existing_beneficiary": beneficiary,
        "warning_message": warning_message,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def revisit_extract(request):
    """
    Step 2 of Revisit workflow: Extract clinical visit data after identity is confirmed.
    Creates a draft in visit_session_service (NOT saved to MongoDB).
    """
    from services.groq_service import groq_service
    from services.mongodb_service import mongodb_service as mdb
    from services.danger_detection_service import detect_danger_signs, detect_danger_signs_from_record
    
    transcript = request.data.get("transcript", "").strip()
    language = request.data.get("language", "en")
    beneficiary_id = request.data.get("beneficiary_id", "").strip().upper()
    
    if not transcript:
        return Response({"error": "Transcript is required"}, status=status.HTTP_400_BAD_REQUEST)
    if not beneficiary_id:
        return Response({"error": "beneficiary_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Verify beneficiary still exists
    beneficiary = mdb.find_one("beneficiaries", {
        "beneficiary_id": beneficiary_id,
        "is_deleted": {"$ne": True},
    })
    if not beneficiary:
        return Response({"error": f"Beneficiary '{beneficiary_id}' not found"}, status=status.HTTP_404_NOT_FOUND)
    
    # Determine category
    b_cat = request.data.get("beneficiary_type") or beneficiary.get("beneficiary_type")
    if not b_cat:
        if beneficiary.get("pregnancy_status") == "pregnant" or beneficiary_id.startswith("PREG"):
            b_cat = "pregnant_woman"
        elif beneficiary_id.startswith("NEWB"):
            b_cat = "newborn"
        elif beneficiary_id.startswith("IMM"):
            b_cat = "immunization_child"
        else:
            b_cat = "pregnant_woman"

    # Translate if needed
    english_transcript = transcript
    if language != 'en':
        try:
            english_transcript = groq_service.translate_to_english(transcript, language)
        except Exception:
            pass
    
    # Extract clinical data tailored to category
    try:
        extracted = groq_service.extract_revisit_clinical(english_transcript, b_cat)
    except Exception as e:
        return Response({"error": f"Extraction failed: {type(e).__name__}: {str(e)}"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    # Determine visit_type
    visit_type = extracted.get("visit_type") or ("pregnancy" if b_cat in ("pregnant_woman", "pregnancy") else "newborn" if b_cat == "newborn" else "immunisation")
    
    # Run danger detection on transcript
    danger_results = detect_danger_signs(english_transcript, visit_type)
    
    # Build complete category-specific clinical visit record
    now = datetime.now(timezone.utc).isoformat()
    draft_id = str(uuid.uuid4())
    
    record = {
        "_id": draft_id,
        "draft_id": draft_id,
        "beneficiary_id": beneficiary_id,
        "beneficiary_name": beneficiary.get("name", ""),
        "visit_type": visit_type,
        "revisit_category": b_cat,
        "is_revisit": True,
        "visit_date": extracted.get("visit_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "danger_signs": [],
        "danger_flag": False,
        "raw_transcript": transcript,
        "english_transcript": english_transcript,
        "confirmation_status": "pending",
        "confidence_score": 0.95,
        "created_at": now,
        "symptoms": extracted.get("symptoms", []),

        # ── 1. Pregnant Woman Mandatory Observations ──
        "weight_kg": extracted.get("weight_kg"),
        "blood_pressure": extracted.get("blood_pressure") or (f"{extracted.get('blood_pressure_systolic')}/{extracted.get('blood_pressure_diastolic')}" if extracted.get("blood_pressure_systolic") and extracted.get("blood_pressure_diastolic") else None),
        "blood_pressure_systolic": extracted.get("blood_pressure_systolic"),
        "blood_pressure_diastolic": extracted.get("blood_pressure_diastolic"),
        "hb_level": extracted.get("hb_level"),
        "blood_sugar_level": extracted.get("blood_sugar_level"),
        "vaginal_bleeding": extracted.get("vaginal_bleeding"),
        "severe_headache_blurred_vision": extracted.get("severe_headache_blurred_vision"),
        "fetal_movement": extracted.get("fetal_movement"),
        "ifa_calcium_consumption": extracted.get("ifa_calcium_consumption"),
        "pregnancy_month": extracted.get("pregnancy_month"),
        "ifa_given": extracted.get("ifa_given"),
        "calcium_given": extracted.get("calcium_given"),

        # ── 2. Newborn Mandatory Observations ──
        "temperature_celsius": extracted.get("temperature_celsius"),
        "respiratory_rate": extracted.get("respiratory_rate"),
        "breastfeeding_status": extracted.get("breastfeeding_status"),
        "difficulty_in_feeding": extracted.get("difficulty_in_feeding"),
        "difficulty_in_breathing": extracted.get("difficulty_in_breathing"),
        "yellowing_skin_eyes": extracted.get("yellowing_skin_eyes"),
        "umbilical_cord_condition": extracted.get("umbilical_cord_condition"),

        # ── 3. Immunization Beneficiary Mandatory Observations ──
        "height_cm": extracted.get("height_cm"),
        "general_health_condition": extracted.get("general_health_condition"),
        "vaccines_due_today": extracted.get("vaccines_due_today"),
        "vaccines_given_today": extracted.get("vaccines_given_today"),
        "missed_vaccination_doses": extracted.get("missed_vaccination_doses"),
        "previous_aefi": extracted.get("previous_aefi"),
        "next_vaccination_due_date": extracted.get("next_vaccination_due_date"),
        "next_visit_date": extracted.get("next_visit_date") or extracted.get("next_vaccination_due_date"),
    }
    
    # Normalize clinical fields for pregnant woman
    if record.get("vaginal_bleeding"):
        vb = str(record["vaginal_bleeding"]).lower()
        if any(w in vb for w in ("no", "none", "nil", "not", "clear", "denied")):
            record["vaginal_bleeding"] = "No"
        elif any(w in vb for w in ("spot", "mild")):
            record["vaginal_bleeding"] = "Spotting"
        elif any(w in vb for w in ("yes", "bleed", "present", "heavy", "true", "active")):
            record["vaginal_bleeding"] = "Yes"

    if record.get("ifa_calcium_consumption"):
        ifa = str(record["ifa_calcium_consumption"]).lower()
        if any(w in ifa for w in ("irregular", "miss", "sometimes", "forgot", "skip", "poor")):
            record["ifa_calcium_consumption"] = "Irregular / Missed Doses"
        elif any(w in ifa for w in ("not", "no", "stopped", "none", "didn't")):
            record["ifa_calcium_consumption"] = "Not Consumed"
        elif any(w in ifa for w in ("only ifa", "iron only")):
            record["ifa_calcium_consumption"] = "Only IFA Consumed"
        elif any(w in ifa for w in ("only calcium", "calcium only")):
            record["ifa_calcium_consumption"] = "Only Calcium Consumed"
        elif any(w in ifa for w in ("both", "regular", "daily", "yes", "all", "compliant")):
            record["ifa_calcium_consumption"] = "Both Consumed Regularly"

    # Evaluate danger signs on BOTH transcript AND structured record fields
    record_dangers = detect_danger_signs_from_record(record, b_cat)
    seen_rules = {r.rule_id for r in danger_results if r.detected}
    combined_danger_results = list(danger_results)
    for rd in record_dangers:
        if rd.rule_id not in seen_rules:
            combined_danger_results.append(rd)
            seen_rules.add(rd.rule_id)

    confirmed_dangers = [r for r in combined_danger_results if r.detected]
    danger_flag = len(confirmed_dangers) > 0
    danger_signs_list = list({r.name for r in confirmed_dangers}) if confirmed_dangers else extracted.get("danger_signs", [])
    record["danger_flag"] = danger_flag
    record["danger_signs"] = danger_signs_list

    # Determine missing mandatory fields for this category
    from services.validation_service import validation_service
    missing = validation_service.get_missing_mandatory_fields(record, category=b_cat)
    record["missing_fields"] = missing
    
    # Store in visit_session_service as draft
    draft_id = visit_session_service.create_draft(record)
    record["_id"] = draft_id
    record["draft_id"] = draft_id
    
    is_complete = len(missing) == 0
    readback_text = validation_service.build_readback_text(record)
    
    danger_detection_results = [
        {
            "rule_id": r.rule_id,
            "name": r.name,
            "detected": r.detected,
            "severity": r.severity,
            "referral_message_en": r.referral_message_en if r.detected else None,
            "referral_message_ta": r.referral_message_ta if r.detected else None,
        }
        for r in combined_danger_results
        if r.detected
    ]
    
    from services.ml_prediction_service import ml_prediction_service
    ml_assessment = ml_prediction_service.predict(b_cat, record, existing_danger_alert=danger_flag)

    return Response({
        "draft_id": draft_id,
        "record": record,
        "missing_fields": missing,
        "is_complete": is_complete,
        "validation_errors": [],
        "readback_text": readback_text,
        "danger_flag": danger_flag,
        "danger_detection_results": danger_detection_results,
        "ml_risk_assessment": ml_assessment,
        "beneficiary": {
            "beneficiary_id": beneficiary_id,
            "name": beneficiary.get("name"),
            "village": beneficiary.get("village", ""),
            "pregnancy_status": beneficiary.get("pregnancy_status", ""),
            "beneficiary_type": b_cat,
        },
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def revisit_extract_field(request):
    """
    Extract a single clinical field value from a voice response and update draft session.
    """
    from services.groq_service import groq_service
    from services.validation_service import validation_service
    from services.danger_detection_service import detect_danger_signs_from_record

    field = request.data.get("field", "").strip()
    transcript = request.data.get("transcript", "").strip()
    category = request.data.get("category", "pregnant_woman")
    draft_id = request.data.get("draft_id")

    if not field or not transcript:
        return Response({"error": "field and transcript are required"}, status=status.HTTP_400_BAD_REQUEST)

    extracted_info = groq_service.extract_single_visit_field(transcript, field, category)
    val = extracted_info.get("value")

    updated_record = None
    missing_fields = []
    is_complete = False

    if draft_id:
        draft = visit_session_service.get_draft(draft_id)
        if draft:
            updates = {field: val}
            for k, v in extracted_info.items():
                if k not in ("field", "value", "raw_transcript"):
                    updates[k] = v
            updated_record = visit_session_service.update_draft(draft_id, updates)
            if updated_record:
                b_cat = category or updated_record.get("revisit_category")
                missing_fields = validation_service.get_missing_mandatory_fields(updated_record, category=b_cat)
                is_complete = len(missing_fields) == 0

    # Evaluate danger signs for the field/updated record
    target_record = updated_record or {field: val}
    for k, v in extracted_info.items():
        if k not in ("field", "value", "raw_transcript"):
            target_record[k] = v

    field_dangers = detect_danger_signs_from_record(target_record, category)
    confirmed_field_dangers = [r for r in field_dangers if r.detected]
    danger_flag = len(confirmed_field_dangers) > 0
    danger_detection_results = [
        {
            "rule_id": r.rule_id,
            "name": r.name,
            "severity": r.severity,
            "detected": r.detected,
            "referral_message_en": r.referral_message_en,
            "referral_message_ta": r.referral_message_ta,
        }
        for r in confirmed_field_dangers
    ]

    from services.ml_prediction_service import ml_prediction_service
    ml_assessment = ml_prediction_service.predict(category, target_record, existing_danger_alert=danger_flag)

    return Response({
        "field": field,
        "value": val,
        "extracted_info": extracted_info,
        "draft_id": draft_id,
        "missing_fields": missing_fields,
        "is_complete": is_complete,
        "record": updated_record,
        "danger_flag": danger_flag,
        "danger_detection_results": danger_detection_results,
        "ml_risk_assessment": ml_assessment,
    })


