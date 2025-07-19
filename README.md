# AI Social Media Creator

🤖 **AI-powered social media content creation platform** that generates, optimizes, and publishes content across multiple platforms using advanced AI technology.

![AI Social Media Creator](https://img.shields.io/badge/AI-Powered-blue) ![Platform](https://img.shields.io/badge/Platform-Multi--Social-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

## 🌟 Features

- ✨ **AI Content Generation** - GPT-4 powered text creation with platform-specific optimization
- 🎨 **Multi-Platform Support** - Instagram, LinkedIn, Twitter/X, Facebook, TikTok
- 🚀 **One-Click Publishing** - Direct posting to social media platforms
- 📊 **Analytics & Insights** - Track performance and engagement
- 🎯 **Brand Voice Consistency** - Maintain consistent tone across platforms
- 🔄 **Content Scheduling** - Plan and automate your social media strategy
- 🖼️ **AI Image Generation** - DALL-E 3 integration for visual content
- 🎬 **Video Content Support** - AI-powered video concept generation

## 🚀 Quick Start

### One-Line Installation
```bash
curl -sSL https://raw.githubusercontent.com/benswaving/SocialMedia/main/install.sh | sudo bash
```

### Manual Installation
1. Clone the repository:
```bash
git clone https://github.com/benswaving/SocialMedia.git
cd SocialMedia
```

2. Run the installation script:
```bash
sudo bash install.sh
```

3. Configure your API keys:
```bash
# Edit backend environment
sudo nano /var/www/ai-social-creator/backend/.env

# Edit frontend environment  
sudo nano /var/www/ai-social-creator/frontend/.env
```

4. Start the services:
```bash
sudo systemctl start ai-social-creator-backend
sudo systemctl start ai-social-creator-frontend
```

5. Access the application:
- **Frontend**: http://localhost:3089
- **API**: http://localhost:3089/api

## 📋 Requirements

### System Requirements
- **OS**: Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- **RAM**: 4GB minimum, 8GB recommended
- **CPU**: 2 cores minimum, 4 cores recommended
- **Storage**: 50GB available space

### API Keys Required
- **OpenAI API** (GPT-4 & DALL-E 3) - Required
- **Facebook/Instagram API** - For social posting
- **LinkedIn API** - For professional content
- **Twitter/X API** - For microblogging ($100/month)
- **TikTok API** - For short-form video content
- **Stability AI** - For enhanced image generation (optional)

## 🔧 Configuration

### Backend Configuration
The backend runs on port **3088** (internal) and includes:
- Flask API with RESTful endpoints
- PostgreSQL database integration
- Redis caching layer
- AI service integrations
- Social media publishing services

### Frontend Configuration  
The frontend runs on port **3089** (external) and features:
- Modern React application
- Responsive design with dark theme
- Real-time content generation
- Platform-specific optimization interface
- Content preview and editing tools

### Port Configuration
- **Backend**: `127.0.0.1:3088` (internal only)
- **Frontend**: `0.0.0.0:3089` (external access)
- **API Access**: `http://localhost:3089/api/` (proxied through frontend)

## 📚 Documentation

### Setup Guides
- **[API Registration Guide](docs/API-Registratie-Stappen.md)** - Step-by-step social media API setup
- **[Deployment Guide](docs/Eigen-Server-Deployment-Handleiding.md)** - Complete server deployment instructions
- **[Systemctl Setup](docs/Systemctl-Service-Setup-Custom-Ports.md)** - Service configuration for custom ports

### Architecture
- **Backend**: Flask + SQLAlchemy + Redis + OpenAI
- **Frontend**: React + TailwindCSS + Vite
- **Database**: PostgreSQL with Redis caching
- **Services**: Systemd services for production deployment
- **Proxy**: Nginx reverse proxy for single-port access

## 🎛️ Management Commands

### Service Management
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
```

### Logs & Monitoring
```bash
# Backend logs
sudo journalctl -u ai-social-creator-backend -f

# Frontend logs
sudo journalctl -u ai-social-creator-frontend -f

# Nginx access logs
sudo tail -f /var/log/nginx/ai-social-creator-access.log

# All system logs
sudo journalctl -f
```

### Updates
```bash
# Update application
cd /var/www/ai-social-creator
git pull origin main
./scripts/update.sh
```

## 🔒 Security Features

- **Input Validation** - XSS and injection protection
- **Rate Limiting** - API abuse prevention  
- **CORS Configuration** - Secure cross-origin requests
- **Environment Variables** - Secure API key management
- **Service Isolation** - Systemd security features
- **HTTP Only** - No SSL complexity (configurable)

## 💰 Cost Breakdown

### API Costs (Monthly)
- **OpenAI GPT-4**: ~$0.03 per 1K tokens (~$10-50/month)
- **OpenAI DALL-E 3**: ~$0.04 per image (~$5-20/month)
- **Twitter/X API**: $100/month (Basic plan)
- **Other APIs**: Free with rate limits
- **Total**: ~$115-170/month for full features

### Infrastructure Costs
- **VPS/Server**: $10-50/month (depending on provider)
- **Domain**: $10-15/year (optional)
- **Total**: $10-50/month + API costs

## 🚀 Deployment Options

### 1. Self-Hosted (Recommended)
- Full control over data and infrastructure
- Custom port configuration (3088/3089)
- Systemctl service management
- No vendor lock-in

### 2. Cloud Deployment
- DigitalOcean App Platform
- AWS EC2 + RDS
- Google Cloud Platform
- Heroku (with limitations)

### 3. Docker Deployment
```bash
# Using Docker Compose
docker-compose up -d

# Access application
http://localhost:3089
```

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Commit your changes: `git commit -m 'Add feature'`
5. Push to the branch: `git push origin feature-name`
6. Submit a pull request

### Development Setup
```bash
# Backend development
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/main.py

# Frontend development
cd frontend
pnpm install
pnpm dev
```

## 📊 Performance & Scaling

### Current Capacity
- **Concurrent Users**: 100-500 (depending on server specs)
- **Content Generation**: 1000+ posts/day
- **API Requests**: 10,000+ requests/day
- **Database**: Handles millions of records

### Scaling Options
- **Horizontal Scaling**: Multiple backend instances
- **Database Scaling**: PostgreSQL read replicas
- **Caching**: Redis cluster setup
- **CDN**: Static asset delivery optimization

## 🆘 Troubleshooting

### Common Issues

**Services won't start:**
```bash
# Check service status
sudo systemctl status ai-social-creator-backend
sudo journalctl -u ai-social-creator-backend -n 50
```

**Database connection errors:**
```bash
# Check PostgreSQL status
sudo systemctl status postgresql
sudo -u postgres psql -d socialmedia_creator
```

**API key errors:**
```bash
# Verify environment variables
sudo cat /var/www/ai-social-creator/backend/.env | grep API_KEY
```

**Port conflicts:**
```bash
# Check port usage
sudo netstat -tlnp | grep -E ":(3088|3089)"
```

### Support
- **Issues**: [GitHub Issues](https://github.com/benswaving/SocialMedia/issues)
- **Discussions**: [GitHub Discussions](https://github.com/benswaving/SocialMedia/discussions)
- **Documentation**: [docs/](docs/) directory

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI** - For GPT-4 and DALL-E 3 API
- **Meta** - For Facebook and Instagram APIs
- **LinkedIn** - For professional networking API
- **Twitter/X** - For microblogging platform API
- **TikTok** - For short-form video platform API
- **Open Source Community** - For the amazing tools and libraries

---

## 🎯 Project Status

**Current Version**: v1.0.0  
**Status**: Production Ready  
**Last Updated**: July 2025  

### Roadmap
- [ ] Mobile app (React Native)
- [ ] Advanced analytics dashboard
- [ ] Team collaboration features
- [ ] White-label solution
- [ ] API marketplace integration
- [ ] Multi-language support

---

**Made with ❤️ by the AI Social Media Creator team**

*Transform your social media strategy with the power of AI!*

