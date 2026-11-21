"""
URL configuration for ASHA Voice backend.
"""
from django.urls import path, include
from django.http import JsonResponse
import sys
from pathlib import Path

# Ensure project root is in sys.path so ivr_prototype is importable
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

def api_root(request):
    return JsonResponse({
        "status": "online",
        "service": "ASHA Voice Backend API",
        "message": "Backend server is running properly. Open the frontend UI at http://localhost:5173",
        "endpoints": [
            "/api/accounts/",
            "/api/beneficiaries/",
            "/api/visits/",
            "/api/voice/",
            "/api/followups/",
            "/api/alerts/",
            "/api/analytics/",
            "/api/ml/",
            "/api/ivr/",
        ]
    })

urlpatterns = [
    path('', api_root, name='root'),
    path('api/', api_root, name='api-root'),
    path('api/accounts/', include('apps.accounts.urls')),
    path('api/beneficiaries/', include('apps.beneficiaries.urls')),
    path('api/visits/', include('apps.visits.urls')),
    path('api/voice/', include('apps.voice_agent.urls')),
    path('api/followups/', include('apps.followups.urls')),
    path('api/alerts/', include('apps.danger_alerts.urls')),
    path('api/analytics/', include('apps.analytics.urls')),
    path('api/ml/', include('apps.ml.urls')),
    path('api/ivr/', include('ivr_prototype.backend.ivr_urls')),
]
