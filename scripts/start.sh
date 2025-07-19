#!/bin/bash
# Start AI Social Media Creator Services

echo "🚀 Starting AI Social Media Creator..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

# Start backend service
echo "🔧 Starting backend service..."
systemctl start ai-social-creator-backend

# Start frontend service
echo "🎨 Starting frontend service..."
systemctl start ai-social-creator-frontend

# Wait a moment for services to start
sleep 3

# Check service status
echo ""
echo "📊 Service Status:"
echo "=================="

if systemctl is-active --quiet ai-social-creator-backend; then
    echo "✅ Backend service is running"
else
    echo "❌ Backend service failed to start"
    systemctl status ai-social-creator-backend --no-pager -l
fi

if systemctl is-active --quiet ai-social-creator-frontend; then
    echo "✅ Frontend service is running"
else
    echo "❌ Frontend service failed to start"
    systemctl status ai-social-creator-frontend --no-pager -l
fi

echo ""
echo "🌐 Application URLs:"
echo "==================="
echo "Frontend: http://localhost:3089"
echo "API: http://localhost:3089/api"
echo "Health: http://localhost:3089/health"
echo ""
echo "✅ Services started successfully!"

