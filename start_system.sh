#!/bin/bash

# Speech Translation System - Startup Script
# Run all required services for the application

echo "🚀 Starting Speech Translation System..."
echo ""

# Check if required services are running
echo "Checking prerequisites..."

# Check Redis
if ! pgrep -x "redis-server" > /dev/null; then
    echo "⚠️  Redis is not running. Please start it with: redis-server"
    echo ""
fi

# Function to check if a port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 0
    else
        return 1
    fi
}

# Start services in separate terminal tabs/windows (manual step)
echo "📋 To run the system, open 4 terminals and run:"
echo ""
echo "Terminal 1 - Redis (if not running as service):"
echo "  redis-server"
echo ""
echo "Terminal 2 - Celery Worker:"
echo "  cd $(pwd)"
echo "  celery -A speech_translator worker -l info"
echo ""
echo "Terminal 3 - Django ASGI Server (for WebSockets):"
echo "  cd $(pwd)"
echo "  daphne -b 0.0.0.0 -p 8000 speech_translator.asgi:application"
echo ""
echo "Terminal 4 - React Frontend:"
echo "  cd $(pwd)/frontend"
echo "  npm run dev"
echo ""
echo "⚡ IMPORTANT: Use 'daphne' instead of 'python manage.py runserver' for WebSocket support!"
echo ""
echo "Once all services are running, access the application at:"
echo "  http://localhost:3000"
echo ""
