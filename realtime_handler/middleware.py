"""
Middleware for WebSocket rate limiting and connection management.
Tracks connections per IP and enforces limits.
"""

import logging
from channels.middleware import BaseMiddleware
from django.core.cache import cache


logger = logging.getLogger(__name__)


class WebSocketRateLimitMiddleware(BaseMiddleware):
    """
    Middleware to limit WebSocket connections per IP address.
    
    Tracks active connections in Redis/cache and enforces limits.
    """
    
    async def __call__(self, scope, receive, send):
        """
        Process WebSocket connection.
        
        Args:
            scope: Connection scope with client information
            receive: Receive function
            send: Send function
        """
        # Only apply to WebSocket connections
        if scope['type'] != 'websocket':
            return await super().__call__(scope, receive, send)
        
        # Get client IP address
        client_ip = self._get_client_ip(scope)
        
        # Check connection limit
        max_connections = int(
            # Use environment variable or default to 5
            cache.get('WS_MAX_CONNECTIONS_PER_IP', 5)
        )
        
        connection_key = f"ws_connections:{client_ip}"
        current_connections = cache.get(connection_key, 0)
        
        if current_connections >= max_connections:
            logger.warning(
                f"Connection limit exceeded for IP {client_ip}: "
                f"{current_connections}/{max_connections}"
            )
            
            # Reject connection
            await send({
                'type': 'websocket.close',
                'code': 1008,  # Policy violation
            })
            return
        
        # Increment connection count
        cache.set(connection_key, current_connections + 1, timeout=3600)
        
        logger.info(
            f"WebSocket connection from {client_ip}: "
            f"{current_connections + 1}/{max_connections}"
        )
        
        try:
            # Process the connection
            await super().__call__(scope, receive, send)
        finally:
            # Decrement connection count on disconnect
            current = cache.get(connection_key, 1)
            if current > 0:
                cache.set(connection_key, current - 1, timeout=3600)
                logger.info(
                    f"WebSocket disconnected from {client_ip}: "
                    f"{current - 1}/{max_connections}"
                )
    
    def _get_client_ip(self, scope) -> str:
        """
        Extract client IP address from connection scope.
        
        Args:
            scope: Connection scope
            
        Returns:
            Client IP address as string
        """
        # Check for forwarded IP (if behind proxy)
        headers = dict(scope.get('headers', []))
        
        # X-Forwarded-For header
        forwarded_for = headers.get(b'x-forwarded-for')
        if forwarded_for:
            # Take first IP if multiple
            ip = forwarded_for.decode().split(',')[0].strip()
            return ip
        
        # X-Real-IP header
        real_ip = headers.get(b'x-real-ip')
        if real_ip:
            return real_ip.decode().strip()
        
        # Fall back to direct client address
        client = scope.get('client')
        if client:
            return client[0]  # (host, port) tuple
        
        return 'unknown'
