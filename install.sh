#!/bin/bash
# AI Social Media Creator - Automated Installation Script
# GitHub: https://github.com/benswaving/SocialMedia
# Backend: Port 3088, Frontend: Port 3089

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

echo -e "${BLUE}"
cat << "EOF"
    _    ___   ____             _       _   __  __          _ _       
   / \  |_ _| / ___|  ___   ___(_) __ _| | |  \/  | ___  __| (_) __ _ 
  / _ \  | |  \___ \ / _ \ / __| |/ _` | | | |\/| |/ _ \/ _` | |/ _` |
 / ___ \ | |   ___) | (_) | (__| | (_| | | | |  | |  __/ (_| | | (_| |
/_/   \_\___| |____/ \___/ \___|_|\__,_|_| |_|  |_|\___|\__,_|_|\__,_|
                                                                      
   ____                _             
  / ___|_ __ ___  __ _| |_ ___  _ __ 
 | |   | '__/ _ \/ _` | __/ _ \| '__|
 | |___| | |  __/ (_| | || (_) | |   
  \____|_|  \___|\__,_|\__\___/|_|   
                                     
EOF
echo -e "${NC}"

log "🚀 AI Social Media Creator - Automated Installation"
log "=================================================="
log "Backend Port: 3088 (internal)"
log "Frontend Port: 3089 (external)"
log "Repository: https://github.com/benswaving/SocialMedia"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   error "❌ This script must be run as root (use sudo)"
fi

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/debian_version ]; then
            OS="debian"
            log "✅ Detected OS: Debian/Ubuntu"
        elif [ -f /etc/redhat-release ]; then
            OS="redhat"
            log "✅ Detected OS: RedHat/CentOS"
        else
            error "❌ Unsupported Linux distribution"
        fi
    else
        error "❌ Unsupported operating system: $OSTYPE"
    fi
}

# Install system dependencies
install_system_deps() {
    log "📦 Installing system dependencies..."
    
    if [ "$OS" = "debian" ]; then
        apt update
        apt install -y curl wget git unzip software-properties-common build-essential
        
        # Python 3.11
        add-apt-repository ppa:deadsnakes/ppa -y
        apt update
        apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
        
        # Node.js 18
        curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
        apt install -y nodejs
        
        # PostgreSQL & Redis
        apt install -y postgresql postgresql-contrib redis-server
        
        # Nginx
        apt install -y nginx
        
    elif [ "$OS" = "redhat" ]; then
        yum update -y
        yum install -y curl wget git unzip gcc gcc-c++ make
        
        # Python 3.11 (from source or EPEL)
        yum install -y python3 python3-pip python3-devel
        
        # Node.js 18
        curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -
        yum install -y nodejs
        
        # PostgreSQL & Redis
        yum install -y postgresql postgresql-server redis
        
        # Nginx
        yum install -y nginx
    fi
    
    # Install pnpm and PM2
    npm install -g pnpm
    
    log "✅ System dependencies installed"
}

# Setup databases
setup_databases() {
    log "🗄️ Setting up databases..."
    
    # Start services
    if [ "$OS" = "debian" ]; then
        systemctl start postgresql redis-server
        systemctl enable postgresql redis-server
    elif [ "$OS" = "redhat" ]; then
        if [ ! -f /var/lib/pgsql/data/postgresql.conf ]; then
            postgresql-setup initdb
        fi
        systemctl start postgresql redis
        systemctl enable postgresql redis
    fi
    
    # Generate secure password
    DB_PASSWORD="smcreator_$(openssl rand -hex 16)"
    
    # Create database and user
    sudo -u postgres psql << EOF
CREATE DATABASE IF NOT EXISTS socialmedia_creator;
CREATE USER IF NOT EXISTS smcreator WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE socialmedia_creator TO smcreator;
ALTER USER smcreator CREATEDB;
\q
EOF
    
    # Save database credentials
    echo "DATABASE_PASSWORD=$DB_PASSWORD" > /tmp/db_credentials
    
    log "✅ Database setup completed"
    log "📝 Database password saved to /tmp/db_credentials"
}

# Clone and setup application
setup_application() {
    log "📁 Setting up application..."
    
    # Create project directory
    PROJECT_DIR="/var/www/ai-social-creator"
    mkdir -p $PROJECT_DIR
    
    # Clone repository
    if [ -d "$PROJECT_DIR/.git" ]; then
        log "📥 Updating existing repository..."
        cd $PROJECT_DIR
        git pull origin main
    else
        log "📥 Cloning repository..."
        git clone https://github.com/benswaving/SocialMedia.git $PROJECT_DIR
        cd $PROJECT_DIR
    fi
    
    # Backend setup
    log "🔧 Setting up backend..."
    cd $PROJECT_DIR/backend
    python3.11 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Copy environment template and configure
    if [ ! -f .env ]; then
        cp .env.example .env
        
        # Read database password
        DB_PASSWORD=$(grep DATABASE_PASSWORD /tmp/db_credentials | cut -d'=' -f2)
        
        # Update .env with database credentials
        sed -i "s/postgresql:\/\/username:password@localhost:5432\/socialmedia_creator/postgresql:\/\/smcreator:$DB_PASSWORD@localhost:5432\/socialmedia_creator/" .env
        
        warn "⚠️  Please edit $PROJECT_DIR/backend/.env with your API keys!"
    fi
    
    # Frontend setup
    log "🎨 Setting up frontend..."
    cd $PROJECT_DIR/frontend
    pnpm install
    
    # Copy environment template
    if [ ! -f .env ]; then
        cp .env.example .env
        # Update API base URL for port 3089
        sed -i 's/VITE_API_BASE_URL=.*/VITE_API_BASE_URL=http:\/\/localhost:3089\/api/' .env
    fi
    
    # Build frontend
    pnpm build
    
    # Set permissions
    chown -R www-data:www-data $PROJECT_DIR
    
    log "✅ Application setup completed"
}

# Create systemd services
create_services() {
    log "⚙️ Creating systemd services..."
    
    PROJECT_DIR="/var/www/ai-social-creator"
    
    # Backend service
    cat > /etc/systemd/system/ai-social-creator-backend.service << EOF
[Unit]
Description=AI Social Media Creator Backend API
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=$PROJECT_DIR/backend
Environment=PATH=$PROJECT_DIR/backend/venv/bin
ExecStart=$PROJECT_DIR/backend/venv/bin/gunicorn --bind 127.0.0.1:3088 --workers 4 --timeout 120 src.main:app
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=10

EnvironmentFile=$PROJECT_DIR/backend/.env

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$PROJECT_DIR/backend
ProtectHome=true

StandardOutput=journal
StandardError=journal
SyslogIdentifier=ai-social-creator-backend

[Install]
WantedBy=multi-user.target
EOF

    # Frontend nginx configuration
    cat > /etc/nginx/ai-social-creator.conf << 'EOF'
pid /run/nginx-ai-social-creator.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    access_log /var/log/nginx/ai-social-creator-access.log;
    error_log /var/log/nginx/ai-social-creator-error.log;
    
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json image/svg+xml;
    
    server {
        listen 3089;
        server_name localhost _;
        
        root /var/www/ai-social-creator/frontend/dist;
        index index.html;
        
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header X-Content-Type-Options "nosniff" always;
        
        location /api/ {
            proxy_pass http://127.0.0.1:3088/api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto http;
            
            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }
        
        location / {
            try_files $uri $uri/ /index.html;
        }
        
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
        
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }
    }
}
EOF

    # Frontend service
    cat > /etc/systemd/system/ai-social-creator-frontend.service << 'EOF'
[Unit]
Description=AI Social Media Creator Frontend (Nginx)
After=network.target ai-social-creator-backend.service
Wants=ai-social-creator-backend.service

[Service]
Type=forking
PIDFile=/run/nginx-ai-social-creator.pid
ExecStartPre=/usr/sbin/nginx -t -c /etc/nginx/ai-social-creator.conf
ExecStart=/usr/sbin/nginx -c /etc/nginx/ai-social-creator.conf
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s QUIT $MAINPID
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    
    log "✅ Systemd services created"
}

# Initialize database
init_database() {
    log "🗄️ Initializing database..."
    
    cd /var/www/ai-social-creator/backend
    source venv/bin/activate
    
    # Create database tables
    python -c "
from src.models.user import db
from src.main import app
with app.app_context():
    try:
        db.create_all()
        print('✅ Database tables created successfully!')
    except Exception as e:
        print(f'❌ Database initialization failed: {e}')
        exit(1)
"
    
    log "✅ Database initialized"
}

# Start services
start_services() {
    log "🚀 Starting services..."
    
    # Test nginx configuration
    nginx -t -c /etc/nginx/ai-social-creator.conf
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable and start backend
    systemctl enable ai-social-creator-backend
    systemctl start ai-social-creator-backend
    
    # Enable and start frontend
    systemctl enable ai-social-creator-frontend
    systemctl start ai-social-creator-frontend
    
    # Wait a moment for services to start
    sleep 5
    
    log "✅ Services started"
}

# Verify installation
verify_installation() {
    log "🔍 Verifying installation..."
    
    # Check service status
    if systemctl is-active --quiet ai-social-creator-backend; then
        log "✅ Backend service is running"
    else
        warn "⚠️  Backend service is not running"
        systemctl status ai-social-creator-backend --no-pager -l
    fi
    
    if systemctl is-active --quiet ai-social-creator-frontend; then
        log "✅ Frontend service is running"
    else
        warn "⚠️  Frontend service is not running"
        systemctl status ai-social-creator-frontend --no-pager -l
    fi
    
    # Test endpoints
    log "🌐 Testing endpoints..."
    
    # Test frontend
    if curl -s http://localhost:3089/ > /dev/null; then
        log "✅ Frontend accessible at http://localhost:3089"
    else
        warn "⚠️  Frontend not accessible"
    fi
    
    # Test backend via proxy
    if curl -s http://localhost:3089/api/health > /dev/null; then
        log "✅ Backend API accessible at http://localhost:3089/api"
    else
        warn "⚠️  Backend API not accessible via proxy"
    fi
    
    # Test direct backend
    if curl -s http://127.0.0.1:3088/api/health > /dev/null; then
        log "✅ Backend direct access working"
    else
        warn "⚠️  Backend direct access not working"
    fi
}

# Create management scripts
create_scripts() {
    log "📝 Creating management scripts..."
    
    mkdir -p /var/www/ai-social-creator/scripts
    
    # Start script
    cat > /var/www/ai-social-creator/scripts/start.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting AI Social Media Creator..."
sudo systemctl start ai-social-creator-backend
sudo systemctl start ai-social-creator-frontend
echo "✅ Services started!"
echo "🌐 Frontend: http://localhost:3089"
echo "🔍 API: http://localhost:3089/api"
EOF

    # Stop script
    cat > /var/www/ai-social-creator/scripts/stop.sh << 'EOF'
#!/bin/bash
echo "🛑 Stopping AI Social Media Creator..."
sudo systemctl stop ai-social-creator-backend
sudo systemctl stop ai-social-creator-frontend
echo "✅ Services stopped!"
EOF

    # Status script
    cat > /var/www/ai-social-creator/scripts/status.sh << 'EOF'
#!/bin/bash
echo "📊 AI Social Media Creator Status"
echo "================================"
echo ""
echo "Backend Service:"
sudo systemctl status ai-social-creator-backend --no-pager -l
echo ""
echo "Frontend Service:"
sudo systemctl status ai-social-creator-frontend --no-pager -l
echo ""
echo "Port Status:"
sudo netstat -tlnp | grep -E ":(3088|3089)"
EOF

    # Update script
    cat > /var/www/ai-social-creator/scripts/update.sh << 'EOF'
#!/bin/bash
echo "🔄 Updating AI Social Media Creator..."

cd /var/www/ai-social-creator
git pull origin main

# Update backend
cd backend
source venv/bin/activate
pip install -r requirements.txt

# Update frontend
cd ../frontend
pnpm install
pnpm build

# Restart services
sudo systemctl restart ai-social-creator-backend
sudo systemctl restart ai-social-creator-frontend

echo "✅ Update completed!"
EOF

    # Make scripts executable
    chmod +x /var/www/ai-social-creator/scripts/*.sh
    
    log "✅ Management scripts created"
}

# Main installation function
main() {
    log "Starting installation process..."
    
    detect_os
    install_system_deps
    setup_databases
    setup_application
    create_services
    init_database
    start_services
    create_scripts
    verify_installation
    
    echo ""
    log "🎉 Installation completed successfully!"
    echo ""
    echo -e "${GREEN}🌐 Application URLs:${NC}"
    echo "  Frontend: http://localhost:3089"
    echo "  Backend API: http://localhost:3089/api"
    echo "  Health Check: http://localhost:3089/health"
    echo ""
    echo -e "${YELLOW}⚠️  Next Steps:${NC}"
    echo "1. Edit API keys: sudo nano /var/www/ai-social-creator/backend/.env"
    echo "2. Restart backend: sudo systemctl restart ai-social-creator-backend"
    echo "3. Test the application: http://localhost:3089"
    echo ""
    echo -e "${BLUE}📋 Management Commands:${NC}"
    echo "  Start:   /var/www/ai-social-creator/scripts/start.sh"
    echo "  Stop:    /var/www/ai-social-creator/scripts/stop.sh"
    echo "  Status:  /var/www/ai-social-creator/scripts/status.sh"
    echo "  Update:  /var/www/ai-social-creator/scripts/update.sh"
    echo ""
    echo -e "${BLUE}📖 Documentation:${NC}"
    echo "  API Setup: https://github.com/benswaving/SocialMedia/blob/main/docs/API-Registratie-Stappen.md"
    echo "  Deployment: https://github.com/benswaving/SocialMedia/blob/main/docs/Eigen-Server-Deployment-Handleiding.md"
    echo ""
    echo -e "${GREEN}🚀 Happy content creating!${NC}"
}

# Run main function
main "$@"

