from django.urls import path
from . import views
from . import gnani_views

urlpatterns = [
    # Existing Groq/Voice Session endpoints (strictly preserved)
    path('sessions/', views.create_session, name='voice-session-create'),
    path('transcribe/', views.transcribe_audio, name='voice-transcribe'),

    # New Isolated Gnani API Platform endpoints
    path('gnani/status/', gnani_views.gnani_status, name='gnani-status'),
    path('gnani/tts/', gnani_views.gnani_tts, name='gnani-tts'),
    path('gnani/translate/', gnani_views.gnani_translate, name='gnani-translate'),
    path('gnani/transcribe/', gnani_views.gnani_transcribe, name='gnani-transcribe'),
]

