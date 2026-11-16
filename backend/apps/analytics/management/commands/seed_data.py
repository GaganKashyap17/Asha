"""Seed synthetic demo data into MongoDB."""
import sys
import os
import hashlib
import logging
from datetime import datetime, timezone, timedelta

# Ensure backend root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from django.core.management.base import BaseCommand
from services.mongodb_service import mongodb_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Seed synthetic demo data for ASHA Voice."

    def handle(self, *args, **options):
        self.stdout.write("Connecting to database...")
        connected = mongodb_service.connect()
        mode = "MongoDB Atlas" if connected else "In-memory"
        self.stdout.write(f"Database mode: {mode}")

        self._seed_users()
        self._seed_beneficiaries()
        self._seed_visits()
        self._seed_followups()
        self._seed_danger_alerts()

        self.stdout.write(self.style.SUCCESS("Seed data created successfully!"))

    def _seed_users(self):
        users = [
            {"worker_id": "ASHA001", "name": "Priya Sundaram", "district": "Chennai", "phc": "Tambaram PHC", "language": "ta", "password_hash": hashlib.sha256("demo123".encode()).hexdigest()},
            {"worker_id": "ASHA002", "name": "Meena Krishnan", "district": "Coimbatore", "phc": "Singanallur PHC", "language": "ta", "password_hash": hashlib.sha256("demo123".encode()).hexdigest()},
            {"worker_id": "ASHA003", "name": "Lakshmi Rajan", "district": "Madurai", "phc": "Thirunagar PHC", "language": "ta", "password_hash": hashlib.sha256("demo123".encode()).hexdigest()},
            {"worker_id": "ASHA004", "name": "Kavitha Murugan", "district": "Salem", "phc": "Hasthampatti PHC", "language": "ta", "password_hash": hashlib.sha256("demo123".encode()).hexdigest()},
            {"worker_id": "ASHA005", "name": "Revathi Natarajan", "district": "Trichy", "phc": "Srirangam PHC", "language": "ta", "password_hash": hashlib.sha256("demo123".encode()).hexdigest()},
        ]
        for u in users:
            if not mongodb_service.find_one("users", {"worker_id": u["worker_id"]}):
                mongodb_service.insert("users", u)
        self.stdout.write(f"  Users: {len(users)} seeded")

    def _seed_beneficiaries(self):
        today = datetime.now(timezone.utc).date()
        beneficiaries = [
            {"beneficiary_id": "BEN001", "name": "Lakshmi", "age": 24, "gender": "female", "village": "Tambaram", "household": "House 12, Gandhi Street", "phone": "9876543210", "pregnancy_status": "pregnant", "pregnancy_month": 7, "expected_delivery_date": "2027-01-15", "last_visit_date": today.isoformat(), "next_visit_date": (today + timedelta(days=14)).isoformat()},
            {"beneficiary_id": "BEN002", "name": "Meena", "age": 22, "gender": "female", "village": "Tambaram", "household": "House 5, Nehru Road", "phone": "9876543211", "pregnancy_status": "postnatal", "newborn_age_days": 14, "last_visit_date": (today - timedelta(days=3)).isoformat(), "next_visit_date": (today + timedelta(days=4)).isoformat()},
            {"beneficiary_id": "BEN003", "name": "Kavitha", "age": 28, "gender": "female", "village": "Chromepet", "household": "House 8, Main Road", "phone": "9876543212", "pregnancy_status": "pregnant", "pregnancy_month": 5, "expected_delivery_date": "2027-03-20"},
            {"beneficiary_id": "BEN004", "name": "Revathi", "age": 20, "gender": "female", "village": "Pallavaram", "household": "House 3, Temple Street", "phone": "9876543213", "pregnancy_status": "not_pregnant"},
            {"beneficiary_id": "BEN005", "name": "Saranya", "age": 26, "gender": "female", "village": "Tambaram", "household": "House 22, Lake View", "phone": "9876543214", "pregnancy_status": "pregnant", "pregnancy_month": 3},
            {"beneficiary_id": "BEN006", "name": "Divya", "age": 30, "gender": "female", "village": "Chromepet", "household": "House 15, Park Lane", "phone": "9876543215", "pregnancy_status": "postnatal", "newborn_age_days": 28},
            {"beneficiary_id": "BEN007", "name": "Anitha", "age": 19, "gender": "female", "village": "Pallavaram", "household": "House 7, Bus Stand Road", "phone": "9876543216", "pregnancy_status": "not_pregnant"},
            {"beneficiary_id": "BEN008", "name": "Priya", "age": 25, "gender": "female", "village": "Tambaram", "household": "House 9, School Street", "phone": "9876543217", "pregnancy_status": "pregnant", "pregnancy_month": 8, "expected_delivery_date": "2026-12-25"},
            {"beneficiary_id": "BEN009", "name": "Deepa", "age": 23, "gender": "female", "village": "Chromepet", "household": "House 11, Market Lane", "phone": "9876543218", "pregnancy_status": "not_pregnant"},
            {"beneficiary_id": "BEN010", "name": "Vani", "age": 27, "gender": "female", "village": "Pallavaram", "household": "House 4, River Road", "phone": "9876543219", "pregnancy_status": "postnatal", "newborn_age_days": 7},
        ]
        for b in beneficiaries:
            if not mongodb_service.find_one("beneficiaries", {"beneficiary_id": b["beneficiary_id"]}):
                mongodb_service.insert("beneficiaries", b)
        self.stdout.write(f"  Beneficiaries: {len(beneficiaries)} seeded")

    def _seed_visits(self):
        today = datetime.now(timezone.utc).date()
        visits = [
            {"beneficiary_id": "BEN001", "beneficiary_name": "Lakshmi", "visit_type": "pregnancy", "visit_date": today.isoformat(), "pregnancy_month": 7, "weight_kg": 62.5, "anc_completed": True, "ifa_given": True, "vaccinations": ["TT1"], "danger_signs": [], "danger_flag": False, "next_visit_date": (today + timedelta(days=14)).isoformat(), "confirmation_status": "confirmed", "confidence_score": 0.95, "raw_transcript": "Lakshmi pregnancy 7 months weight 62.5 ANC done IFA given"},
            {"beneficiary_id": "BEN001", "beneficiary_name": "Lakshmi", "visit_type": "pregnancy", "visit_date": (today - timedelta(days=14)).isoformat(), "pregnancy_month": 6, "weight_kg": 61.0, "anc_completed": True, "ifa_given": True, "vaccinations": [], "danger_signs": [], "danger_flag": False, "confirmation_status": "confirmed", "confidence_score": 0.92},
            {"beneficiary_id": "BEN002", "beneficiary_name": "Meena", "visit_type": "newborn", "visit_date": (today - timedelta(days=3)).isoformat(), "weight_kg": 2.8, "danger_signs": [], "danger_flag": False, "confirmation_status": "confirmed", "confidence_score": 0.88},
            {"beneficiary_id": "BEN002", "beneficiary_name": "Meena", "visit_type": "postnatal", "visit_date": (today - timedelta(days=10)).isoformat(), "weight_kg": 55.0, "danger_signs": [], "danger_flag": False, "confirmation_status": "confirmed", "confidence_score": 0.90},
            {"beneficiary_id": "BEN003", "beneficiary_name": "Kavitha", "visit_type": "pregnancy", "visit_date": (today - timedelta(days=7)).isoformat(), "pregnancy_month": 5, "weight_kg": 58.0, "anc_completed": True, "ifa_given": False, "confirmation_status": "confirmed", "confidence_score": 0.85},
            {"beneficiary_id": "BEN004", "beneficiary_name": "Revathi", "visit_type": "immunisation", "visit_date": (today - timedelta(days=2)).isoformat(), "vaccinations": ["OPV1", "Pentavalent1"], "danger_signs": [], "danger_flag": False, "confirmation_status": "confirmed", "confidence_score": 0.93},
            {"beneficiary_id": "BEN005", "beneficiary_name": "Saranya", "visit_type": "pregnancy", "visit_date": (today - timedelta(days=5)).isoformat(), "pregnancy_month": 3, "weight_kg": 52.0, "anc_completed": True, "confirmation_status": "confirmed", "confidence_score": 0.87},
            {"beneficiary_id": "BEN006", "beneficiary_name": "Divya", "visit_type": "newborn", "visit_date": (today - timedelta(days=1)).isoformat(), "weight_kg": 3.2, "confirmation_status": "confirmed", "confidence_score": 0.91},
            {"beneficiary_id": "BEN007", "beneficiary_name": "Anitha", "visit_type": "household", "visit_date": (today - timedelta(days=4)).isoformat(), "confirmation_status": "confirmed", "confidence_score": 0.80},
            {"beneficiary_id": "BEN008", "beneficiary_name": "Priya", "visit_type": "pregnancy", "visit_date": (today - timedelta(days=6)).isoformat(), "pregnancy_month": 8, "weight_kg": 65.0, "anc_completed": True, "ifa_given": True, "confirmation_status": "confirmed", "confidence_score": 0.94},
            {"beneficiary_id": "BEN009", "beneficiary_name": "Deepa", "visit_type": "immunisation", "visit_date": (today - timedelta(days=8)).isoformat(), "vaccinations": ["BCG", "OPV0"], "confirmation_status": "confirmed", "confidence_score": 0.89},
            {"beneficiary_id": "BEN010", "beneficiary_name": "Vani", "visit_type": "newborn", "visit_date": (today - timedelta(days=2)).isoformat(), "weight_kg": 2.9, "confirmation_status": "confirmed", "confidence_score": 0.86},
            {"beneficiary_id": "BEN003", "beneficiary_name": "Kavitha", "visit_type": "pregnancy", "visit_date": (today - timedelta(days=21)).isoformat(), "pregnancy_month": 4, "weight_kg": 56.5, "anc_completed": True, "confirmation_status": "confirmed", "confidence_score": 0.82},
            {"beneficiary_id": "BEN005", "beneficiary_name": "Saranya", "visit_type": "household", "visit_date": (today - timedelta(days=15)).isoformat(), "confirmation_status": "confirmed", "confidence_score": 0.78},
            {"beneficiary_id": "BEN008", "beneficiary_name": "Priya", "visit_type": "pregnancy", "visit_date": (today - timedelta(days=20)).isoformat(), "pregnancy_month": 7, "weight_kg": 63.5, "confirmation_status": "confirmed", "confidence_score": 0.90},
            {"beneficiary_id": "BEN001", "beneficiary_name": "Lakshmi", "visit_type": "pregnancy", "visit_date": (today - timedelta(days=28)).isoformat(), "pregnancy_month": 5, "weight_kg": 59.5, "anc_completed": True, "confirmation_status": "confirmed", "confidence_score": 0.88},
            {"beneficiary_id": "BEN006", "beneficiary_name": "Divya", "visit_type": "postnatal", "visit_date": (today - timedelta(days=12)).isoformat(), "weight_kg": 53.0, "confirmation_status": "confirmed", "confidence_score": 0.84},
            {"beneficiary_id": "BEN010", "beneficiary_name": "Vani", "visit_type": "postnatal", "visit_date": (today - timedelta(days=5)).isoformat(), "weight_kg": 50.0, "confirmation_status": "confirmed", "confidence_score": 0.81},
            {"beneficiary_id": "BEN004", "beneficiary_name": "Revathi", "visit_type": "household", "visit_date": (today - timedelta(days=9)).isoformat(), "confirmation_status": "confirmed", "confidence_score": 0.79},
            {"beneficiary_id": "BEN007", "beneficiary_name": "Anitha", "visit_type": "immunisation", "visit_date": (today - timedelta(days=11)).isoformat(), "vaccinations": ["Measles1"], "confirmation_status": "confirmed", "confidence_score": 0.87},
        ]
        for v in visits:
            mongodb_service.insert("visits", v)
        self.stdout.write(f"  Visits: {len(visits)} seeded")

    def _seed_followups(self):
        today = datetime.now(timezone.utc).date()
        followups = [
            {"beneficiary_id": "BEN001", "beneficiary_name": "Lakshmi", "visit_type": "pregnancy", "due_date": (today + timedelta(days=14)).isoformat(), "priority": "high", "status": "pending", "notes": "ANC followup", "danger_flag": False},
            {"beneficiary_id": "BEN002", "beneficiary_name": "Meena", "visit_type": "newborn", "due_date": (today + timedelta(days=4)).isoformat(), "priority": "emergency", "status": "pending", "notes": "Newborn followup", "danger_flag": False},
            {"beneficiary_id": "BEN003", "beneficiary_name": "Kavitha", "visit_type": "pregnancy", "due_date": (today + timedelta(days=7)).isoformat(), "priority": "high", "status": "pending", "notes": "ANC followup — IFA not given last visit", "danger_flag": False},
            {"beneficiary_id": "BEN005", "beneficiary_name": "Saranya", "visit_type": "pregnancy", "due_date": (today - timedelta(days=2)).isoformat(), "priority": "high", "status": "pending", "notes": "OVERDUE — ANC followup", "danger_flag": False},
            {"beneficiary_id": "BEN010", "beneficiary_name": "Vani", "visit_type": "newborn", "due_date": (today + timedelta(days=1)).isoformat(), "priority": "emergency", "status": "pending", "notes": "Newborn followup", "danger_flag": False},
        ]
        for f in followups:
            mongodb_service.insert("followups", f)
        self.stdout.write(f"  Followups: {len(followups)} seeded")

    def _seed_danger_alerts(self):
        alerts = [
            {"beneficiary_id": "BEN008", "beneficiary_name": "Priya", "visit_type": "pregnancy", "danger_signs": ["Severe headache"], "danger_details": [{"rule_id": "DS003", "name": "Severe headache or blurred vision", "severity": "emergency"}], "referral_status": "referred", "resolved": False, "created_at": "2026-11-14T10:00:00Z"},
            {"beneficiary_id": "BEN006", "beneficiary_name": "Divya", "danger_signs": ["Bleeding during pregnancy"], "danger_details": [{"rule_id": "DS001", "name": "Bleeding during pregnancy", "severity": "emergency"}], "referral_status": "pending", "resolved": False, "created_at": "2026-11-15T14:30:00Z"},
        ]
        for a in alerts:
            mongodb_service.insert("danger_alerts", a)
        self.stdout.write(f"  Danger alerts: {len(alerts)} seeded")
