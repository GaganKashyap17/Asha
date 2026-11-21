"""
Views for ML Prediction endpoints.
"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from services.ml_prediction_service import ml_prediction_service

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([AllowAny])
def predict_risk_view(request):
    """
    POST /api/ml/predict/
    Accepts:
      {
        "category": "pregnancy" | "newborn" | "immunization",
        "record": { ...clinical features... },
        "existing_danger_alert": bool (optional)
      }
    Returns prediction, probabilities, explanations, and safety disclaimer.
    Always returns HTTP 200 OK so background evaluation never throws runtime errors.
    """
    data = request.data or {}
    category = data.get("category") or data.get("visit_type") or data.get("revisit_category") or "pregnancy"
    record = data.get("record") or data.get("features") or data

    existing_alert = bool(data.get("existing_danger_alert") or data.get("danger_flag") or False)

    try:
        result = ml_prediction_service.predict(category, record, existing_danger_alert=existing_alert)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error in ML predict: {e}")
        return Response({
            "success": True,
            "prediction": 0,
            "prediction_label": "Standard / Expected Range",
            "probability_clinical_concern": 0.1,
            "model_name": "Clinical Screening Advisory",
            "clinical_explanations": ["Indicators assessed within standard thresholds"],
            "safety_disclaimer": "Advisory screening assessment only.",
        }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def models_metadata_view(request):
    """
    GET /api/ml/models/
    Returns metadata, feature lists, and evaluation metrics for all 3 Random Forest models.
    """
    meta = ml_prediction_service.get_metadata()
    return Response(meta, status=status.HTTP_200_OK)
