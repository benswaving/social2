import os
import redis
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from celery import Celery
from src.models.user import db

class DatabaseService:
    """Service for managing database connections and operations"""
    
    def __init__(self):
        self.redis_client = None
        self.celery_app = None
        self.setup_redis()
        self.setup_celery()
    
    def setup_redis(self):
        """Setup Redis connection for caching and session management"""
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            self.redis_client.ping()
            logging.info("Redis connection established successfully")
            
        except Exception as e:
            logging.warning(f"Redis connection failed: {str(e)}. Caching will be disabled.")
            self.redis_client = None
    
    def setup_celery(self):
        """Setup Celery for background tasks"""
        try:
            broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1')
            result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
            
            self.celery_app = Celery(
                'social_media_creator',
                broker=broker_url,
                backend=result_backend,
                include=['src.tasks']
            )
            
            # Configure Celery
            self.celery_app.conf.update(
                task_serializer='json',
                accept_content=['json'],
                result_serializer='json',
                timezone='UTC',
                enable_utc=True,
                task_track_started=True,
                task_time_limit=30 * 60,  # 30 minutes
                task_soft_time_limit=25 * 60,  # 25 minutes
                worker_prefetch_multiplier=1,
                worker_max_tasks_per_child=1000,
            )
            
            logging.info("Celery configured successfully")
            
        except Exception as e:
            logging.warning(f"Celery setup failed: {str(e)}. Background tasks will be disabled.")
            self.celery_app = None
    
    def get_postgresql_config(self) -> Dict[str, Any]:
        """Get PostgreSQL configuration for production"""
        return {
            'SQLALCHEMY_DATABASE_URI': os.getenv(
                'DATABASE_URL',
                'postgresql://postgres:password@localhost:5432/social_media_creator'
            ),
            'SQLALCHEMY_ENGINE_OPTIONS': {
                'poolclass': QueuePool,
                'pool_size': 10,
                'pool_recycle': 3600,
                'pool_pre_ping': True,
                'max_overflow': 20,
                'pool_timeout': 30,
                'echo': os.getenv('DATABASE_ECHO', 'false').lower() == 'true'
            }
        }
    
    def test_database_connection(self) -> Dict[str, Any]:
        """Test database connection and return status"""
        try:
            # Test SQLAlchemy connection
            db.session.execute(text('SELECT 1'))
            db_status = 'connected'
            db_error = None
        except Exception as e:
            db_status = 'disconnected'
            db_error = str(e)
        
        # Test Redis connection
        redis_status = 'disconnected'
        redis_error = None
        if self.redis_client:
            try:
                self.redis_client.ping()
                redis_status = 'connected'
            except Exception as e:
                redis_error = str(e)
        
        return {
            'database': {
                'status': db_status,
                'error': db_error
            },
            'redis': {
                'status': redis_status,
                'error': redis_error
            },
            'overall_status': 'healthy' if db_status == 'connected' else 'unhealthy'
        }
    
    # Cache Management Methods
    def cache_set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """Set value in cache with expiration"""
        if not self.redis_client:
            return False
        
        try:
            serialized_value = json.dumps(value) if not isinstance(value, str) else value
            return self.redis_client.setex(key, expire, serialized_value)
        except Exception as e:
            logging.error(f"Cache set failed for key {key}: {str(e)}")
            return False
    
    def cache_get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.redis_client:
            return None
        
        try:
            value = self.redis_client.get(key)
            if value is None:
                return None
            
            # Try to deserialize JSON, fallback to string
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            logging.error(f"Cache get failed for key {key}: {str(e)}")
            return None
    
    def cache_delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.redis_client:
            return False
        
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logging.error(f"Cache delete failed for key {key}: {str(e)}")
            return False
    
    def cache_exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.redis_client:
            return False
        
        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logging.error(f"Cache exists check failed for key {key}: {str(e)}")
            return False
    
    def cache_expire(self, key: str, seconds: int) -> bool:
        """Set expiration for existing key"""
        if not self.redis_client:
            return False
        
        try:
            return bool(self.redis_client.expire(key, seconds))
        except Exception as e:
            logging.error(f"Cache expire failed for key {key}: {str(e)}")
            return False
    
    def cache_keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern"""
        if not self.redis_client:
            return []
        
        try:
            return self.redis_client.keys(pattern)
        except Exception as e:
            logging.error(f"Cache keys failed for pattern {pattern}: {str(e)}")
            return []
    
    def cache_flush_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.redis_client:
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logging.error(f"Cache flush pattern failed for {pattern}: {str(e)}")
            return 0
    
    # Session Management Methods
    def create_session(self, user_id: str, session_data: Dict[str, Any], expire: int = 86400) -> str:
        """Create user session in Redis"""
        if not self.redis_client:
            return None
        
        try:
            import uuid
            session_id = str(uuid.uuid4())
            session_key = f"session:{session_id}"
            
            session_info = {
                'user_id': user_id,
                'created_at': datetime.utcnow().isoformat(),
                'last_accessed': datetime.utcnow().isoformat(),
                'data': session_data
            }
            
            if self.cache_set(session_key, session_info, expire):
                return session_id
            return None
        except Exception as e:
            logging.error(f"Session creation failed: {str(e)}")
            return None
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        if not self.redis_client:
            return None
        
        try:
            session_key = f"session:{session_id}"
            session_info = self.cache_get(session_key)
            
            if session_info:
                # Update last accessed time
                session_info['last_accessed'] = datetime.utcnow().isoformat()
                self.cache_set(session_key, session_info, 86400)  # Extend for 24 hours
                
            return session_info
        except Exception as e:
            logging.error(f"Session get failed: {str(e)}")
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        if not self.redis_client:
            return False
        
        try:
            session_key = f"session:{session_id}"
            return self.cache_delete(session_key)
        except Exception as e:
            logging.error(f"Session delete failed: {str(e)}")
            return False
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions (called by background task)"""
        if not self.redis_client:
            return 0
        
        try:
            # Redis automatically handles expiration, but we can clean up manually if needed
            session_keys = self.cache_keys("session:*")
            cleaned = 0
            
            for key in session_keys:
                session_info = self.cache_get(key)
                if session_info:
                    last_accessed = datetime.fromisoformat(session_info.get('last_accessed', ''))
                    if datetime.utcnow() - last_accessed > timedelta(days=7):  # 7 days inactive
                        self.cache_delete(key)
                        cleaned += 1
            
            return cleaned
        except Exception as e:
            logging.error(f"Session cleanup failed: {str(e)}")
            return 0
    
    # Rate Limiting Methods
    def check_rate_limit(self, key: str, limit: int, window: int) -> Dict[str, Any]:
        """Check rate limit using sliding window"""
        if not self.redis_client:
            return {'allowed': True, 'remaining': limit}
        
        try:
            current_time = datetime.utcnow().timestamp()
            window_start = current_time - window
            
            # Use Redis sorted set for sliding window
            pipe = self.redis_client.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(key, window)
            
            results = pipe.execute()
            current_count = results[1]
            
            allowed = current_count < limit
            remaining = max(0, limit - current_count - 1)
            
            return {
                'allowed': allowed,
                'remaining': remaining,
                'reset_time': current_time + window,
                'current_count': current_count + 1
            }
            
        except Exception as e:
            logging.error(f"Rate limit check failed for key {key}: {str(e)}")
            return {'allowed': True, 'remaining': limit}
    
    # Background Task Methods
    def queue_task(self, task_name: str, *args, **kwargs) -> Optional[str]:
        """Queue background task"""
        if not self.celery_app:
            logging.warning(f"Celery not available, cannot queue task: {task_name}")
            return None
        
        try:
            task = self.celery_app.send_task(task_name, args=args, kwargs=kwargs)
            return task.id
        except Exception as e:
            logging.error(f"Task queue failed for {task_name}: {str(e)}")
            return None
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status"""
        if not self.celery_app:
            return {'status': 'unavailable'}
        
        try:
            task = self.celery_app.AsyncResult(task_id)
            return {
                'status': task.status,
                'result': task.result,
                'traceback': task.traceback
            }
        except Exception as e:
            logging.error(f"Task status check failed for {task_id}: {str(e)}")
            return {'status': 'error', 'error': str(e)}


# Service instance
database_service = DatabaseService()

