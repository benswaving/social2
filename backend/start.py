#!/usr/bin/env python3
"""
Startup script for AI Social Media Creator Backend
Loads environment variables and starts the Flask application
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import and run the main application
if __name__ == '__main__':
    from src.main import app
    
    # Get configuration from environment
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 3088))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"🚀 Starting AI Social Media Creator Backend...")
    print(f"📡 Host: {host}")
    print(f"🔌 Port: {port}")
    print(f"🐛 Debug: {debug}")
    print(f"🔑 OpenAI API Key: {'✅ Set' if os.getenv('OPENAI_API_KEY') else '❌ Missing'}")
    print(f"🔐 Encryption Key: {'✅ Set' if os.getenv('ENCRYPTION_KEY') else '❌ Missing'}")
    
    app.run(host=host, port=port, debug=debug)
