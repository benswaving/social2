import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from src.models.user import db
from src.routes.user import user_bp
from src.routes.auth import auth_bp
from src.routes.content import content_bp
from src.routes.ai_analysis import ai_analysis_bp
from src.routes.social_accounts import social_accounts_bp
from src.routes.oauth import oauth_bp
from src.routes.media import media_bp
from src.routes.database import database_bp
from src.routes.advanced_media import advanced_media_bp
from src.routes.sentiment import sentiment_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'asdf#FGSgvasgf$5$WGT-dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Enable CORS for all routes
CORS(app, origins="*", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], 
     allow_headers=["Content-Type", "Authorization"])

# Register blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(content_bp, url_prefix='/api/content')
app.register_blueprint(ai_analysis_bp, url_prefix='/api/ai')
app.register_blueprint(social_accounts_bp, url_prefix='/api')
app.register_blueprint(oauth_bp, url_prefix='/api')
app.register_blueprint(media_bp, url_prefix='/api')
app.register_blueprint(database_bp, url_prefix='/api')
app.register_blueprint(advanced_media_bp, url_prefix='/api')
app.register_blueprint(sentiment_bp, url_prefix='/api')

# Initialize database
db.init_app(app)
with app.app_context():
    db.create_all()

# Health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'service': 'social-media-creator-api',
        'version': '1.0.0'
    }), 200

@app.route('/ready')
def readiness_check():
    """Readiness check endpoint for Kubernetes"""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        return jsonify({
            'status': 'ready',
            'database': 'connected'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'not ready',
            'database': 'disconnected',
            'error': str(e)
        }), 503

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# Serve frontend (React app)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return jsonify({'error': 'Static folder not configured'}), 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            # If no frontend is built, return API info
            return jsonify({
                'service': 'Social Media Creator API',
                'version': '1.0.0',
                'status': 'running',
                'endpoints': {
                    'auth': '/api/auth/*',
                    'content': '/api/content/*',
                    'ai_analysis': '/api/ai/*',
                    'social_accounts': '/api/social-accounts/*',
                    'users': '/api/users/*',
                    'health': '/health',
                    'ready': '/ready'
                }
            })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
