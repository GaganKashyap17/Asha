from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    worker_id = serializers.CharField(max_length=20)
    password = serializers.CharField(max_length=128, write_only=True)


class UserSerializer(serializers.Serializer):
    worker_id = serializers.CharField()
    name = serializers.CharField()
    district = serializers.CharField()
    sub_district = serializers.CharField()
    village = serializers.CharField()
    phone = serializers.CharField()
    language = serializers.CharField()
    role = serializers.CharField()
