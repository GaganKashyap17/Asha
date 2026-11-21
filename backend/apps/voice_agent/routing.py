from django.urls import re_path
from . import consumers
from . import gnani_consumer

websocket_urlpatterns = [
    # Existing voice session websocket (preserved)
    re_path(r"ws/voice/(?P<session_id>[\w-]+)/$", consumers.VoiceSessionConsumer.as_asgi()),

    # New Gnani Prisma v3.0 real-time streaming WebSocket
    re_path(r"ws/gnani/stream/$", gnani_consumer.GnaniStreamConsumer.as_asgi()),
]

