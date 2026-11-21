"""
URL configuration for ASHA Voice backend.
"""
from django.urls import path, include
from django.http import JsonResponse

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
]
