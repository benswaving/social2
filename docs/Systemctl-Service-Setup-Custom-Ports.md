# AI Social Media Creator - Systemctl Setup (Poort 3088/3089)

## 🎯 **Custom Port Configuration:**
- **Backend**: Poort 3088 (Flask API)
- **Frontend**: Poort 3089 (Nginx)
- **Geen SSL**: Alleen HTTP

---

## 📋 **Systemctl Services Setup**

### **1. Backend Service**
**Bestand:** `/etc/systemd/system/ai-social-creator-backend.service`

```ini
[Unit]
Description=AI Social Media Creator Backend API
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/ai-social-creator/backend
Environment=PATH=/var/www/ai-social-creator/backend/venv/bin
ExecStart=/var/www/ai-social-creator/backend/venv/bin/gunicorn --bind 127.0.0.1:3088 --workers 4 --timeout 120 src.main:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10

# Environment variables
EnvironmentFile=/var/www/ai-social-creator/backend/.env

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/www/ai-social-creator/backend
ProtectHome=true

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ai-social-creator-backend

[Install]
WantedBy=multi-user.target
```

### **2. Frontend Service (Nginx)**
**Bestand:** `/etc/systemd/system/ai-social-creator-frontend.service`

```ini
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
```

---

## 🌐 **Nginx Configuratie (Poort 3089)**

**Bestand:** `/etc/nginx/ai-social-creator.conf`

```nginx
# AI Social Media Creator - Custom Ports Configuration
# Frontend: 3089, Backend: 3088

# PID file voor systemd service
pid /run/nginx-ai-social-creator.pid;

# Events block
events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

# HTTP block
http {
    # Basic settings
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    
    # MIME types
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    # Logging
    access_log /var/log/nginx/ai-social-creator-access.log;
    error_log /var/log/nginx/ai-social-creator-error.log;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/javascript
        application/xml+rss
        application/json
        image/svg+xml;
    
    # Server block
    server {
        listen 3089;
        server_name localhost _;
        
        # Root directory voor frontend
        root /var/www/ai-social-creator/frontend/dist;
        index index.html;
        
        # Security headers (HTTP only)
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Referrer-Policy "no-referrer-when-downgrade" always;
        
        # API Backend Proxy (naar poort 3088)
        location /api/ {
            proxy_pass http://127.0.0.1:3088/api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto http;
            
            # Timeouts
            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
            
            # Buffer settings
            proxy_buffering on;
            proxy_buffer_size 4k;
            proxy_buffers 8 4k;
        }
        
        # Frontend Static Files
        location / {
            try_files $uri $uri/ /index.html;
            
            # Cache control voor HTML
            location ~* \.html$ {
                expires -1;
                add_header Cache-Control "no-cache, no-store, must-revalidate";
            }
        }
        
        # Static Assets Caching
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
            
            # CORS voor fonts
            location ~* \.(woff|woff2|ttf|eot)$ {
                add_header Access-Control-Allow-Origin "*";
            }
        }
        
        # Health check endpoint
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }
        
        # Deny access to sensitive files
        location ~ /\. {
            deny all;
            access_log off;
            log_not_found off;
        }
        
        location ~ ~$ {
            deny all;
            access_log off;
            log_not_found off;
        }
    }
}
```

---

## 🔧 **Installation Script (Custom Ports)**

**Bestand:** `install-systemctl-custom-ports.sh`

```bash
#!/bin/bash
# AI Social Media Creator - Custom Ports Installation Script
# Backend: 3088, Frontend: 3089

set -e

echo "🚀 Installing AI Social Media Creator (Backend:3088, Frontend:3089)"
echo "=================================================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

# Variables
PROJECT_DIR="/var/www/ai-social-creator"
NGINX_CONF="/etc/nginx/ai-social-creator.conf"
BACKEND_SERVICE="/etc/systemd/system/ai-social-creator-backend.service"
FRONTEND_SERVICE="/etc/systemd/system/ai-social-creator-frontend.service"

# Create project directory
echo "📁 Creating project directory..."
mkdir -p $PROJECT_DIR
chown www-data:www-data $PROJECT_DIR

# Install system dependencies
echo "📦 Installing system dependencies..."
apt update
apt install -y python3.11 python3.11-venv python3-pip nodejs npm nginx postgresql redis-server git

# Install pnpm
npm install -g pnpm

# Setup databases
echo "🗄️ Setting up databases..."
systemctl start postgresql redis-server
systemctl enable postgresql redis-server

# Create database
sudo -u postgres psql << EOF
CREATE DATABASE IF NOT EXISTS socialmedia_creator;
CREATE USER IF NOT EXISTS smcreator WITH PASSWORD 'secure_password_$(date +%s)';
GRANT ALL PRIVILEGES ON DATABASE socialmedia_creator TO smcreator;
\q
EOF

# Setup application (assuming code is already in place)
echo "🔧 Setting up backend..."
cd $PROJECT_DIR/backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "🎨 Setting up frontend..."
cd $PROJECT_DIR/frontend
pnpm install
pnpm build

# Set permissions
chown -R www-data:www-data $PROJECT_DIR

# Create backend systemd service
echo "⚙️ Creating backend service (port 3088)..."
cat > $BACKEND_SERVICE << 'EOF'
[Unit]
Description=AI Social Media Creator Backend API
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/ai-social-creator/backend
Environment=PATH=/var/www/ai-social-creator/backend/venv/bin
ExecStart=/var/www/ai-social-creator/backend/venv/bin/gunicorn --bind 127.0.0.1:3088 --workers 4 --timeout 120 src.main:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10

EnvironmentFile=/var/www/ai-social-creator/backend/.env

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/www/ai-social-creator/backend
ProtectHome=true

StandardOutput=journal
StandardError=journal
SyslogIdentifier=ai-social-creator-backend

[Install]
WantedBy=multi-user.target
EOF

# Create frontend systemd service
echo "⚙️ Creating frontend service (port 3089)..."
cat > $FRONTEND_SERVICE << 'EOF'
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

# Create nginx configuration
echo "🌐 Creating nginx configuration (port 3089)..."
cat > $NGINX_CONF << 'EOF'
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

# Test nginx configuration
nginx -t -c $NGINX_CONF

# Reload systemd and start services
echo "🚀 Starting services..."
systemctl daemon-reload

# Enable and start backend
systemctl enable ai-social-creator-backend
systemctl start ai-social-creator-backend

# Enable and start frontend
systemctl enable ai-social-creator-frontend
systemctl start ai-social-creator-frontend

# Check service status
echo "✅ Installation completed!"
echo ""
echo "Service Status:"
systemctl status ai-social-creator-backend --no-pager -l
systemctl status ai-social-creator-frontend --no-pager -l

echo ""
echo "🌐 Application URLs:"
echo "  Frontend: http://localhost:3089"
echo "  Backend API: http://localhost:3089/api"
echo "  Health Check: http://localhost:3089/health"
echo ""
echo "Direct Backend Access (internal):"
echo "  Backend: http://127.0.0.1:3088"
echo ""
echo "Management commands:"
echo "  sudo systemctl start ai-social-creator-backend"
echo "  sudo systemctl start ai-social-creator-frontend"
echo "  sudo systemctl stop ai-social-creator-backend"
echo "  sudo systemctl stop ai-social-creator-frontend"
echo "  sudo systemctl restart ai-social-creator-backend"
echo "  sudo systemctl restart ai-social-creator-frontend"
echo ""
echo "Logs:"
echo "  sudo journalctl -u ai-social-creator-backend -f"
echo "  sudo journalctl -u ai-social-creator-frontend -f"
echo "  sudo tail -f /var/log/nginx/ai-social-creator-access.log"
```

---

## 🎛️ **Management Commands**

### **Service Management:**
```bash
# Start services
sudo systemctl start ai-social-creator-backend
sudo systemctl start ai-social-creator-frontend

# Stop services
sudo systemctl stop ai-social-creator-backend
sudo systemctl stop ai-social-creator-frontend

# Restart services
sudo systemctl restart ai-social-creator-backend
sudo systemctl restart ai-social-creator-frontend

# Check status
sudo systemctl status ai-social-creator-backend
sudo systemctl status ai-social-creator-frontend

# Enable auto-start
sudo systemctl enable ai-social-creator-backend
sudo systemctl enable ai-social-creator-frontend
```

### **Logs:**
```bash
# Backend logs
sudo journalctl -u ai-social-creator-backend -f

# Frontend logs
sudo journalctl -u ai-social-creator-frontend -f

# Nginx access logs
sudo tail -f /var/log/nginx/ai-social-creator-access.log

# Nginx error logs
sudo tail -f /var/log/nginx/ai-social-creator-error.log
```

### **Port Testing:**
```bash
# Test frontend (port 3089)
curl http://localhost:3089/

# Test backend via frontend proxy
curl http://localhost:3089/api/health

# Test backend direct (internal only)
curl http://127.0.0.1:3088/api/health

# Check listening ports
sudo netstat -tlnp | grep -E ":(3088|3089)"
```

---

## 🔧 **Frontend Environment Update**

**Update:** `/var/www/ai-social-creator/frontend/.env`

```env
# Update API base URL to use port 3089
VITE_API_BASE_URL=http://localhost:3089/api
VITE_APP_NAME=AI Social Media Creator
VITE_ENABLE_ANALYTICS=false
```

---

## ✅ **Verificatie Checklist**

### **Port Configuration:**
- [ ] Backend draait op `127.0.0.1:3088` (intern)
- [ ] Frontend draait op `0.0.0.0:3089` (extern toegankelijk)
- [ ] API proxy werkt: `http://localhost:3089/api/` → `http://127.0.0.1:3088/api/`

### **Services:**
- [ ] `ai-social-creator-backend.service` actief
- [ ] `ai-social-creator-frontend.service` actief
- [ ] Auto-start enabled voor beide services

### **Functionality:**
- [ ] Frontend bereikbaar: `http://localhost:3089`
- [ ] API werkt: `http://localhost:3089/api/health`
- [ ] Content generation test succesvol

### **Security:**
- [ ] Backend alleen intern bereikbaar (127.0.0.1:3088)
- [ ] Frontend extern bereikbaar (0.0.0.0:3089)
- [ ] Geen SSL configuratie (HTTP only)

---

## 🎯 **Custom Ports Summary:**

✅ **Backend**: Poort 3088 (127.0.0.1 - intern)  
✅ **Frontend**: Poort 3089 (0.0.0.0 - extern)  
✅ **API Access**: Via frontend proxy op 3089  
✅ **Systemctl Services**: Beide services geconfigureerd  
✅ **Geen SSL**: Alleen HTTP configuratie  

**Perfect voor jouw custom port setup!** 🚀

