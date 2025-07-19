#!/bin/bash
# Check AI Social Media Creator Status

echo "📊 AI Social Media Creator Status"
echo "================================="
echo ""

# Service status
echo "🔧 Backend Service Status:"
echo "-------------------------"
systemctl status ai-social-creator-backend --no-pager -l
echo ""

echo "🎨 Frontend Service Status:"
echo "--------------------------"
systemctl status ai-social-creator-frontend --no-pager -l
echo ""

# Port status
echo "🌐 Port Status:"
echo "--------------"
echo "Listening ports:"
netstat -tlnp | grep -E ":(3088|3089)" || echo "No services listening on ports 3088/3089"
echo ""

# Process status
echo "⚙️  Process Status:"
echo "------------------"
ps aux | grep -E "(gunicorn|nginx)" | grep -v grep || echo "No gunicorn or nginx processes found"
echo ""

# Disk usage
echo "💾 Disk Usage:"
echo "-------------"
df -h /var/www/ai-social-creator 2>/dev/null || echo "Application directory not found"
echo ""

# Memory usage
echo "🧠 Memory Usage:"
echo "---------------"
free -h
echo ""

# Test connectivity
echo "🌐 Connectivity Test:"
echo "--------------------"

# Test frontend
if curl -s http://localhost:3089/ > /dev/null 2>&1; then
    echo "✅ Frontend accessible at http://localhost:3089"
else
    echo "❌ Frontend not accessible"
fi

# Test API
if curl -s http://localhost:3089/api/health > /dev/null 2>&1; then
    echo "✅ API accessible at http://localhost:3089/api"
else
    echo "❌ API not accessible"
fi

# Test backend direct
if curl -s http://127.0.0.1:3088/api/health > /dev/null 2>&1; then
    echo "✅ Backend direct access working"
else
    echo "❌ Backend direct access not working"
fi

echo ""
echo "📋 Quick Commands:"
echo "=================="
echo "Start:   sudo /var/www/ai-social-creator/scripts/start.sh"
echo "Stop:    sudo /var/www/ai-social-creator/scripts/stop.sh"
echo "Restart: sudo systemctl restart ai-social-creator-backend ai-social-creator-frontend"
echo "Logs:    sudo journalctl -u ai-social-creator-backend -f"
echo "Update:  sudo /var/www/ai-social-creator/scripts/update.sh"

