"""
Atomic and Unique Category-Based Beneficiary ID Generation for ASHA Voice.

Category Prefixes:
- pregnant_woman      -> PREG-000001
- newborn             -> NEWB-000001
- immunization_child  -> IMM-000001
- other               -> BEN-000001
"""
import re
import threading
from typing import Dict
from services.mongodb_service import mongodb_service

_lock = threading.Lock()

PREFIX_MAP: Dict[str, str] = {
    "pregnant_woman": "PREG-",
    "newborn": "NEWB-",
    "immunization_child": "IMM-",
    "other": "BEN-",
}


def generate_category_beneficiary_id(category: str) -> str:
    """
    Generate unique sequential Beneficiary ID for a category.
    Thread-safe with global lock to prevent concurrency races.
    """
    prefix = PREFIX_MAP.get(category, "BEN-")
    
    with _lock:
        all_records = mongodb_service.find_all("beneficiaries", limit=5000)
        max_num = 0

        # Pattern matches PREFIX followed by digits
        pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
        legacy_pattern = re.compile(r"^BEN(\d+)$") if prefix == "BEN-" else None

        for b in all_records:
            bid = str(b.get("beneficiary_id") or "").strip().upper()
            m = pattern.match(bid)
            if m:
                try:
                    num = int(m.group(1))
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
            elif legacy_pattern:
                # Support legacy BEN001 format
                lm = legacy_pattern.match(bid)
                if lm:
                    try:
                        num = int(lm.group(1))
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        pass

        next_num = max_num + 1
        new_id = f"{prefix}{next_num:06d}"
        return new_id
