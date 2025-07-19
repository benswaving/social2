from flask import Blueprint, jsonify, request, redirect, url_for
from src.routes.auth import token_required
from src.services.oauth_service import oauth_service
from src.models.user import SocialMediaAccount, db
import logging

oauth_bp = Blueprint('oauth', __name__)

@oauth_bp.route('/oauth/authorize/<platform>', methods=['GET'])
@token_required
def initiate_oauth(current_user, platform):
    """Initiate OAuth2 flow for a social media platform"""
    try:
        # Validate platform
        supported_platforms = ['instagram', 'facebook', 'linkedin', 'twitter', 'tiktok']
        if platform not in supported_platforms:
            return jsonify({'error': f'Platform {platform} not supported'}), 400
        
        # Generate authorization URL
        authorization_url, state = oauth_service.get_authorization_url(platform, current_user.id)
        
        # Store state temporarily (in production, use Redis with expiration)
        # For now, we'll return it to the client to include in callback
        
        return jsonify({
            'authorization_url': authorization_url,
            'state': state,
            'platform': platform,
            'message': f'Redirect user to authorization URL for {platform}'
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"OAuth initiation failed for {platform}: {str(e)}")
        return jsonify({'error': 'Failed to initiate OAuth flow'}), 500

@oauth_bp.route('/oauth/callback/<platform>', methods=['POST'])
@token_required
def oauth_callback(current_user, platform):
    """Handle OAuth2 callback from social media platform"""
    try:
        data = request.get_json()
        
        # Validate required parameters
        if not data.get('code'):
            return jsonify({'error': 'Authorization code is required'}), 400
        
        if not data.get('state'):
            return jsonify({'error': 'State parameter is required'}), 400
        
        code = data['code']
        state = data['state']
        
        # Exchange code for access token
        token_data = oauth_service.exchange_code_for_token(platform, code, state, current_user.id)
        
        # Get user profile from platform
        profile_data = oauth_service.get_user_profile(platform, token_data['access_token'])
        
        # Store account credentials
        account = oauth_service.store_account_credentials(
            user_id=current_user.id,
            platform=platform,
            token_data=token_data,
            profile_data=profile_data
        )
        
        return jsonify({
            'message': f'{platform.title()} account connected successfully',
            'account': {
                'id': account.id,
                'platform': account.platform,
                'account_name': account.account_name,
                'account_username': account.account_username,
                'connected_at': account.connected_at.isoformat(),
                'expires_at': account.expires_at.isoformat() if account.expires_at else None
            }
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"OAuth callback failed for {platform}: {str(e)}")
        return jsonify({'error': 'Failed to complete OAuth flow'}), 500

@oauth_bp.route('/oauth/refresh/<account_id>', methods=['POST'])
@token_required
def refresh_token(current_user, account_id):
    """Refresh expired access token for a social media account"""
    try:
        # Get account
        account = SocialMediaAccount.query.filter_by(
            id=account_id,
            user_id=current_user.id
        ).first()
        
        if not account:
            return jsonify({'error': 'Social media account not found'}), 404
        
        # Get decrypted credentials
        credentials = oauth_service.get_decrypted_credentials(account)
        
        if not credentials.get('refresh_token'):
            return jsonify({'error': 'No refresh token available'}), 400
        
        # Refresh the token
        new_token_data = oauth_service.refresh_access_token(
            platform=account.platform,
            refresh_token=credentials['refresh_token']
        )
        
        # Update stored credentials
        encrypted_credentials = account.credentials.copy()
        encrypted_credentials['access_token'] = oauth_service.encrypt_token(new_token_data['access_token'])
        
        if new_token_data.get('refresh_token'):
            encrypted_credentials['refresh_token'] = oauth_service.encrypt_token(new_token_data['refresh_token'])
        
        if new_token_data.get('expires_in'):
            from datetime import datetime, timedelta
            account.expires_at = datetime.utcnow() + timedelta(seconds=int(new_token_data['expires_in']))
        
        account.credentials = encrypted_credentials
        db.session.commit()
        
        return jsonify({
            'message': 'Token refreshed successfully',
            'expires_at': account.expires_at.isoformat() if account.expires_at else None
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Token refresh failed for account {account_id}: {str(e)}")
        return jsonify({'error': 'Failed to refresh token'}), 500

@oauth_bp.route('/oauth/validate/<account_id>', methods=['POST'])
@token_required
def validate_token(current_user, account_id):
    """Validate if access token is still valid"""
    try:
        # Get account
        account = SocialMediaAccount.query.filter_by(
            id=account_id,
            user_id=current_user.id
        ).first()
        
        if not account:
            return jsonify({'error': 'Social media account not found'}), 404
        
        # Get decrypted credentials
        credentials = oauth_service.get_decrypted_credentials(account)
        
        if not credentials.get('access_token'):
            return jsonify({'error': 'No access token found'}), 400
        
        # Validate token
        is_valid = oauth_service.validate_token(account.platform, credentials['access_token'])
        
        if is_valid:
            # Update last tested time
            from datetime import datetime
            account.last_tested_at = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                'valid': True,
                'message': 'Token is valid',
                'tested_at': account.last_tested_at.isoformat()
            }), 200
        else:
            return jsonify({
                'valid': False,
                'message': 'Token is invalid or expired',
                'suggestion': 'Please refresh token or reconnect account'
            }), 200
        
    except Exception as e:
        logging.error(f"Token validation failed for account {account_id}: {str(e)}")
        return jsonify({'error': 'Failed to validate token'}), 500

@oauth_bp.route('/oauth/revoke/<account_id>', methods=['POST'])
@token_required
def revoke_token(current_user, account_id):
    """Revoke access token and disconnect account"""
    try:
        # Get account
        account = SocialMediaAccount.query.filter_by(
            id=account_id,
            user_id=current_user.id
        ).first()
        
        if not account:
            return jsonify({'error': 'Social media account not found'}), 404
        
        # Get decrypted credentials
        credentials = oauth_service.get_decrypted_credentials(account)
        
        if credentials.get('access_token'):
            # Attempt to revoke token on platform
            revoked = oauth_service.revoke_token(account.platform, credentials['access_token'])
            
            if not revoked:
                logging.warning(f"Failed to revoke token on {account.platform} for account {account_id}")
        
        # Deactivate account locally
        account.is_active = False
        account.credentials = {}  # Clear stored credentials
        db.session.commit()
        
        return jsonify({
            'message': f'{account.platform.title()} account disconnected successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Token revocation failed for account {account_id}: {str(e)}")
        return jsonify({'error': 'Failed to revoke token'}), 500

@oauth_bp.route('/oauth/status', methods=['GET'])
@token_required
def oauth_status(current_user):
    """Get OAuth status for all connected accounts"""
    try:
        accounts = SocialMediaAccount.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()
        
        status_list = []
        
        for account in accounts:
            try:
                credentials = oauth_service.get_decrypted_credentials(account)
                
                # Check if token is expired
                from datetime import datetime
                is_expired = False
                if account.expires_at:
                    is_expired = datetime.utcnow() > account.expires_at
                
                # Quick validation (optional, can be slow)
                is_valid = None
                if not is_expired and credentials.get('access_token'):
                    # Only validate if requested explicitly
                    validate_param = request.args.get('validate', 'false').lower()
                    if validate_param == 'true':
                        is_valid = oauth_service.validate_token(account.platform, credentials['access_token'])
                
                status_list.append({
                    'account_id': account.id,
                    'platform': account.platform,
                    'account_name': account.account_name,
                    'account_username': account.account_username,
                    'connected_at': account.connected_at.isoformat(),
                    'expires_at': account.expires_at.isoformat() if account.expires_at else None,
                    'is_expired': is_expired,
                    'is_valid': is_valid,
                    'has_refresh_token': bool(credentials.get('refresh_token')),
                    'last_tested_at': account.last_tested_at.isoformat() if account.last_tested_at else None
                })
                
            except Exception as e:
                logging.error(f"Failed to get status for account {account.id}: {str(e)}")
                status_list.append({
                    'account_id': account.id,
                    'platform': account.platform,
                    'account_name': account.account_name,
                    'error': 'Failed to retrieve status'
                })
        
        return jsonify({
            'accounts': status_list,
            'total_accounts': len(status_list)
        }), 200
        
    except Exception as e:
        logging.error(f"Failed to get OAuth status: {str(e)}")
        return jsonify({'error': 'Failed to retrieve OAuth status'}), 500

@oauth_bp.route('/oauth/platforms', methods=['GET'])
def get_oauth_platforms():
    """Get list of supported OAuth platforms with configuration status"""
    platforms_status = {}
    
    for platform, config in oauth_service.platforms.items():
        platforms_status[platform] = {
            'name': platform.title(),
            'configured': bool(config.get('client_id') and config.get('client_secret')),
            'scopes': config.get('scope', '').split(',') if config.get('scope') else [],
            'redirect_uri': config.get('redirect_uri'),
            'supports_refresh': platform in ['twitter', 'linkedin', 'facebook']  # Platforms that support refresh tokens
        }
    
    return jsonify({
        'platforms': platforms_status,
        'total_platforms': len(platforms_status)
    }), 200

