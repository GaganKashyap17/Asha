"""Tests for extraction service and Pydantic schema."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.extraction_service import VisitRecord


class TestVisitRecordSchema:
    def test_valid_record(self):
        record = VisitRecord(
            beneficiary_name="Lakshmi",
            visit_type="pregnancy",
            pregnancy_month=7,
            weight_kg=2.8,
            confidence_score=0.9,
        )
        assert record.beneficiary_name == "Lakshmi"
        assert record.weight_kg == 2.8
        assert record.pregnancy_month == 7

    def test_decimal_preservation(self):
        record = VisitRecord(visit_type="newborn", weight_kg=2.8)
        assert record.weight_kg == 2.8

    def test_null_handling(self):
        record = VisitRecord(visit_type="household")
        assert record.beneficiary_name is None
        assert record.weight_kg is None
        assert record.pregnancy_month is None
        assert record.confirmation_status == "pending"

    def test_date_validation_valid(self):
        record = VisitRecord(visit_type="pregnancy", visit_date="2026-12-02")
        assert record.visit_date == "2026-12-02"

    def test_date_validation_invalid(self):
        record = VisitRecord(visit_type="pregnancy", visit_date="invalid-date")
        assert record.visit_date is None

    def test_visit_type_validation(self):
        record = VisitRecord(visit_type="invalid_type")
        assert record.visit_type == "household"

    def test_weight_out_of_range(self):
        record = VisitRecord(visit_type="pregnancy", weight_kg=500.0)
        assert record.weight_kg is None

    def test_pregnancy_month_range(self):
        record = VisitRecord(visit_type="pregnancy", pregnancy_month=12)
        assert record.pregnancy_month is None

    def test_confidence_score_bounds(self):
        record = VisitRecord(visit_type="pregnancy", confidence_score=0.95)
        assert record.confidence_score == 0.95

    def test_defaults(self):
        record = VisitRecord(visit_type="household")
        assert record.danger_flag == False
        assert record.vaccinations == []
        assert record.missing_fields == []
