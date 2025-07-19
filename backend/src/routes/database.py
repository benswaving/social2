from flask import Blueprint, jsonify, request
from src.routes.auth import token_required
from src.services.database_service import database_service
from src.models.user import db, User
import logging

database_bp = Blueprint('database', __name__)

@database_bp.route('/database/health', methods=['GET'])
def database_health():
    """Check database and cache health"""
    try:
        health_status = database_service.test_database_connection()
        
        status_code = 200 if health_status['overall_status'] == 'healthy' else 503
        
        return jsonify({
            'status': health_status['overall_status'],
            'components': health_status,
            'timestamp': database_service.cache_get('health_check_time') or 'unknown'
        }), status_code
        
    except Exception as e:
        logging.error(f"Database health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503

@database_bp.route('/database/cache/stats', methods=['GET'])
@token_required
def cache_stats(current_user):
    """Get cache statistics (admin only)"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        if not database_service.redis_client:
            return jsonify({'error': 'Redis not available'}), 503
        
        # Get Redis info
        redis_info = database_service.redis_client.info()
        
        # Get key statistics
        total_keys = len(database_service.cache_keys("*"))
        session_keys = len(database_service.cache_keys("session:*"))
        rate_limit_keys = len(database_service.cache_keys("rate_limit:*"))
        content_cache_keys = len(database_service.cache_keys("content:*"))
        
        return jsonify({
            'redis_info': {
                'connected_clients': redis_info.get('connected_clients'),
                'used_memory': redis_info.get('used_memory_human'),
                'total_commands_processed': redis_info.get('total_commands_processed'),
                'keyspace_hits': redis_info.get('keyspace_hits'),
                'keyspace_misses': redis_info.get('keyspace_misses'),
                'uptime_in_seconds': redis_info.get('uptime_in_seconds')
            },
            'key_statistics': {
                'total_keys': total_keys,
                'session_keys': session_keys,
                'rate_limit_keys': rate_limit_keys,
                'content_cache_keys': content_cache_keys
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Cache stats failed: {str(e)}")
        return jsonify({'error': 'Failed to get cache statistics'}), 500

@database_bp.route('/database/cache/flush', methods=['POST'])
@token_required
def flush_cache(current_user):
    """Flush cache by pattern (admin only)"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        data = request.get_json()
        pattern = data.get('pattern', '*')
        
        if pattern == '*':
            return jsonify({'error': 'Cannot flush all keys, specify a pattern'}), 400
        
        deleted_count = database_service.cache_flush_pattern(pattern)
        
        return jsonify({
            'message': f'Flushed cache for pattern: {pattern}',
            'deleted_keys': deleted_count
        }), 200
        
    except Exception as e:
        logging.error(f"Cache flush failed: {str(e)}")
        return jsonify({'error': 'Failed to flush cache'}), 500

@database_bp.route('/database/sessions/cleanup', methods=['POST'])
@token_required
def cleanup_sessions(current_user):
    """Clean up expired sessions (admin only)"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        cleaned_count = database_service.cleanup_expired_sessions()
        
        return jsonify({
            'message': 'Session cleanup completed',
            'cleaned_sessions': cleaned_count
        }), 200
        
    except Exception as e:
        logging.error(f"Session cleanup failed: {str(e)}")
        return jsonify({'error': 'Failed to cleanup sessions'}), 500

@database_bp.route('/database/rate-limit/check', methods=['POST'])
@token_required
def check_rate_limit(current_user):
    """Check rate limit for a key"""
    try:
        data = request.get_json()
        
        if not data.get('key'):
            return jsonify({'error': 'Key is required'}), 400
        
        key = data['key']
        limit = data.get('limit', 100)
        window = data.get('window', 3600)  # 1 hour
        
        result = database_service.check_rate_limit(key, limit, window)
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Rate limit check failed: {str(e)}")
        return jsonify({'error': 'Failed to check rate limit'}), 500

@database_bp.route('/database/backup/create', methods=['POST'])
@token_required
def create_backup(current_user):
    """Create database backup (admin only)"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        # Queue backup task
        task_id = database_service.queue_task('create_database_backup')
        
        if task_id:
            return jsonify({
                'message': 'Backup task queued',
                'task_id': task_id
            }), 202
        else:
            return jsonify({'error': 'Failed to queue backup task'}), 500
        
    except Exception as e:
        logging.error(f"Backup creation failed: {str(e)}")
        return jsonify({'error': 'Failed to create backup'}), 500

@database_bp.route('/database/tasks/<task_id>/status', methods=['GET'])
@token_required
def get_task_status(current_user, task_id):
    """Get background task status"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        status = database_service.get_task_status(task_id)
        
        return jsonify({
            'task_id': task_id,
            'status': status
        }), 200
        
    except Exception as e:
        logging.error(f"Task status check failed: {str(e)}")
        return jsonify({'error': 'Failed to get task status'}), 500

@database_bp.route('/database/migrate', methods=['POST'])
@token_required
def run_migrations(current_user):
    """Run database migrations (admin only)"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        # Create all tables
        db.create_all()
        
        return jsonify({
            'message': 'Database migrations completed successfully'
        }), 200
        
    except Exception as e:
        logging.error(f"Database migration failed: {str(e)}")
        return jsonify({'error': 'Failed to run migrations'}), 500

@database_bp.route('/database/optimize', methods=['POST'])
@token_required
def optimize_database(current_user):
    """Optimize database performance (admin only)"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        # Queue optimization task
        task_id = database_service.queue_task('optimize_database')
        
        if task_id:
            return jsonify({
                'message': 'Database optimization task queued',
                'task_id': task_id
            }), 202
        else:
            return jsonify({'error': 'Failed to queue optimization task'}), 500
        
    except Exception as e:
        logging.error(f"Database optimization failed: {str(e)}")
        return jsonify({'error': 'Failed to optimize database'}), 500

