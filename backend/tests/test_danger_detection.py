"""
Tests for danger sign detection engine — CRITICAL safety tests.
Missing a clearly spoken danger sign is a test failure.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.danger_detection_service import detect_danger_signs


class TestBleedingDetection:
    def test_positive_bleeding(self):
        results = detect_danger_signs("Patient is experiencing bleeding", "pregnancy")
        assert any(r.detected and r.rule_id == "DS001" for r in results)

    def test_english_bleeding(self):
        results = detect_danger_signs("Pregnant woman is experiencing bleeding", "pregnancy")
        assert any(r.detected and r.rule_id == "DS001" for r in results)

    def test_negated_bleeding(self):
        results = detect_danger_signs("Patient has no bleeding", "pregnancy")
        assert not any(r.detected and r.rule_id == "DS001" for r in results)

    def test_historical_bleeding(self):
        results = detect_danger_signs("History of bleeding in previous pregnancy", "pregnancy")
        assert not any(r.detected and r.rule_id == "DS001" for r in results)

    def test_hypothetical_bleeding(self):
        results = detect_danger_signs("If there is bleeding what should we do", "pregnancy")
        assert not any(r.detected and r.rule_id == "DS001" for r in results)

    def test_tamil_bleeding(self):
        results = detect_danger_signs("ரத்தப்போக்கு இருக்கிறது", "pregnancy")
        assert any(r.detected and r.rule_id == "DS001" for r in results)

    def test_codemix_bleeding(self):
        results = detect_danger_signs("Patient ku bleeding aaguthu", "pregnancy")
        assert any(r.detected and r.rule_id == "DS001" for r in results)

    def test_negated_flags_ambiguous(self):
        results = detect_danger_signs("No bleeding observed today", "pregnancy")
        matches = [r for r in results if r.rule_id == "DS001"]
        assert len(matches) > 0 and matches[0].is_negated

    def test_blood_keyword(self):
        results = detect_danger_signs("There is blood coming out", "pregnancy")
        assert any(r.detected and r.rule_id == "DS001" for r in results)


class TestNewbornFeverDetection:
    def test_newborn_fever(self):
        results = detect_danger_signs("The baby has high fever", "newborn")
        assert any(r.detected and r.rule_id == "DS002" for r in results)

    def test_negated_fever(self):
        results = detect_danger_signs("The baby has no fever", "newborn")
        assert not any(r.detected and r.rule_id == "DS002" for r in results)

    def test_fever_no_newborn_context(self):
        results = detect_danger_signs("Patient has fever", "pregnancy")
        assert not any(r.detected and r.rule_id == "DS002" for r in results)

    def test_fever_with_newborn_context_in_text(self):
        results = detect_danger_signs("The newborn has high fever and is not feeding well", "household")
        assert any(r.detected and r.rule_id == "DS002" for r in results)

    def test_tamil_fever_newborn(self):
        results = detect_danger_signs("குழந்தைக்கு காய்ச்சல் இருக்கிறது", "newborn")
        assert any(r.detected and r.rule_id == "DS002" for r in results)


class TestMultipleDangerSigns:
    def test_bleeding_and_fever(self):
        results = detect_danger_signs("Pregnant woman bleeding and newborn has fever", "pregnancy")
        ds001 = [r for r in results if r.rule_id == "DS001" and r.detected]
        assert len(ds001) > 0  # bleeding detected

    def test_no_danger_normal_visit(self):
        results = detect_danger_signs(
            "Lakshmi pregnancy 7 months weight 62 ANC done", "pregnancy"
        )
        detected = [r for r in results if r.detected]
        assert len(detected) == 0


class TestReferralMessages:
    def test_referral_message_present(self):
        results = detect_danger_signs("Bleeding during pregnancy", "pregnancy")
        confirmed = [r for r in results if r.detected]
        assert len(confirmed) > 0
        assert "PHC" in confirmed[0].referral_message_en
        assert confirmed[0].disclaimer != ""
