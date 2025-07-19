import os
import re
import hashlib
import secrets
import bleach
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from functools import wraps
from flask import request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from src.services.database_service import database_service
from src.models.user import User, db

class SecurityService:
    """Service for handling security, validation, and GDPR compliance"""
    
    def __init__(self):
        # Input validation patterns
        self.validation_patterns = {
            'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
            'username': re.compile(r'^[a-zA-Z0-9_]{3,30}$'),
            'password': re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'),
            'phone': re.compile(r'^\+?1?\d{9,15}$'),
            'url': re.compile(r'^https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?$'),
            'uuid': re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'),
            'alphanumeric': re.compile(r'^[a-zA-Z0-9]+$'),
            'safe_text': re.compile(r'^[a-zA-Z0-9\s\-_.,!?()]+$')
        }
        
        # XSS protection configuration
        self.allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'blockquote', 'code', 'pre', 'a', 'img'
        ]
        
        self.allowed_attributes = {
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'width', 'height'],
            '*': ['class']
        }
        
        # Rate limiting configuration
        self.rate_limits = {
            'login': {'limit': 5, 'window': 900},  # 5 attempts per 15 minutes
            'register': {'limit': 3, 'window': 3600},  # 3 registrations per hour
            'api_general': {'limit': 1000, 'window': 3600},  # 1000 requests per hour
            'api_media': {'limit': 50, 'window': 3600},  # 50 media generations per hour
            'api_oauth': {'limit': 10, 'window': 600},  # 10 OAuth attempts per 10 minutes
        }
        
        # GDPR data categories
        self.gdpr_data_categories = {
            'personal_identifiable': ['email', 'name', 'phone', 'address'],
            'authentication': ['password_hash', 'tokens', 'sessions'],
            'behavioral': ['login_history', 'content_history', 'preferences'],
            'technical': ['ip_address', 'user_agent', 'device_info'],
            'content': ['posts', 'media_files', 'social_accounts']
        }
    
    def validate_input(self, data: Dict[str, Any], validation_rules: Dict[str, str]) -> Tuple[bool, List[str]]:
        """Validate input data against rules"""
        errors = []
        
        for field, rule in validation_rules.items():
            value = data.get(field)
            
            # Check required fields
            if rule.startswith('required'):
                if not value or (isinstance(value, str) and not value.strip()):
                    errors.append(f"{field} is required")
                    continue
                
                # Extract pattern from rule (e.g., "required|email")
                if '|' in rule:
                    pattern_name = rule.split('|')[1]
                else:
                    continue
            else:
                pattern_name = rule
                if not value:  # Optional field, skip if empty
                    continue
            
            # Validate against pattern
            if pattern_name in self.validation_patterns:
                if not self.validation_patterns[pattern_name].match(str(value)):
                    errors.append(f"{field} format is invalid")
            
            # Additional validations
            if pattern_name == 'password' and value:
                password_errors = self.validate_password_strength(value)
                errors.extend([f"{field}: {error}" for error in password_errors])
        
        return len(errors) == 0, errors
    
    def validate_password_strength(self, password: str) -> List[str]:
        """Validate password strength"""
        errors = []
        
        if len(password) < 8:
            errors.append("must be at least 8 characters long")
        
        if not re.search(r'[a-z]', password):
            errors.append("must contain at least one lowercase letter")
        
        if not re.search(r'[A-Z]', password):
            errors.append("must contain at least one uppercase letter")
        
        if not re.search(r'\d', password):
            errors.append("must contain at least one digit")
        
        if not re.search(r'[@$!%*?&]', password):
            errors.append("must contain at least one special character (@$!%*?&)")
        
        # Check for common passwords
        common_passwords = [
            'password', '123456', '123456789', 'qwerty', 'abc123', 'password123',
            'admin', 'letmein', 'welcome', 'monkey', '1234567890'
        ]
        
        if password.lower() in common_passwords:
            errors.append("cannot be a common password")
        
        return errors
    
    def sanitize_html(self, content: str) -> str:
        """Sanitize HTML content to prevent XSS"""
        if not content:
            return ""
        
        return bleach.clean(
            content,
            tags=self.allowed_tags,
            attributes=self.allowed_attributes,
            strip=True
        )
    
    def sanitize_text(self, text: str, max_length: int = None) -> str:
        """Sanitize plain text input"""
        if not text:
            return ""
        
        # Remove null bytes and control characters
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Normalize whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        # Truncate if max_length specified
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized
    
    def check_rate_limit(self, identifier: str, limit_type: str = 'api_general') -> Dict[str, Any]:
        """Check rate limit for identifier"""
        if limit_type not in self.rate_limits:
            return {'allowed': True, 'remaining': 1000}
        
        config = self.rate_limits[limit_type]
        key = f"rate_limit:{limit_type}:{identifier}"
        
        return database_service.check_rate_limit(
            key=key,
            limit=config['limit'],
            window=config['window']
        )
    
    def rate_limit_decorator(self, limit_type: str = 'api_general'):
        """Decorator for rate limiting endpoints"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Get identifier (IP address or user ID)
                identifier = request.remote_addr
                
                # Try to get user ID if authenticated
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    try:
                        from src.routes.auth import decode_token
                        token = auth_header.split(' ')[1]
                        payload = decode_token(token)
                        if payload:
                            identifier = f"user:{payload['user_id']}"
                    except:
                        pass  # Use IP address as fallback
                
                # Check rate limit
                rate_limit_result = self.check_rate_limit(identifier, limit_type)
                
                if not rate_limit_result['allowed']:
                    return jsonify({
                        'error': 'Rate limit exceeded',
                        'retry_after': rate_limit_result.get('reset_time', 3600)
                    }), 429
                
                # Add rate limit headers
                response = f(*args, **kwargs)
                if hasattr(response, 'headers'):
                    response.headers['X-RateLimit-Limit'] = str(self.rate_limits[limit_type]['limit'])
                    response.headers['X-RateLimit-Remaining'] = str(rate_limit_result['remaining'])
                    response.headers['X-RateLimit-Reset'] = str(int(rate_limit_result.get('reset_time', 0)))
                
                return response
            
            return decorated_function
        return decorator
    
    def log_security_event(self, event_type: str, user_id: str = None, details: Dict[str, Any] = None):
        """Log security events for monitoring"""
        try:
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'event_type': event_type,
                'user_id': user_id,
                'ip_address': request.remote_addr if request else None,
                'user_agent': request.headers.get('User-Agent') if request else None,
                'details': details or {}
            }
            
            # Store in cache for recent events
            cache_key = f"security_events:{datetime.utcnow().strftime('%Y-%m-%d')}"
            events = database_service.cache_get(cache_key) or []
            events.append(log_entry)
            
            # Keep only last 1000 events per day
            if len(events) > 1000:
                events = events[-1000:]
            
            database_service.cache_set(cache_key, events, 86400)  # 24 hours
            
            # Log to application logger
            logging.info(f"Security Event: {event_type} - User: {user_id} - IP: {log_entry['ip_address']}")
            
        except Exception as e:
            logging.error(f"Failed to log security event: {str(e)}")
    
    def hash_password(self, password: str) -> str:
        """Hash password securely"""
        return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return check_password_hash(password_hash, password)
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure token"""
        return secrets.token_urlsafe(length)
    
    def hash_sensitive_data(self, data: str) -> str:
        """Hash sensitive data for storage"""
        salt = os.getenv('DATA_SALT', 'default-salt-change-in-production')
        return hashlib.pbkdf2_hmac('sha256', data.encode(), salt.encode(), 100000).hex()
    
    # GDPR Compliance Methods
    def get_user_data_export(self, user_id: str) -> Dict[str, Any]:
        """Export all user data for GDPR compliance"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {'error': 'User not found'}
            
            # Collect all user data
            user_data = {
                'personal_information': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'full_name': user.full_name,
                    'created_at': user.created_at.isoformat(),
                    'updated_at': user.updated_at.isoformat(),
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'is_active': user.is_active,
                    'preferences': user.preferences
                },
                'content_projects': [],
                'social_media_accounts': [],
                'media_files': [],
                'login_history': [],
                'api_usage': []
            }
            
            # Get content projects
            from src.models.user import ContentProject
            projects = ContentProject.query.filter_by(user_id=user_id).all()
            for project in projects:
                user_data['content_projects'].append({
                    'id': project.id,
                    'title': project.title,
                    'content': project.content,
                    'platform': project.platform,
                    'status': project.status,
                    'created_at': project.created_at.isoformat(),
                    'updated_at': project.updated_at.isoformat()
                })
            
            # Get social media accounts (without sensitive tokens)
            from src.models.user import SocialMediaAccount
            accounts = SocialMediaAccount.query.filter_by(user_id=user_id).all()
            for account in accounts:
                user_data['social_media_accounts'].append({
                    'id': account.id,
                    'platform': account.platform,
                    'account_name': account.account_name,
                    'account_username': account.account_username,
                    'connected_at': account.connected_at.isoformat(),
                    'is_active': account.is_active
                })
            
            # Get media files
            from src.models.user import MediaFile
            media_files = MediaFile.query.filter_by(user_id=user_id).all()
            for media_file in media_files:
                user_data['media_files'].append({
                    'id': media_file.id,
                    'filename': media_file.filename,
                    'file_type': media_file.file_type,
                    'file_size': media_file.file_size,
                    'created_at': media_file.created_at.isoformat()
                })
            
            return {
                'export_date': datetime.utcnow().isoformat(),
                'user_data': user_data,
                'data_categories': list(self.gdpr_data_categories.keys())
            }
            
        except Exception as e:
            logging.error(f"Data export failed for user {user_id}: {str(e)}")
            return {'error': 'Failed to export user data'}
    
    def delete_user_data(self, user_id: str, categories: List[str] = None) -> Dict[str, Any]:
        """Delete user data for GDPR compliance"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {'error': 'User not found'}
            
            deleted_items = {
                'content_projects': 0,
                'social_media_accounts': 0,
                'media_files': 0,
                'sessions': 0,
                'cache_entries': 0
            }
            
            # If no categories specified, delete everything
            if not categories:
                categories = list(self.gdpr_data_categories.keys())
            
            # Delete based on categories
            if 'content' in categories:
                # Delete content projects
                from src.models.user import ContentProject
                projects = ContentProject.query.filter_by(user_id=user_id).all()
                for project in projects:
                    db.session.delete(project)
                    deleted_items['content_projects'] += 1
                
                # Delete media files
                from src.models.user import MediaFile
                media_files = MediaFile.query.filter_by(user_id=user_id).all()
                for media_file in media_files:
                    # Delete physical file
                    if os.path.exists(media_file.storage_path):
                        os.remove(media_file.storage_path)
                    db.session.delete(media_file)
                    deleted_items['media_files'] += 1
            
            if 'behavioral' in categories or 'authentication' in categories:
                # Delete social media accounts
                from src.models.user import SocialMediaAccount
                accounts = SocialMediaAccount.query.filter_by(user_id=user_id).all()
                for account in accounts:
                    db.session.delete(account)
                    deleted_items['social_media_accounts'] += 1
                
                # Delete sessions from cache
                session_keys = database_service.cache_keys(f"session:*")
                for key in session_keys:
                    session_data = database_service.cache_get(key)
                    if session_data and session_data.get('user_id') == user_id:
                        database_service.cache_delete(key)
                        deleted_items['sessions'] += 1
                
                # Delete user-specific cache entries
                cache_patterns = [
                    f"user:{user_id}:*",
                    f"rate_limit:*:user:{user_id}",
                    f"content:{user_id}:*"
                ]
                
                for pattern in cache_patterns:
                    deleted_items['cache_entries'] += database_service.cache_flush_pattern(pattern)
            
            # If deleting personal_identifiable, anonymize the user record
            if 'personal_identifiable' in categories:
                user.email = f"deleted_{user.id}@example.com"
                user.username = f"deleted_{user.id}"
                user.full_name = "Deleted User"
                user.is_active = False
                user.preferences = {}
            
            db.session.commit()
            
            # Log the deletion
            self.log_security_event('gdpr_data_deletion', user_id, {
                'categories': categories,
                'deleted_items': deleted_items
            })
            
            return {
                'success': True,
                'message': 'User data deleted successfully',
                'deleted_items': deleted_items,
                'categories_processed': categories
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Data deletion failed for user {user_id}: {str(e)}")
            return {'error': 'Failed to delete user data'}
    
    def anonymize_user_data(self, user_id: str) -> Dict[str, Any]:
        """Anonymize user data while preserving analytics"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {'error': 'User not found'}
            
            # Generate anonymous identifier
            anonymous_id = hashlib.sha256(f"{user_id}{secrets.token_hex(16)}".encode()).hexdigest()[:16]
            
            # Anonymize user record
            user.email = f"anonymous_{anonymous_id}@example.com"
            user.username = f"anonymous_{anonymous_id}"
            user.full_name = "Anonymous User"
            user.preferences = {}
            
            # Anonymize content projects (keep content for analytics but remove personal identifiers)
            from src.models.user import ContentProject
            projects = ContentProject.query.filter_by(user_id=user_id).all()
            for project in projects:
                project.title = f"Anonymous Project {project.id}"
                # Keep content and metadata for analytics
            
            db.session.commit()
            
            self.log_security_event('gdpr_data_anonymization', user_id, {
                'anonymous_id': anonymous_id
            })
            
            return {
                'success': True,
                'message': 'User data anonymized successfully',
                'anonymous_id': anonymous_id
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Data anonymization failed for user {user_id}: {str(e)}")
            return {'error': 'Failed to anonymize user data'}
    
    def get_consent_status(self, user_id: str) -> Dict[str, Any]:
        """Get user's consent status for different data processing activities"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {'error': 'User not found'}
            
            consent_data = user.preferences.get('gdpr_consent', {})
            
            default_consents = {
                'essential': True,  # Required for service functionality
                'analytics': False,
                'marketing': False,
                'third_party_sharing': False,
                'ai_training': False
            }
            
            # Merge with user's actual consents
            for key in default_consents:
                if key not in consent_data:
                    consent_data[key] = default_consents[key]
            
            return {
                'user_id': user_id,
                'consent_status': consent_data,
                'last_updated': user.preferences.get('gdpr_consent_updated', user.created_at.isoformat())
            }
            
        except Exception as e:
            logging.error(f"Failed to get consent status for user {user_id}: {str(e)}")
            return {'error': 'Failed to get consent status'}
    
    def update_consent(self, user_id: str, consent_updates: Dict[str, bool]) -> Dict[str, Any]:
        """Update user's consent preferences"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {'error': 'User not found'}
            
            if not user.preferences:
                user.preferences = {}
            
            if 'gdpr_consent' not in user.preferences:
                user.preferences['gdpr_consent'] = {}
            
            # Update consents
            for consent_type, value in consent_updates.items():
                if consent_type != 'essential':  # Essential consent cannot be revoked
                    user.preferences['gdpr_consent'][consent_type] = bool(value)
            
            user.preferences['gdpr_consent_updated'] = datetime.utcnow().isoformat()
            
            # Mark the user object as modified for SQLAlchemy
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(user, 'preferences')
            
            db.session.commit()
            
            self.log_security_event('gdpr_consent_update', user_id, {
                'consent_updates': consent_updates
            })
            
            return {
                'success': True,
                'message': 'Consent preferences updated successfully',
                'updated_consents': consent_updates
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Failed to update consent for user {user_id}: {str(e)}")
            return {'error': 'Failed to update consent preferences'}


# Service instance
security_service = SecurityService()

