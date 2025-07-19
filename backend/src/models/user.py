from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    company_name = db.Column(db.String(255), nullable=True)
    subscription_tier = db.Column(db.String(50), default='free', nullable=False)
    subscription_expires_at = db.Column(db.DateTime, nullable=True)
    language_preference = db.Column(db.String(10), default='nl', nullable=False)
    timezone = db.Column(db.String(50), default='Europe/Amsterdam', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    social_accounts = db.relationship('SocialMediaAccount', backref='user', lazy=True, cascade='all, delete-orphan')
    content_projects = db.relationship('ContentProject', backref='user', lazy=True, cascade='all, delete-orphan')
    media_files = db.relationship('MediaFile', backref='user', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.email}>'
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self, include_sensitive=False):
        """Convert user to dictionary"""
        data = {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'company_name': self.company_name,
            'subscription_tier': self.subscription_tier,
            'language_preference': self.language_preference,
            'timezone': self.timezone,
            'is_active': self.is_active,
            'email_verified': self.email_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            data['subscription_expires_at'] = self.subscription_expires_at.isoformat() if self.subscription_expires_at else None
            
        return data

class SocialMediaAccount(db.Model):
    __tablename__ = 'social_media_accounts'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    platform = db.Column(db.String(50), nullable=False)
    platform_user_id = db.Column(db.String(255), nullable=False)
    platform_username = db.Column(db.String(255), nullable=True)
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    account_metadata = db.Column(db.JSON, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Constraints
    __table_args__ = (
        db.UniqueConstraint('user_id', 'platform', 'platform_user_id', name='unique_user_platform_account'),
        db.CheckConstraint(platform.in_(['instagram', 'facebook', 'linkedin', 'tiktok', 'twitter']), name='valid_platform')
    )
    
    def to_dict(self, include_tokens=False):
        """Convert social account to dictionary"""
        data = {
            'id': self.id,
            'platform': self.platform,
            'platform_username': self.platform_username,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'account_metadata': self.account_metadata
        }
        
        if include_tokens:
            data['access_token'] = self.access_token
            data['refresh_token'] = self.refresh_token
            data['token_expires_at'] = self.token_expires_at.isoformat() if self.token_expires_at else None
            
        return data

class ContentProject(db.Model):
    __tablename__ = 'content_projects'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    original_prompt = db.Column(db.Text, nullable=False)
    target_platforms = db.Column(db.JSON, nullable=False)  # Array of platform names
    brand_guidelines = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(50), default='draft', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    generated_content = db.relationship('GeneratedContent', backref='project', lazy=True, cascade='all, delete-orphan')
    
    # Constraints
    __table_args__ = (
        db.CheckConstraint(status.in_(['draft', 'generating', 'ready', 'scheduled', 'published', 'failed']), name='valid_status'),
    )
    
    def to_dict(self):
        """Convert content project to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'original_prompt': self.original_prompt,
            'target_platforms': self.target_platforms,
            'brand_guidelines': self.brand_guidelines,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class GeneratedContent(db.Model):
    __tablename__ = 'generated_content'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(db.String(36), db.ForeignKey('content_projects.id'), nullable=False)
    platform = db.Column(db.String(50), nullable=False)
    content_type = db.Column(db.String(50), nullable=False)
    generated_text = db.Column(db.Text, nullable=True)
    generated_hashtags = db.Column(db.String(500), nullable=True)
    media_urls = db.Column(db.JSON, nullable=True)  # Array of URLs
    tone_of_voice = db.Column(db.String(100), nullable=True)
    generation_parameters = db.Column(db.JSON, nullable=True)
    ai_model_used = db.Column(db.String(100), nullable=True)
    generation_cost = db.Column(db.Numeric(10, 4), nullable=True)
    quality_score = db.Column(db.Numeric(3, 2), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    scheduled_posts = db.relationship('ScheduledPost', backref='content', lazy=True, cascade='all, delete-orphan')
    
    # Constraints
    __table_args__ = (
        db.CheckConstraint(platform.in_(['instagram', 'facebook', 'linkedin', 'tiktok', 'twitter']), name='valid_platform'),
        db.CheckConstraint(content_type.in_(['text', 'image', 'video', 'carousel']), name='valid_content_type')
    )
    
    def to_dict(self):
        """Convert generated content to dictionary"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'platform': self.platform,
            'content_type': self.content_type,
            'generated_text': self.generated_text,
            'generated_hashtags': self.generated_hashtags,
            'media_urls': self.media_urls,
            'tone_of_voice': self.tone_of_voice,
            'generation_parameters': self.generation_parameters,
            'ai_model_used': self.ai_model_used,
            'generation_cost': float(self.generation_cost) if self.generation_cost else None,
            'quality_score': float(self.quality_score) if self.quality_score else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ScheduledPost(db.Model):
    __tablename__ = 'scheduled_posts'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content_id = db.Column(db.String(36), db.ForeignKey('generated_content.id'), nullable=False)
    social_account_id = db.Column(db.String(36), db.ForeignKey('social_media_accounts.id'), nullable=False)
    scheduled_for = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), default='scheduled', nullable=False)
    platform_post_id = db.Column(db.String(255), nullable=True)
    published_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    social_account = db.relationship('SocialMediaAccount', backref='scheduled_posts')
    
    # Constraints
    __table_args__ = (
        db.CheckConstraint(status.in_(['scheduled', 'publishing', 'published', 'failed', 'cancelled']), name='valid_status'),
    )
    
    def to_dict(self):
        """Convert scheduled post to dictionary"""
        return {
            'id': self.id,
            'content_id': self.content_id,
            'social_account_id': self.social_account_id,
            'scheduled_for': self.scheduled_for.isoformat() if self.scheduled_for else None,
            'status': self.status,
            'platform_post_id': self.platform_post_id,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class MediaFile(db.Model):
    __tablename__ = 'media_files'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=True)
    file_type = db.Column(db.String(50), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    storage_path = db.Column(db.Text, nullable=False)
    storage_provider = db.Column(db.String(50), default='local', nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    dimensions = db.Column(db.JSON, nullable=True)  # {width: 1080, height: 1080}
    duration = db.Column(db.Integer, nullable=True)  # for videos in seconds
    file_metadata = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Constraints
    __table_args__ = (
        db.CheckConstraint(file_type.in_(['image', 'video', 'audio']), name='valid_file_type'),
    )
    
    def to_dict(self):
        """Convert media file to dictionary"""
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'storage_path': self.storage_path,
            'storage_provider': self.storage_provider,
            'mime_type': self.mime_type,
            'dimensions': self.dimensions,
            'duration': self.duration,
            'file_metadata': self.file_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
