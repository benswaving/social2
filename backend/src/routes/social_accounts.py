from flask import Blueprint, jsonify, request
from src.models.user import SocialMediaAccount, ScheduledPost, db
from src.routes.auth import token_required
from src.services.social_media_service import social_media_service
from datetime import datetime, timedelta
import uuid

social_accounts_bp = Blueprint('social_accounts', __name__)

@social_accounts_bp.route('/social-accounts', methods=['GET'])
@token_required
def get_social_accounts(current_user):
    """Get all social media accounts for current user"""
    try:
        accounts = SocialMediaAccount.query.filter_by(user_id=current_user.id).all()
        
        return jsonify({
            'accounts': [
                {
                    'id': account.id,
                    'platform': account.platform,
                    'account_name': account.account_name,
                    'account_username': account.account_username,
                    'is_active': account.is_active,
                    'posts_count': account.posts_count,
                    'followers_count': account.followers_count,
                    'last_post_at': account.last_post_at.isoformat() if account.last_post_at else None,
                    'connected_at': account.connected_at.isoformat(),
                    'expires_at': account.expires_at.isoformat() if account.expires_at else None
                }
                for account in accounts
            ]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch social accounts', 'details': str(e)}), 500

@social_accounts_bp.route('/social-accounts', methods=['POST'])
@token_required
def connect_social_account(current_user):
    """Connect a new social media account"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['platform', 'account_name', 'credentials']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        platform = data['platform']
        account_name = data['account_name']
        credentials = data['credentials']
        
        # Validate platform
        supported_platforms = ['instagram', 'linkedin', 'twitter', 'facebook', 'tiktok']
        if platform not in supported_platforms:
            return jsonify({'error': f'Platform {platform} not supported'}), 400
        
        # Validate credentials
        if not social_media_service.validate_account_credentials(platform, credentials):
            return jsonify({'error': 'Invalid credentials for platform'}), 400
        
        # Check if account already exists
        existing_account = SocialMediaAccount.query.filter_by(
            user_id=current_user.id,
            platform=platform,
            account_username=data.get('account_username', account_name)
        ).first()
        
        if existing_account:
            return jsonify({'error': 'Account already connected'}), 409
        
        # Create new social media account
        account = SocialMediaAccount(
            user_id=current_user.id,
            platform=platform,
            account_name=account_name,
            account_username=data.get('account_username', account_name),
            credentials=credentials,  # In production, encrypt these
            is_active=True,
            connected_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=60) if data.get('expires_in') else None
        )
        
        db.session.add(account)
        db.session.commit()
        
        return jsonify({
            'message': 'Social media account connected successfully',
            'account': {
                'id': account.id,
                'platform': account.platform,
                'account_name': account.account_name,
                'account_username': account.account_username,
                'connected_at': account.connected_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to connect social account', 'details': str(e)}), 500

@social_accounts_bp.route('/social-accounts/<account_id>', methods=['DELETE'])
@token_required
def disconnect_social_account(current_user, account_id):
    """Disconnect a social media account"""
    try:
        account = SocialMediaAccount.query.filter_by(
            id=account_id,
            user_id=current_user.id
        ).first()
        
        if not account:
            return jsonify({'error': 'Social media account not found'}), 404
        
        # Cancel any scheduled posts for this account
        ScheduledPost.query.filter_by(
            social_account_id=account_id,
            status='scheduled'
        ).update({'status': 'cancelled'})
        
        # Delete the account
        db.session.delete(account)
        db.session.commit()
        
        return jsonify({'message': 'Social media account disconnected successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to disconnect social account', 'details': str(e)}), 500

@social_accounts_bp.route('/social-accounts/<account_id>/publish', methods=['POST'])
@token_required
def publish_to_account(current_user, account_id):
    """Publish content to a specific social media account"""
    try:
        # Verify account ownership
        account = SocialMediaAccount.query.filter_by(
            id=account_id,
            user_id=current_user.id
        ).first()
        
        if not account:
            return jsonify({'error': 'Social media account not found'}), 404
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('content'):
            return jsonify({'error': 'Content is required'}), 400
        
        content = data['content']
        content_type = data.get('content_type', 'text')
        media_path = data.get('media_path')
        hashtags = data.get('hashtags')
        
        # Publish content
        result = social_media_service.publish_content(
            account_id=account_id,
            content=content,
            content_type=content_type,
            media_path=media_path,
            hashtags=hashtags
        )
        
        if result.get('success'):
            return jsonify({
                'message': 'Content published successfully',
                'result': result
            }), 200
        else:
            return jsonify({
                'error': 'Publishing failed',
                'details': result.get('error')
            }), 400
        
    except Exception as e:
        return jsonify({'error': 'Publishing failed', 'details': str(e)}), 500

@social_accounts_bp.route('/social-accounts/<account_id>/schedule', methods=['POST'])
@token_required
def schedule_post_to_account(current_user, account_id):
    """Schedule content for a specific social media account"""
    try:
        # Verify account ownership
        account = SocialMediaAccount.query.filter_by(
            id=account_id,
            user_id=current_user.id
        ).first()
        
        if not account:
            return jsonify({'error': 'Social media account not found'}), 404
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('content'):
            return jsonify({'error': 'Content is required'}), 400
        
        if not data.get('scheduled_time'):
            return jsonify({'error': 'Scheduled time is required'}), 400
        
        content = data['content']
        content_type = data.get('content_type', 'text')
        media_path = data.get('media_path')
        hashtags = data.get('hashtags')
        
        # Parse scheduled time
        try:
            scheduled_time = datetime.fromisoformat(data['scheduled_time'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid scheduled time format'}), 400
        
        # Validate scheduled time is in the future
        if scheduled_time <= datetime.utcnow():
            return jsonify({'error': 'Scheduled time must be in the future'}), 400
        
        # Schedule content
        result = social_media_service.schedule_content(
            account_id=account_id,
            content=content,
            scheduled_time=scheduled_time,
            content_type=content_type,
            media_path=media_path,
            hashtags=hashtags
        )
        
        if result.get('success'):
            return jsonify({
                'message': 'Content scheduled successfully',
                'result': result
            }), 201
        else:
            return jsonify({
                'error': 'Scheduling failed',
                'details': result.get('error')
            }), 400
        
    except Exception as e:
        return jsonify({'error': 'Scheduling failed', 'details': str(e)}), 500

@social_accounts_bp.route('/scheduled-posts', methods=['GET'])
@token_required
def get_scheduled_posts(current_user):
    """Get all scheduled posts for current user"""
    try:
        platform = request.args.get('platform')
        
        scheduled_posts = social_media_service.get_scheduled_posts(
            user_id=current_user.id,
            platform=platform
        )
        
        return jsonify({
            'scheduled_posts': scheduled_posts,
            'count': len(scheduled_posts)
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch scheduled posts', 'details': str(e)}), 500

@social_accounts_bp.route('/scheduled-posts/<post_id>', methods=['DELETE'])
@token_required
def cancel_scheduled_post(current_user, post_id):
    """Cancel a scheduled post"""
    try:
        result = social_media_service.cancel_scheduled_post(
            post_id=post_id,
            user_id=current_user.id
        )
        
        if result.get('success'):
            return jsonify({'message': result['message']}), 200
        else:
            return jsonify({'error': result.get('error')}), 400
        
    except Exception as e:
        return jsonify({'error': 'Failed to cancel scheduled post', 'details': str(e)}), 500

@social_accounts_bp.route('/platforms', methods=['GET'])
def get_supported_platforms():
    """Get list of supported social media platforms"""
    platforms = {
        'instagram': {
            'name': 'Instagram',
            'supported_content_types': ['text', 'image', 'video', 'carousel'],
            'max_text_length': 2200,
            'max_hashtags': 30,
            'auth_method': 'oauth2',
            'requires_business_account': True
        },
        'linkedin': {
            'name': 'LinkedIn',
            'supported_content_types': ['text', 'image', 'video'],
            'max_text_length': 3000,
            'max_hashtags': 5,
            'auth_method': 'oauth2',
            'requires_business_account': False
        },
        'twitter': {
            'name': 'Twitter/X',
            'supported_content_types': ['text', 'image', 'video'],
            'max_text_length': 280,
            'max_hashtags': 5,
            'auth_method': 'oauth2',
            'requires_business_account': False
        },
        'facebook': {
            'name': 'Facebook',
            'supported_content_types': ['text', 'image', 'video'],
            'max_text_length': 63206,
            'max_hashtags': 10,
            'auth_method': 'oauth2',
            'requires_business_account': True
        },
        'tiktok': {
            'name': 'TikTok',
            'supported_content_types': ['video'],
            'max_text_length': 150,
            'max_hashtags': 10,
            'auth_method': 'oauth2',
            'requires_business_account': True
        }
    }
    
    return jsonify({'platforms': platforms}), 200

@social_accounts_bp.route('/social-accounts/<account_id>/test', methods=['POST'])
@token_required
def test_account_connection(current_user, account_id):
    """Test connection to a social media account"""
    try:
        account = SocialMediaAccount.query.filter_by(
            id=account_id,
            user_id=current_user.id
        ).first()
        
        if not account:
            return jsonify({'error': 'Social media account not found'}), 404
        
        # Test credentials
        is_valid = social_media_service.validate_account_credentials(
            platform=account.platform,
            credentials=account.credentials
        )
        
        if is_valid:
            # Update last tested time
            account.last_tested_at = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                'message': 'Account connection is valid',
                'platform': account.platform,
                'account_name': account.account_name,
                'tested_at': account.last_tested_at.isoformat()
            }), 200
        else:
            return jsonify({
                'error': 'Account connection is invalid',
                'platform': account.platform,
                'message': 'Please reconnect your account'
            }), 400
        
    except Exception as e:
        return jsonify({'error': 'Connection test failed', 'details': str(e)}), 500

