"""Beneficiary CRUD views — registration, edit, soft-delete/archive, and detail."""
import logging
from datetime import datetime, timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from services.mongodb_service import mongodb_service
from services.beneficiary_validation_service import validate_beneficiary_data, VALID_CATEGORIES
from services.id_generation_service import generate_category_beneficiary_id

logger = logging.getLogger(__name__)


def generate_beneficiary_id() -> str:
    """Legacy helper: generate generic sequential beneficiary ID."""
    return generate_category_beneficiary_id("other")


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def beneficiary_list_create(request):
    if request.method == "GET":
        search = request.query_params.get("search", "").strip()
        include_archived = request.query_params.get("include_archived", "false").lower() == "true"
        category = request.query_params.get("category") or request.query_params.get("beneficiary_type")

        query = {}
        if not include_archived:
            query["is_deleted"] = {"$ne": True}
        if category:
            query["beneficiary_type"] = category

        beneficiaries = mongodb_service.find_all("beneficiaries", query, limit=200)

        if search:
            search_lower = search.lower()
            beneficiaries = [
                b for b in beneficiaries
                if search_lower in b.get("name", "").lower()
                or search_lower in b.get("beneficiary_id", "").lower()
                or search_lower in b.get("village", "").lower()
                or search_lower in b.get("household", "").lower()
                or search_lower in b.get("phone", "").lower()
            ]

        return Response({"results": beneficiaries, "count": len(beneficiaries)})

    if request.method == "POST":
        data = request.data.copy()
        beneficiary_type = (data.get("beneficiary_type") or data.get("category") or "other").strip().lower()
        if beneficiary_type not in VALID_CATEGORIES:
            return Response(
                {"error": f"Invalid category '{beneficiary_type}'. Allowed: {VALID_CATEGORIES}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── 1. Category-Based Mandatory Field & Rule Validation ──────────
        val_result = validate_beneficiary_data(beneficiary_type, data, check_mother_exists=True)
        if not val_result["is_valid"]:
            return Response(
                {
                    "error": f"Mandatory validation failed for category '{beneficiary_type}'",
                    "missing_mandatory": val_result["missing_mandatory"],
                    "validation_errors": val_result["validation_errors"],
                    "inconsistencies": val_result["inconsistencies"],
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        sanitized = val_result["sanitized_data"]

        # ── 2. Unique Beneficiary ID Generation ──────────────────────────
        # Generated ONLY AFTER mandatory validation succeeds
        beneficiary_id = str(data.get("beneficiary_id") or "").strip().upper()
        if not beneficiary_id:
            beneficiary_id = generate_category_beneficiary_id(beneficiary_type)
        else:
            existing = mongodb_service.find_one("beneficiaries", {
                "beneficiary_id": beneficiary_id,
                "is_deleted": {"$ne": True}
            })
            if existing:
                return Response(
                    {"error": f"Beneficiary ID '{beneficiary_id}' already exists"},
                    status=status.HTTP_409_CONFLICT,
                )

        now_iso = datetime.now(timezone.utc).isoformat()
        reg_date = sanitized.get("registration_date") or datetime.now(timezone.utc).date().isoformat()
        name = sanitized.get("name") or sanitized.get("baby_name") or sanitized.get("child_name")

        # ── 3. Build Structured Category-Specific Document ───────────────
        doc = {
            "beneficiary_id": beneficiary_id,
            "beneficiary_type": beneficiary_type,
            "name": name,
            "registration_date": reg_date,
            "asha_worker_id": data.get("asha_worker_id") or "ASHA001",
            "phone": sanitized.get("phone", ""),
            "village": sanitized.get("village", ""),
            "household": sanitized.get("household", ""),
            "address": sanitized.get("address", "") or sanitized.get("household", ""),
            "gender": sanitized.get("gender", ""),
            "age": sanitized.get("age"),
            "original_transcript": data.get("original_transcript", ""),
            "english_translation": data.get("english_translation", ""),
            "registration_status": "registered",
            "confirmation_status": "confirmed",
            "is_deleted": False,
            "is_archived": False,
            "created_at": now_iso,
            "updated_at": now_iso,
        }

        # Embed category-specific object without populating irrelevant fields
        if beneficiary_type == "pregnant_woman":
            doc["pregnancy_status"] = "pregnant"
            doc["pregnancy_month"] = sanitized.get("pregnancy_month") or (sanitized.get("gestational_age_weeks", 0) // 4)
            doc["expected_delivery_date"] = sanitized.get("edd") or sanitized.get("expected_delivery_date")
            doc["pregnancy_details"] = {
                "lmp": sanitized.get("lmp"),
                "edd": sanitized.get("edd") or sanitized.get("expected_delivery_date"),
                "gestational_age_weeks": sanitized.get("gestational_age_weeks"),
                "pregnancy_registration_status": sanitized.get("pregnancy_registration_status"),
                "gravida": sanitized.get("gravida"),
                "previous_live_births": sanitized.get("previous_live_births"),
                "previous_complications": sanitized.get("previous_complications"),
            }

        elif beneficiary_type == "newborn":
            doc["pregnancy_status"] = "postnatal"
            doc["newborn_details"] = {
                "baby_name": sanitized.get("baby_name") or name,
                "dob": sanitized.get("dob"),
                "gender": sanitized.get("gender"),
                "mother_name": sanitized.get("mother_name"),
                "mother_beneficiary_id": sanitized.get("mother_beneficiary_id"),
                "place_of_delivery": sanitized.get("place_of_delivery"),
                "birth_weight_kg": sanitized.get("birth_weight_kg"),
            }

        elif beneficiary_type == "immunization_child":
            doc["immunization_details"] = {
                "child_name": sanitized.get("child_name") or name,
                "dob": sanitized.get("dob"),
                "gender": sanitized.get("gender"),
                "mother_name": sanitized.get("mother_name"),
                "mother_beneficiary_id": sanitized.get("mother_beneficiary_id"),
                "immunization_card_status": sanitized.get("immunization_card_status"),
                "vaccination_status": sanitized.get("vaccination_status"),
                "vaccinations_received": sanitized.get("vaccinations_received", []),
                "vaccinations_pending": sanitized.get("vaccinations_pending", []),
            }

        elif beneficiary_type == "other":
            doc["other_beneficiary_details"] = {
                "beneficiary_category": sanitized.get("beneficiary_category"),
                "emergency_contact": sanitized.get("emergency_contact"),
                "blood_group": sanitized.get("blood_group"),
            }

        saved = mongodb_service.insert("beneficiaries", doc)
        logger.info(f"Beneficiary created successfully: {beneficiary_id} ({name}, {beneficiary_type})")
        return Response(saved, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([AllowAny])
def beneficiary_detail(request, beneficiary_id):
    beneficiary_id = beneficiary_id.strip()
    beneficiary = mongodb_service.find_one("beneficiaries", {"beneficiary_id": beneficiary_id})
    if not beneficiary:
        return Response({"error": "Beneficiary not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        visits = mongodb_service.find_all("visits", {"beneficiary_id": beneficiary_id})
        beneficiary["visit_history"] = visits
        return Response(beneficiary)

    if request.method in ("PUT", "PATCH"):
        update_data = {
            k: v for k, v in request.data.items()
            if k not in ("_id", "beneficiary_id", "created_at")
        }

        # Validation
        if "name" in update_data:
            new_name = str(update_data["name"]).strip()
            if not new_name:
                return Response({"error": "Name cannot be empty"}, status=status.HTTP_400_BAD_REQUEST)
            update_data["name"] = new_name

        if "age" in update_data and update_data["age"] not in (None, ""):
            try:
                age = int(update_data["age"])
                if not (0 <= age <= 120):
                    return Response({"error": "Age must be between 0 and 120"}, status=status.HTTP_400_BAD_REQUEST)
                update_data["age"] = age
            except (ValueError, TypeError):
                return Response({"error": "Age must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        if "pregnancy_month" in update_data and update_data["pregnancy_month"] not in (None, ""):
            try:
                pm = int(update_data["pregnancy_month"])
                if not (1 <= pm <= 9):
                    return Response({"error": "Pregnancy month must be between 1 and 9"}, status=status.HTTP_400_BAD_REQUEST)
                update_data["pregnancy_month"] = pm
            except (ValueError, TypeError):
                return Response({"error": "Pregnancy month must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        if "newborn_age_days" in update_data and update_data["newborn_age_days"] not in (None, ""):
            try:
                nad = int(update_data["newborn_age_days"])
                if not (0 <= nad <= 365):
                    return Response({"error": "Newborn age must be between 0 and 365 days"}, status=status.HTTP_400_BAD_REQUEST)
                update_data["newborn_age_days"] = nad
            except (ValueError, TypeError):
                return Response({"error": "Newborn age must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        mongodb_service.update_one(
            "beneficiaries",
            {"beneficiary_id": beneficiary_id},
            {"$set": update_data},
        )

        # Synchronize updated name across visits and danger alerts if name was changed
        if "name" in update_data and update_data["name"] != beneficiary.get("name"):
            new_name = update_data["name"]
            mongodb_service.update_many(
                "visits",
                {"beneficiary_id": beneficiary_id},
                {"$set": {"beneficiary_name": new_name}},
            )
            mongodb_service.update_many(
                "danger_alerts",
                {"beneficiary_id": beneficiary_id},
                {"$set": {"beneficiary_name": new_name}},
            )
            logger.info(f"Updated associated visits and alerts with new name '{new_name}' for {beneficiary_id}")

        updated = mongodb_service.find_one("beneficiaries", {"beneficiary_id": beneficiary_id})
        return Response(updated)

    if request.method == "DELETE":
        # Safe archive / soft-delete: keeps all historical records and visits intact
        mongodb_service.update_one(
            "beneficiaries",
            {"beneficiary_id": beneficiary_id},
            {"$set": {
                "is_deleted": True,
                "is_archived": True,
                "archived_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        logger.info(f"Beneficiary {beneficiary_id} safely archived. Historical visits preserved.")
        return Response({
            "message": f"Beneficiary {beneficiary_id} archived successfully. Visit history is preserved.",
            "beneficiary_id": beneficiary_id,
            "status": "archived",
        }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def beneficiary_register_voice(request):
    """
    Voice-based new beneficiary registration preview.
    1. Accept transcript + beneficiary_type + language
    2. Translate if needed
    3. LLM-extract structured beneficiary data based on category
    4. Validate mandatory fields & consistency using category rules
    5. Check for duplicates
    6. Return extracted data + duplicate warning + missing fields
    NOTE: Does NOT generate Beneficiary ID and does NOT save to MongoDB.
    """
    from services.groq_service import groq_service
    
    transcript = request.data.get("transcript", "").strip()
    beneficiary_type = (request.data.get("beneficiary_type") or request.data.get("category") or "pregnant_woman").strip().lower()
    language = request.data.get("language", "en")
    
    if not transcript:
        return Response({"error": "Transcript is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    if beneficiary_type not in VALID_CATEGORIES:
        return Response(
            {"error": f"Invalid category '{beneficiary_type}'. Allowed: {VALID_CATEGORIES}"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Translate to English if needed
    english_transcript = transcript
    if language != 'en':
        try:
            english_transcript = groq_service.translate_to_english(transcript, language)
        except Exception as e:
            logger.warning(f"Translation failed, using original: {e}")
    
    # LLM extraction tailored to category
    try:
        extracted = groq_service.extract_beneficiary_registration(english_transcript, beneficiary_type)
    except Exception as e:
        return Response({"error": f"Extraction failed: {type(e).__name__}: {str(e)}"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    # Do NOT generate Beneficiary ID in preview (only generated after final confirmation)
    extracted["beneficiary_id"] = None
    
    # Category-based validation
    val_res = validate_beneficiary_data(beneficiary_type, extracted, check_mother_exists=True)
    
    # Duplicate check across name, phone, mother_beneficiary_id, address
    duplicate_warning = None
    name = str(extracted.get("name") or extracted.get("baby_name") or extracted.get("child_name") or "").strip()
    phone = str(extracted.get("phone") or "").strip()
    mother_id = str(extracted.get("mother_beneficiary_id") or "").strip().upper()

    if name or phone:
        name_lower = name.lower()
        existing = mongodb_service.find_all("beneficiaries", {"is_deleted": {"$ne": True}}, limit=500)
        for b in existing:
            existing_name = str(b.get("name") or "").lower().strip()
            existing_phone = str(b.get("phone") or "").strip()
            existing_mother = str(b.get("mother_beneficiary_id") or "").strip().upper()

            name_match = bool(name and existing_name and (name_lower == existing_name or (len(name_lower) > 3 and name_lower in existing_name) or (len(existing_name) > 3 and existing_name in name_lower)))
            phone_match = bool(phone and existing_phone and phone == existing_phone)
            mother_match = bool(mother_id and existing_mother and mother_id == existing_mother)

            if phone_match or (name_match and (phone_match or mother_match or b.get("village") == extracted.get("village"))):
                duplicate_warning = {
                    "existing_id": b.get("beneficiary_id"),
                    "existing_name": b.get("name"),
                    "existing_village": b.get("village", ""),
                    "existing_category": b.get("beneficiary_type", ""),
                    "phone_match": phone_match,
                    "message": f"Possible duplicate found: '{b.get('name')}' (ID: {b.get('beneficiary_id')}). Please verify identity."
                }
                break

    return Response({
        "beneficiary_id": None,
        "extracted": val_res["sanitized_data"],
        "english_transcript": english_transcript,
        "beneficiary_type": beneficiary_type,
        "missing_mandatory": val_res["missing_mandatory"],
        "validation_errors": val_res["validation_errors"],
        "inconsistencies": val_res["inconsistencies"],
        "is_ready": val_res["is_valid"],
        "duplicate_warning": duplicate_warning,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def beneficiary_check_duplicate(request):
    """Check if a beneficiary with given name/phone/mother_id already exists."""
    name = request.data.get("name", "").strip()
    phone = request.data.get("phone", "").strip()
    mother_id = request.data.get("mother_beneficiary_id", "").strip().upper()
    dob = request.data.get("dob", "").strip()
    
    if not name and not phone and not mother_id:
        return Response({"error": "name, phone, or mother_beneficiary_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    existing = mongodb_service.find_all("beneficiaries", {"is_deleted": {"$ne": True}}, limit=500)
    matches = []
    
    name_lower = name.lower() if name else ""
    for b in existing:
        en = str(b.get("name") or "").lower().strip()
        ep = str(b.get("phone") or "").strip()
        em = str(b.get("mother_beneficiary_id") or "").strip().upper()
        edob = str(b.get("dob") or "").strip()

        name_match = bool(name_lower and (en == name_lower or (len(en) > 3 and en in name_lower) or (len(name_lower) > 3 and name_lower in en)))
        phone_match = bool(phone and ep and phone == ep)
        mother_match = bool(mother_id and em and mother_id == em)
        dob_match = bool(dob and edob and dob == edob)

        if name_match or phone_match or (mother_match and name_match):
            matches.append({
                "beneficiary_id": b.get("beneficiary_id"),
                "name": b.get("name"),
                "village": b.get("village", ""),
                "phone": b.get("phone", ""),
                "beneficiary_type": b.get("beneficiary_type", ""),
                "name_match": name_match,
                "phone_match": phone_match,
                "mother_match": mother_match,
                "dob_match": dob_match,
            })
    
    return Response({"duplicates": matches, "count": len(matches)})


@api_view(["POST"])
@permission_classes([AllowAny])
def beneficiary_extract_field(request):
    """
    Extract a single field from a short speech answer.
    Normalizes dates to YYYY-MM-DD, numbers to int/float, etc.
    """
    from services.beneficiary_validation_service import normalize_date_string
    import re
    
    field = request.data.get("field", "").strip()
    transcript = request.data.get("transcript", "").strip()
    category = request.data.get("category", "").strip()
    language = request.data.get("language", "en")
    
    if not field or not transcript:
        return Response({"error": "field and transcript are required"}, status=status.HTTP_400_BAD_REQUEST)
        
    extracted_val = None
    target_field = field

    # Maternal reference: determine if it's ID or name
    if field in ("maternal_reference", "mother_reference"):
        id_match = re.search(r"\b(PREG|BEN)[-_ ]?(\d+)\b", transcript, re.I)
        if id_match:
            prefix = id_match.group(1).upper()
            num = id_match.group(2)
            if prefix == "PREG":
                extracted_val = f"PREG-{num.zfill(6)}"
            else:
                extracted_val = f"BEN{num.zfill(3)}"
            target_field = "mother_beneficiary_id"
        else:
            cleaned = re.sub(r"^(mother('s)?\s*(name|id)?\s*(is)?\s*)", "", transcript, flags=re.I).strip()
            extracted_val = cleaned or transcript
            target_field = "mother_name"
        return Response({
            "field": target_field,
            "value": extracted_val,
            "raw_transcript": transcript
        })
    
    # Date fields
    if field in ("lmp", "edd", "expected_delivery_date", "dob", "date_of_birth"):
        def_yr = (datetime.now().year + 1) if field in ("edd", "expected_delivery_date") else None
        extracted_val = normalize_date_string(transcript, default_year=def_yr)
        if not extracted_val:
            try:
                from services.groq_service import groq_service
                res = groq_service.chat(
                    messages=[
                        {"role": "system", "content": f"Extract ONLY the date in YYYY-MM-DD format for {field}. Current year is 2026. If year not mentioned for EDD, use 2027. Return JSON: {{\"value\": \"YYYY-MM-DD\"}}"},
                        {"role": "user", "content": f"Speech: {transcript}"}
                    ],
                    max_tokens=60
                )
                import json
                parsed = json.loads(res)
                extracted_val = normalize_date_string(parsed.get("value"))
            except Exception:
                pass
        # Never return invalid non-date text into a date field
        return Response({
            "field": target_field,
            "value": extracted_val,
            "raw_transcript": transcript
        })
                
    # Integer fields
    elif field in ("age", "gestational_age_weeks", "gravida", "previous_pregnancies", "previous_live_births", "pregnancy_month"):
        nums = re.findall(r"\b\d+\b", transcript)
        if nums:
            extracted_val = int(nums[0])
            
    # Float fields
    elif field in ("birth_weight_kg", "birth_weight", "weight_kg"):
        nums = re.findall(r"\b\d+(?:\.\d+)?\b", transcript)
        if nums:
            extracted_val = float(nums[0])
            
    # Blood group
    elif field == "blood_group":
        bg_match = re.search(r"\b(A|B|AB|O)\s*(\+|\-|positive|negative)\b", transcript, re.I)
        if bg_match:
            grp = bg_match.group(1).upper()
            sign = "+" if ("+" in bg_match.group(2) or "pos" in bg_match.group(2).lower()) else "-"
            extracted_val = f"{grp}{sign}"
        elif "unknown" in transcript.lower():
            extracted_val = "Unknown"
            
    # Status / select fields
    elif field == "pregnancy_registration_status":
        t_low = transcript.lower()
        if "reg" in t_low or "complete" in t_low or "yes" in t_low:
            extracted_val = "registered"
        else:
            extracted_val = "pending"
            
    elif field == "gender":
        t_low = transcript.lower()
        if "female" in t_low or "girl" in t_low or "woman" in t_low:
            extracted_val = "female"
        elif "male" in t_low or "boy" in t_low or "man" in t_low:
            extracted_val = "male"
        else:
            extracted_val = "other"
            
    elif field == "immunization_card_status":
        t_low = transcript.lower()
        if "yes" in t_low or "avail" in t_low:
            extracted_val = "yes"
        elif "no" in t_low or "not" in t_low:
            extracted_val = "no"
        else:
            extracted_val = "unknown"
            
    elif field == "previous_complications":
        t_low = transcript.lower()
        if any(w in t_low for w in ("no", "none", "nil", "false", "nothing", "na")):
            extracted_val = "None reported"
        elif "unknown" in t_low:
            extracted_val = "Unknown"
        else:
            extracted_val = transcript
            
    # Text fields: clean up common voice prefixes
    else:
        cleaned = re.sub(r"^(her|his|the|my)?\s*(name|address|household|phone|category)\s*(is)?\s*", "", transcript, flags=re.I).strip()
        extracted_val = cleaned or transcript
        
    return Response({
        "field": target_field,
        "value": extracted_val if extracted_val is not None else transcript,
        "raw_transcript": transcript
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def beneficiary_lookup(request, beneficiary_id):
    """
    Lookup for revisit identity verification.
    Matches by Beneficiary ID (case-insensitive) or by Name!
    """
    import re
    query_id = beneficiary_id.strip()
    beneficiary = mongodb_service.find_one("beneficiaries", {
        "$or": [
            {"beneficiary_id": query_id.upper()},
            {"name": {"$regex": f"^{re.escape(query_id)}$", "$options": "i"}},
        ],
        "is_deleted": {"$ne": True},
    })
    if not beneficiary:
        # Also try partial name search
        all_b = mongodb_service.find_all("beneficiaries", {"is_deleted": {"$ne": True}})
        for b in all_b:
            if query_id.lower() in b.get("name", "").lower() or query_id.upper() in b.get("beneficiary_id", "").upper():
                beneficiary = b
                break
                
    if not beneficiary:
        return Response({
            "found": False,
            "beneficiary_id": query_id,
            "message": f"No active beneficiary found with ID or name '{query_id}'",
        }, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        "found": True,
        "beneficiary": beneficiary,
    })
