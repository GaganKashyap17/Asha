"""Beneficiary serializers (for request validation)."""
from rest_framework import serializers

class BeneficiarySerializer(serializers.Serializer):
    beneficiary_id = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=100)
    age = serializers.IntegerField(min_value=0, max_value=120, required=False)
    gender = serializers.CharField(max_length=10, default="female")
    village = serializers.CharField(max_length=100, required=False, default="")
    household = serializers.CharField(max_length=100, required=False, default="")
    phone = serializers.CharField(max_length=15, required=False, default="")
    pregnancy_status = serializers.ChoiceField(
        choices=["pregnant", "postnatal", "not_pregnant", "na"],
        default="na", required=False,
    )
    pregnancy_month = serializers.IntegerField(min_value=1, max_value=9, required=False, allow_null=True)
    expected_delivery_date = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    newborn_age_days = serializers.IntegerField(required=False, allow_null=True)
    last_visit_date = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    next_visit_date = serializers.CharField(required=False, allow_null=True, allow_blank=True)
