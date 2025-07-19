# AI Social Media Creator - Eigen Server Deployment Handleiding

**Voor:** Deployment op eigen server/VPS/PC  
**Tijd:** 2-4 uur setup  
**Vereisten:** Ubuntu 20.04+ of vergelijkbaar Linux systeem  

---

## 📋 DEEL 1: Server Voorbereiding (30 minuten)

### Stap 1: Server Requirements
**Minimale Specificaties:**
- 4GB RAM
- 2 CPU cores  
- 50GB opslag
- Ubuntu 20.04+ of Debian 11+

### Stap 2: Basis Software Installeren
```bash
# Update systeem
sudo apt update && sudo apt upgrade -y

# Installeer basis tools
sudo apt install -y curl wget git unzip software-properties-common

# Installeer Python 3.11
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Installeer Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Installeer pnpm
npm install -g pnpm

# Installeer PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Installeer Redis
sudo apt install -y redis-server

# Installeer Nginx (voor frontend)
sudo apt install -y nginx

# Installeer PM2 (voor process management)
npm install -g pm2
```

### Stap 3: Database Setup
```bash
# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Maak database en gebruiker
sudo -u postgres psql << EOF
CREATE DATABASE socialmedia_creator;
CREATE USER smcreator WITH PASSWORD 'jouw_sterke_wachtwoord_hier';
GRANT ALL PRIVILEGES ON DATABASE socialmedia_creator TO smcreator;
\q
EOF

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

---

## 🔑 DEEL 2: API Keys Registreren (1-2 uur)

### Stap 4: OpenAI API (Al werkend)
✅ **Je hebt al een werkende OpenAI API key**
- Controleer je usage limits op [platform.openai.com](https://platform.openai.com)
- Upgrade naar betaald plan als je veel gaat gebruiken

### Stap 5: Facebook/Instagram API
**Registratie Process:**
1. Ga naar [developers.facebook.com](https://developers.facebook.com)
2. Klik "Get Started" → "Create App"
3. Kies "Business" → "Next"
4. Vul app details in:
   - **App Name**: "AI Social Creator" (of jouw naam)
   - **Contact Email**: jouw email
   - **Business Account**: Maak nieuwe aan
5. Klik "Create App"

**Instagram Basic Display Setup:**
1. In je app dashboard → "Add Product" → "Instagram Basic Display"
2. Klik "Set Up" → "Create New App"
3. Noteer je **Instagram App ID** en **Instagram App Secret**
4. Voeg Redirect URI toe: `http://jouw-domain.com/auth/instagram/callback`

**Facebook Login Setup:**
1. "Add Product" → "Facebook Login" → "Set Up"
2. Kies "Web" platform
3. Site URL: `http://jouw-domain.com`
4. Noteer **App ID** en **App Secret**

### Stap 6: LinkedIn API
**Registratie Process:**
1. Ga naar [developer.linkedin.com](https://developer.linkedin.com)
2. Klik "Create App"
3. Vul in:
   - **App Name**: "AI Social Creator"
   - **LinkedIn Page**: Maak een bedrijfspagina aan
   - **Privacy Policy URL**: `http://jouw-domain.com/privacy`
   - **App Logo**: Upload een logo
4. Klik "Create App"

**API Access Aanvragen:**
1. Ga naar "Products" tab
2. Vraag aan: "Share on LinkedIn" en "Sign In with LinkedIn"
3. Wacht op approval (1-3 dagen)
4. Noteer **Client ID** en **Client Secret**

### Stap 7: Twitter/X API
**Registratie Process:**
1. Ga naar [developer.twitter.com](https://developer.twitter.com)
2. Klik "Sign up for free account"
3. Vul formulier in:
   - **Use Case**: "Building a social media management tool"
   - **Will you make Twitter content available to government**: No
4. Bevestig email en telefoonnummer

**API Keys Verkrijgen:**
1. Create New Project → "AI Social Creator"
2. Create New App binnen project
3. Ga naar "Keys and Tokens"
4. Noteer:
   - **API Key** (Consumer Key)
   - **API Secret** (Consumer Secret)
   - **Bearer Token**
5. Generate **Access Token** en **Access Token Secret**

### Stap 8: TikTok API
**Registratie Process:**
1. Ga naar [developers.tiktok.com](https://developers.tiktok.com)
2. Klik "Register" → "Login with TikTok"
3. Vul bedrijfsinformatie in
4. Create New App:
   - **App Name**: "AI Social Creator"
   - **Category**: "Productivity"
   - **Platform**: "Web"

**API Access:**
1. Ga naar app dashboard
2. Noteer **Client Key** en **Client Secret**
3. Vraag "Content Posting API" aan (kan 1-2 weken duren)

---

## 💻 DEEL 3: Code Deployment (45 minuten)

### Stap 9: Code Downloaden
```bash
# Maak project directory
mkdir -p /var/www/ai-social-creator
cd /var/www/ai-social-creator

# Download de code (vervang met jouw GitHub repo als je die hebt)
# Voor nu kopiëren we van de sandbox
```

**Kopieer de bestanden van de sandbox naar je server:**
```bash
# Backend
scp -r /home/ubuntu/social-media-creator-api user@jouw-server:/var/www/ai-social-creator/
scp -r /home/ubuntu/social-media-creator-frontend user@jouw-server:/var/www/ai-social-creator/

# Of gebruik rsync
rsync -av /home/ubuntu/social-media-creator-api/ user@jouw-server:/var/www/ai-social-creator/backend/
rsync -av /home/ubuntu/social-media-creator-frontend/ user@jouw-server:/var/www/ai-social-creator/frontend/
```

### Stap 10: Backend Setup
```bash
cd /var/www/ai-social-creator/backend

# Maak virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Installeer dependencies
pip install -r requirements.txt

# Maak .env bestand
cp .env.example .env
nano .env
```

**Vul .env bestand in:**
```env
# Database
DATABASE_URL=postgresql://smcreator:jouw_sterke_wachtwoord_hier@localhost:5432/socialmedia_creator
REDIS_URL=redis://localhost:6379/0

# Flask
FLASK_ENV=production
FLASK_SECRET_KEY=genereer_een_sterke_random_string_hier
JWT_SECRET_KEY=nog_een_sterke_random_string_hier

# OpenAI (jouw bestaande key)
OPENAI_API_KEY=jouw_openai_key_hier
OPENAI_API_BASE=https://api.openai.com/v1

# Facebook/Instagram (van stap 5)
FACEBOOK_APP_ID=jouw_facebook_app_id
FACEBOOK_APP_SECRET=jouw_facebook_app_secret
INSTAGRAM_APP_ID=jouw_instagram_app_id
INSTAGRAM_APP_SECRET=jouw_instagram_app_secret

# LinkedIn (van stap 6)
LINKEDIN_CLIENT_ID=jouw_linkedin_client_id
LINKEDIN_CLIENT_SECRET=jouw_linkedin_client_secret

# Twitter (van stap 7)
TWITTER_API_KEY=jouw_twitter_api_key
TWITTER_API_SECRET=jouw_twitter_api_secret
TWITTER_ACCESS_TOKEN=jouw_twitter_access_token
TWITTER_ACCESS_TOKEN_SECRET=jouw_twitter_access_token_secret

# TikTok (van stap 8)
TIKTOK_CLIENT_KEY=jouw_tiktok_client_key
TIKTOK_CLIENT_SECRET=jouw_tiktok_client_secret

# Security
CORS_ORIGINS=http://jouw-domain.com,https://jouw-domain.com
```

**Database initialiseren:**
```bash
# Activeer virtual environment
source venv/bin/activate

# Maak database tabellen
python -c "
from src.models.user import db
from src.main import app
with app.app_context():
    db.create_all()
    print('Database tabellen aangemaakt!')
"
```

### Stap 11: Frontend Setup
```bash
cd /var/www/ai-social-creator/frontend

# Installeer dependencies
pnpm install

# Maak .env bestand
cp .env.example .env
nano .env
```

**Vul frontend .env in:**
```env
VITE_API_BASE_URL=http://jouw-domain.com:5000/api
VITE_APP_NAME=AI Social Media Creator
VITE_ENABLE_ANALYTICS=false
```

**Build frontend:**
```bash
pnpm build
```

---

## 🚀 DEEL 4: Services Starten (30 minuten)

### Stap 12: Backend Service Setup
**Maak PM2 ecosystem bestand:**
```bash
nano /var/www/ai-social-creator/ecosystem.config.js
```

```javascript
module.exports = {
  apps: [{
    name: 'ai-social-creator-backend',
    cwd: '/var/www/ai-social-creator/backend',
    script: 'venv/bin/gunicorn',
    args: '--bind 0.0.0.0:5000 --workers 4 src.main:app',
    env: {
      NODE_ENV: 'production'
    },
    error_file: '/var/log/ai-social-creator/backend-error.log',
    out_file: '/var/log/ai-social-creator/backend-out.log',
    log_file: '/var/log/ai-social-creator/backend.log'
  }]
};
```

**Start backend:**
```bash
# Maak log directory
sudo mkdir -p /var/log/ai-social-creator
sudo chown $USER:$USER /var/log/ai-social-creator

# Start met PM2
cd /var/www/ai-social-creator
pm2 start ecosystem.config.js

# Auto-start bij reboot
pm2 startup
pm2 save
```

### Stap 13: Nginx Setup voor Frontend
```bash
sudo nano /etc/nginx/sites-available/ai-social-creator
```

```nginx
server {
    listen 80;
    server_name jouw-domain.com www.jouw-domain.com;
    
    # Frontend
    location / {
        root /var/www/ai-social-creator/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
    
    # Backend API
    location /api/ {
        proxy_pass http://localhost:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Static assets caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        root /var/www/ai-social-creator/frontend/dist;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

**Activeer site:**
```bash
# Symlink maken
sudo ln -s /etc/nginx/sites-available/ai-social-creator /etc/nginx/sites-enabled/

# Test configuratie
sudo nginx -t

# Herstart Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## 🔧 DEEL 5: Testing & Troubleshooting (30 minuten)

### Stap 14: Services Controleren
```bash
# Check backend status
pm2 status
pm2 logs ai-social-creator-backend

# Check database connectie
sudo -u postgres psql -d socialmedia_creator -c "SELECT version();"

# Check Redis
redis-cli ping

# Check Nginx
sudo systemctl status nginx
```

### Stap 15: API Testing
```bash
# Test backend health
curl http://localhost:5000/health

# Test API endpoint
curl http://localhost:5000/api/content/platforms

# Test frontend
curl http://localhost/
```

### Stap 16: Firewall Setup
```bash
# Installeer UFW
sudo apt install ufw

# Basis regels
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH, HTTP, HTTPS
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Activeer firewall
sudo ufw enable
```

---

## 🌐 DEEL 6: Domain & SSL (Optioneel, 30 minuten)

### Stap 17: Domain Setup
1. Koop een domain naam (bijv. Namecheap, GoDaddy)
2. Wijs A-record naar je server IP:
   - `@` → `jouw.server.ip.adres`
   - `www` → `jouw.server.ip.adres`

### Stap 18: SSL Certificaat (Let's Encrypt)
```bash
# Installeer Certbot
sudo apt install certbot python3-certbot-nginx

# Verkrijg SSL certificaat
sudo certbot --nginx -d jouw-domain.com -d www.jouw-domain.com

# Auto-renewal setup
sudo crontab -e
# Voeg toe: 0 12 * * * /usr/bin/certbot renew --quiet
```

---

## ✅ DEEL 7: Verificatie Checklist

### Functionaliteit Test:
- [ ] Website bereikbaar op http://jouw-domain.com
- [ ] Backend API reageert op /api/health
- [ ] Database connectie werkt
- [ ] Redis cache werkt
- [ ] Content generation test succesvol
- [ ] Alle social media platforms zichtbaar

### Security Check:
- [ ] Firewall actief
- [ ] SSL certificaat geïnstalleerd (indien domain)
- [ ] Environment variables secure
- [ ] Database wachtwoorden sterk
- [ ] Geen debug mode in productie

### Performance Check:
- [ ] PM2 processes draaien
- [ ] Nginx caching werkt
- [ ] Database queries snel (<2s)
- [ ] Frontend laadt snel (<3s)

---

## 🆘 Troubleshooting

### Backend start niet:
```bash
# Check logs
pm2 logs ai-social-creator-backend

# Manual start voor debugging
cd /var/www/ai-social-creator/backend
source venv/bin/activate
python src/main.py
```

### Database connectie problemen:
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test connectie
sudo -u postgres psql -d socialmedia_creator
```

### Frontend niet bereikbaar:
```bash
# Check Nginx status
sudo systemctl status nginx

# Check configuratie
sudo nginx -t

# Check logs
sudo tail -f /var/log/nginx/error.log
```

### API Keys werken niet:
1. Controleer .env bestand syntax
2. Herstart backend: `pm2 restart ai-social-creator-backend`
3. Test individuele API's via curl
4. Check API provider dashboards voor errors

---

## 🎉 Gefeliciteerd!

Je AI Social Media Creator draait nu op je eigen server! 

**Volgende stappen:**
1. Test alle functionaliteiten grondig
2. Setup monitoring (PM2 web dashboard)
3. Maak backup strategie
4. Begin met marketing en gebruikers werven

**Support:**
- Check logs: `pm2 logs`
- Monitor resources: `htop`
- Database backup: `pg_dump socialmedia_creator > backup.sql`

---

*Voor technische vragen, check de logs eerst en gebruik de troubleshooting sectie.*

