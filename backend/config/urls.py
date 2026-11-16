"""
URL configuration for ASHA Voice backend.
"""
from django.urls import path, include

urlpatterns = [
    path('api/accounts/', include('apps.accounts.urls')),
    path('api/beneficiaries/', include('apps.beneficiaries.urls')),
    path('api/visits/', include('apps.visits.urls')),
    path('api/voice/', include('apps.voice_agent.urls')),
    path('api/followups/', include('apps.followups.urls')),
    path('api/alerts/', include('apps.danger_alerts.urls')),
    path('api/analytics/', include('apps.analytics.urls')),
]
