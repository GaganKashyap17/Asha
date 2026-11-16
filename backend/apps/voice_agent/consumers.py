"""WebSocket consumer for voice session state updates."""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class VoiceSessionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.room_group_name = f"voice_{self.session_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({
            "type": "session_connected",
            "session_id": self.session_id,
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "session_update", "data": data},
        )

    async def session_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))
