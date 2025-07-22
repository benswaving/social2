import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, jsonify, abort, request
from flask_cors import CORS
from src.models.user import db
from src.routes.user import user_bp
from src.routes.content import content_bp
from src.routes.platform import platform_bp
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Initialize Flask app
app = Flask(__name__, static_folder='../../frontend/dist')

# App configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MEDIA_STORAGE_PATH'] = os.environ.get('MEDIA_STORAGE_PATH')

# Initialize extensions
CORS(app, resources={r"/api/*": {"origins": "*"}})
db.init_app(app)

# Register blueprints FIRST - this is critical
app.register_blueprint(user_bp, url_prefix='/api/auth')
app.register_blueprint(content_bp, url_prefix='/api/content')
app.register_blueprint(platform_bp, url_prefix='/api/platforms')

# Only serve the root path for the frontend
@app.route('/')
def serve_root():
    return send_from_directory(app.static_folder, 'index.html')

# NO catch-all route - let Flask handle 404s naturally for API routes
# This allows the blueprints to work correctly without interference

if __name__ == '__main__':
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('BACKEND_PORT', 3088)))
