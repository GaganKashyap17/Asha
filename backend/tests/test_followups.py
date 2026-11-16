"""Tests for followup service."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.followup_service import followup_service, FOLLOWUP_RULES


class TestFollowupRules:
    def test_pregnancy_rule(self):
        rule = FOLLOWUP_RULES["pregnancy"]
        assert rule["interval_days"] == 14
        assert rule["priority"] == "high"

    def test_newborn_rule(self):
        rule = FOLLOWUP_RULES["newborn"]
        assert rule["interval_days"] == 3
        assert rule["priority"] == "emergency"

    def test_immunisation_rule(self):
        rule = FOLLOWUP_RULES["immunisation"]
        assert rule["interval_days"] == 30
