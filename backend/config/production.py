import os
from datetime import timedelta

class ProductionConfig:
    """Production configuration for the AI Social Media Creator API"""
    
    # Basic Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(32))
    DEBUG = False
    TESTING = False
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql://postgres:password@localhost:5432/social_media_creator'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 20,
        'pool_timeout': 30,
        'echo': False  # Set to True for SQL debugging
    }
    
    # Redis Configuration
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 3600  # 1 hour
    
    # Session Configuration
    SESSION_TYPE = 'redis'
    SESSION_REDIS = REDIS_URL
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'smc:'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Celery Configuration
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = 'UTC'
    CELERY_ENABLE_UTC = True
    
    # Security Configuration
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    
    # CORS Configuration
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')
    CORS_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
    CORS_ALLOW_HEADERS = ['Content-Type', 'Authorization']
    
    # Rate Limiting Configuration
    RATELIMIT_STORAGE_URL = REDIS_URL
    RATELIMIT_DEFAULT = "1000 per hour"
    RATELIMIT_HEADERS_ENABLED = True
    
    # File Upload Configuration
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file size
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/app/uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}
    
    # Media Storage Configuration
    MEDIA_STORAGE_PATH = os.getenv('MEDIA_STORAGE_PATH', '/app/media')
    MEDIA_CDN_URL = os.getenv('MEDIA_CDN_URL', '')
    
    # AI Service Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')
    OPENAI_MAX_TOKENS = int(os.getenv('OPENAI_MAX_TOKENS', '2000'))
    OPENAI_TEMPERATURE = float(os.getenv('OPENAI_TEMPERATURE', '0.7'))
    
    # Social Media API Configuration
    INSTAGRAM_CLIENT_ID = os.getenv('INSTAGRAM_CLIENT_ID')
    INSTAGRAM_CLIENT_SECRET = os.getenv('INSTAGRAM_CLIENT_SECRET')
    INSTAGRAM_REDIRECT_URI = os.getenv('INSTAGRAM_REDIRECT_URI')
    
    FACEBOOK_CLIENT_ID = os.getenv('FACEBOOK_CLIENT_ID')
    FACEBOOK_CLIENT_SECRET = os.getenv('FACEBOOK_CLIENT_SECRET')
    FACEBOOK_REDIRECT_URI = os.getenv('FACEBOOK_REDIRECT_URI')
    
    LINKEDIN_CLIENT_ID = os.getenv('LINKEDIN_CLIENT_ID')
    LINKEDIN_CLIENT_SECRET = os.getenv('LINKEDIN_CLIENT_SECRET')
    LINKEDIN_REDIRECT_URI = os.getenv('LINKEDIN_REDIRECT_URI')
    
    TWITTER_CLIENT_ID = os.getenv('TWITTER_CLIENT_ID')
    TWITTER_CLIENT_SECRET = os.getenv('TWITTER_CLIENT_SECRET')
    TWITTER_REDIRECT_URI = os.getenv('TWITTER_REDIRECT_URI')
    
    TIKTOK_CLIENT_ID = os.getenv('TIKTOK_CLIENT_ID')
    TIKTOK_CLIENT_SECRET = os.getenv('TIKTOK_CLIENT_SECRET')
    TIKTOK_REDIRECT_URI = os.getenv('TIKTOK_REDIRECT_URI')
    
    # Encryption Configuration
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s %(message)s'
    
    # Monitoring Configuration
    SENTRY_DSN = os.getenv('SENTRY_DSN')
    
    # Email Configuration (for notifications)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.getenv('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')
    
    # Backup Configuration
    BACKUP_ENABLED = os.getenv('BACKUP_ENABLED', 'true').lower() == 'true'
    BACKUP_SCHEDULE = os.getenv('BACKUP_SCHEDULE', '0 2 * * *')  # Daily at 2 AM
    BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))
    
    # Performance Configuration
    SQLALCHEMY_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '10'))
    SQLALCHEMY_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '20'))
    SQLALCHEMY_POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '30'))
    SQLALCHEMY_POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', '3600'))
    
    # Feature Flags
    ENABLE_ANALYTICS = os.getenv('ENABLE_ANALYTICS', 'true').lower() == 'true'
    ENABLE_SCHEDULING = os.getenv('ENABLE_SCHEDULING', 'true').lower() == 'true'
    ENABLE_MEDIA_GENERATION = os.getenv('ENABLE_MEDIA_GENERATION', 'true').lower() == 'true'
    ENABLE_OAUTH = os.getenv('ENABLE_OAUTH', 'true').lower() == 'true'
    
    @staticmethod
    def init_app(app):
        """Initialize application with production configuration"""
        
        # Setup logging
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not app.debug:
            # File logging
            if not os.path.exists('logs'):
                os.mkdir('logs')
            
            file_handler = RotatingFileHandler(
                'logs/social_media_creator.log',
                maxBytes=10240000,  # 10MB
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(ProductionConfig.LOG_FORMAT))
            file_handler.setLevel(getattr(logging, ProductionConfig.LOG_LEVEL))
            app.logger.addHandler(file_handler)
            
            app.logger.setLevel(getattr(logging, ProductionConfig.LOG_LEVEL))
            app.logger.info('Social Media Creator API startup')
        
        # Setup Sentry for error tracking
        if ProductionConfig.SENTRY_DSN:
            try:
                import sentry_sdk
                from sentry_sdk.integrations.flask import FlaskIntegration
                from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
                from sentry_sdk.integrations.redis import RedisIntegration
                
                sentry_sdk.init(
                    dsn=ProductionConfig.SENTRY_DSN,
                    integrations=[
                        FlaskIntegration(),
                        SqlalchemyIntegration(),
                        RedisIntegration()
                    ],
                    traces_sample_rate=0.1,
                    environment='production'
                )
            except ImportError:
                app.logger.warning('Sentry SDK not installed, error tracking disabled')


class DevelopmentConfig:
    """Development configuration"""
    
    DEBUG = True
    TESTING = False
    SECRET_KEY = 'dev-secret-key-change-in-production'
    
    # Use SQLite for development
    SQLALCHEMY_DATABASE_URI = 'sqlite:///social_media_creator_dev.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = True
    
    # Redis (optional for development)
    REDIS_URL = 'redis://localhost:6379/0'
    
    # Relaxed CORS for development
    CORS_ORIGINS = ['http://localhost:3000', 'http://localhost:5173', 'http://localhost:5174']
    
    # Development media storage
    MEDIA_STORAGE_PATH = './media_dev'
    
    # AI Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')


class TestingConfig:
    """Testing configuration"""
    
    TESTING = True
    DEBUG = True
    SECRET_KEY = 'test-secret-key'
    
    # In-memory SQLite for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Disable Redis for testing
    REDIS_URL = None
    
    # Test media storage
    MEDIA_STORAGE_PATH = './media_test'
    
    # Mock AI services for testing
    OPENAI_API_KEY = 'test-key'


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

