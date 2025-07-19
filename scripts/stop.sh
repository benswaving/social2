#!/bin/bash
# Stop AI Social Media Creator Services

echo "🛑 Stopping AI Social Media Creator..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

# Stop frontend service
echo "🎨 Stopping frontend service..."
systemctl stop ai-social-creator-frontend

# Stop backend service
echo "🔧 Stopping backend service..."
systemctl stop ai-social-creator-backend

# Wait a moment for services to stop
sleep 2

# Check service status
echo ""
echo "📊 Service Status:"
echo "=================="

if systemctl is-active --quiet ai-social-creator-backend; then
    echo "⚠️  Backend service is still running"
else
    echo "✅ Backend service stopped"
fi

if systemctl is-active --quiet ai-social-creator-frontend; then
    echo "⚠️  Frontend service is still running"
else
    echo "✅ Frontend service stopped"
fi

echo ""
echo "✅ Services stopped successfully!"

