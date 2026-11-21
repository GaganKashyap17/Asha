"""
Serializers for IVR Reminder Service.
"""
import re
from rest_framework import serializers


class IVRInitiateSerializer(serializers.Serializer):
    beneficiary_name = serializers.CharField(max_length=150, required=True)
    mobile_number = serializers.CharField(max_length=25, required=True)
    visit_date = serializers.CharField(max_length=30, required=True)
    visit_type = serializers.CharField(max_length=150, required=True)
    language = serializers.ChoiceField(
        choices=["en", "hi", "ta", "kn"],
        default="en",
        required=False
    )
    followup_id = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    beneficiary_id = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")

    def validate_mobile_number(self, value):
        cleaned = re.sub(r"\D", "", value)
        if len(cleaned) < 10:
            raise serializers.ValidationError("Mobile number must contain at least 10 digits.")
        # If 12 digits starting with 91, extract the 10-digit number
        if len(cleaned) == 12 and cleaned.startswith("91"):
            cleaned = cleaned[2:]
        return cleaned


class IVRCallRecordSerializer(serializers.Serializer):
    call_id = serializers.CharField()
    beneficiary_name = serializers.CharField()
    mobile_number = serializers.CharField()
    visit_date = serializers.CharField()
    visit_type = serializers.CharField()
    language = serializers.CharField()
    reminder_message = serializers.CharField()
    status = serializers.CharField()
    outcome = serializers.CharField()
    initiated_at = serializers.CharField()
    completed_at = serializers.CharField(allow_null=True)
    duration_seconds = serializers.IntegerField()
    followup_id = serializers.CharField(allow_blank=True, required=False)
    beneficiary_id = serializers.CharField(allow_blank=True, required=False)
    is_demo = serializers.BooleanField(default=True)
