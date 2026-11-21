"""
IVR API Views for ASHA Voice.
Unified Django REST Framework views for the integrated IVR subsystem.
"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .serializers import IVRInitiateSerializer
from .services import ivr_service

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def ivr_status(request):
    """Return status and configuration details for the IVR reminder service."""
    status_data = ivr_service.get_status()
    return Response(status_data)


@api_view(["GET"])
@permission_classes([AllowAny])
def ivr_beneficiaries(request):
    """
    Return list of beneficiaries scheduled for revisit reminders.
    Supports query param ?tomorrow_only=false to fetch all scheduled revisits.
    """
    tomorrow_param = request.query_params.get("tomorrow_only", "true").lower()
    tomorrow_only = tomorrow_param not in ["false", "0", "no"]

    results = ivr_service.get_beneficiaries(tomorrow_only=tomorrow_only)
    return Response({
        "results": results,
        "count": len(results),
        "tomorrow_only": tomorrow_only,
        "demo": True,
        "note": "Beneficiary records retrieved from MongoDB with simulated telephony integration.",
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def ivr_initiate(request):
    """
    Initiate an IVR reminder call for a scheduled revisit.
    Validates mobile number, checks 24h duplication, and logs the call record in MongoDB.
    """
    serializer = IVRInitiateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"error": "Validation failed", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = ivr_service.initiate_call(serializer.validated_data)

    if result.get("is_duplicate"):
        return Response(
            {
                "error": result.get("error"),
                "message": result.get("message"),
                "existing_call": result.get("existing_call"),
            },
            status=status.HTTP_409_CONFLICT,
        )

    return Response(result, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def ivr_history(request):
    """Return past IVR reminder calls, newest first."""
    limit = int(request.query_params.get("limit", 100))
    calls = ivr_service.get_history(limit=limit)
    return Response({
        "results": calls,
        "count": len(calls),
        "demo": True,
        "note": "Integrated call history stored in MongoDB Atlas / in-memory store.",
    })
