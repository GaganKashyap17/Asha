from django.urls import path
from . import views

urlpatterns = [
    path('sessions/', views.create_session, name='voice-session-create'),
    path('transcribe/', views.transcribe_audio, name='voice-transcribe'),
]
