from django.urls import path
from .consumers import TranslationConsumer
from session_manager.consumers import SessionConsumer

websocket_urlpatterns = [
    # Original one-to-one translation
    path('ws/translate/', TranslationConsumer.as_asgi()),
    
    # Session-based multi-receiver translation
    path('ws/session/<str:room_code>/', SessionConsumer.as_asgi()),
]