from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/voice/(?P<session_id>[\w-]+)/$", consumers.VoiceSessionConsumer.as_asgi()),
]
