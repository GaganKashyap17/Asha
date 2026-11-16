"""Beneficiary CRUD views."""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from services.mongodb_service import mongodb_service

logger = logging.getLogger(__name__)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def beneficiary_list_create(request):
    if request.method == "GET":
        search = request.query_params.get("search", "")
        query = {}
        if search:
            query = {"name": {"$regex": search, "$options": "i"}} if mongodb_service.is_connected() else {}
        beneficiaries = mongodb_service.find_all("beneficiaries", query, limit=100)
        if search and not mongodb_service.is_connected():
            beneficiaries = [b for b in beneficiaries if search.lower() in b.get("name", "").lower()]
        return Response({"results": beneficiaries, "count": len(beneficiaries)})

    if request.method == "POST":
        data = request.data
        if not data.get("beneficiary_id") or not data.get("name"):
            return Response(
                {"error": "beneficiary_id and name are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        existing = mongodb_service.find_one("beneficiaries", {"beneficiary_id": data["beneficiary_id"]})
        if existing:
            return Response(
                {"error": "Beneficiary ID already exists"},
                status=status.HTTP_409_CONFLICT,
            )
        saved = mongodb_service.insert("beneficiaries", data)
        return Response(saved, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT"])
@permission_classes([AllowAny])
def beneficiary_detail(request, beneficiary_id):
    beneficiary = mongodb_service.find_one("beneficiaries", {"beneficiary_id": beneficiary_id})
    if not beneficiary:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        visits = mongodb_service.find_all("visits", {"beneficiary_id": beneficiary_id})
        beneficiary["visit_history"] = visits
        return Response(beneficiary)

    if request.method == "PUT":
        mongodb_service.update_one(
            "beneficiaries",
            {"beneficiary_id": beneficiary_id},
            {"$set": request.data},
        )
        updated = mongodb_service.find_one("beneficiaries", {"beneficiary_id": beneficiary_id})
        return Response(updated)
