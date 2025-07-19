#!/bin/bash
# Update AI Social Media Creator

echo "🔄 Updating AI Social Media Creator..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

PROJECT_DIR="/var/www/ai-social-creator"

# Check if project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Project directory not found: $PROJECT_DIR"
    exit 1
fi

cd $PROJECT_DIR

# Backup current .env files
echo "💾 Backing up configuration files..."
cp backend/.env backend/.env.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
cp frontend/.env frontend/.env.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true

# Pull latest changes
echo "📥 Pulling latest changes from GitHub..."
git fetch origin main
git pull origin main

# Update backend
echo "🔧 Updating backend..."
cd backend
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Update frontend
echo "🎨 Updating frontend..."
cd ../frontend
pnpm install
pnpm build

# Set proper permissions
echo "🔒 Setting permissions..."
chown -R www-data:www-data $PROJECT_DIR

# Restart services
echo "🔄 Restarting services..."
systemctl restart ai-social-creator-backend
systemctl restart ai-social-creator-frontend

# Wait for services to start
sleep 5

# Verify services are running
echo ""
echo "🔍 Verifying services..."

if systemctl is-active --quiet ai-social-creator-backend; then
    echo "✅ Backend service restarted successfully"
else
    echo "❌ Backend service failed to restart"
    systemctl status ai-social-creator-backend --no-pager -l
fi

if systemctl is-active --quiet ai-social-creator-frontend; then
    echo "✅ Frontend service restarted successfully"
else
    echo "❌ Frontend service failed to restart"
    systemctl status ai-social-creator-frontend --no-pager -l
fi

# Test connectivity
echo ""
echo "🌐 Testing connectivity..."

if curl -s http://localhost:3089/health > /dev/null; then
    echo "✅ Application is accessible"
else
    echo "❌ Application is not accessible"
fi

echo ""
echo "✅ Update completed!"
echo ""
echo "🌐 Application URLs:"
echo "Frontend: http://localhost:3089"
echo "API: http://localhost:3089/api"
echo ""
echo "📋 If you encounter issues:"
echo "1. Check logs: sudo journalctl -u ai-social-creator-backend -f"
echo "2. Check status: sudo /var/www/ai-social-creator/scripts/status.sh"
echo "3. Restore backup: cp backend/.env.backup.* backend/.env"

