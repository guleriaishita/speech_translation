import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'speech_translator.settings')

django_asgi_app = get_asgi_application()

# Import after Django setup
from realtime_handler.routing import websocket_urlpatterns
from realtime_handler.middleware import WebSocketRateLimitMiddleware

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        WebSocketRateLimitMiddleware(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        )
    ),
})