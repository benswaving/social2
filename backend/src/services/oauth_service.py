import os
import secrets
import hashlib
import base64
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode, parse_qs, urlparse
from cryptography.fernet import Fernet
from src.models.user import SocialMediaAccount, db

class OAuthService:
    """Service for handling OAuth2 flows with social media platforms"""
    
    def __init__(self):
        # Initialize encryption for storing tokens securely
        self.encryption_key = os.getenv('ENCRYPTION_KEY', Fernet.generate_key())
        self.cipher_suite = Fernet(self.encryption_key)
        
        # Platform configurations
        self.platforms = {
            'instagram': {
                'client_id': os.getenv('INSTAGRAM_CLIENT_ID'),
                'client_secret': os.getenv('INSTAGRAM_CLIENT_SECRET'),
                'authorization_url': 'https://api.instagram.com/oauth/authorize',
                'token_url': 'https://api.instagram.com/oauth/access_token',
                'scope': 'user_profile,user_media',
                'redirect_uri': os.getenv('INSTAGRAM_REDIRECT_URI', 'http://localhost:3000/auth/instagram/callback')
            },
            'facebook': {
                'client_id': os.getenv('FACEBOOK_CLIENT_ID'),
                'client_secret': os.getenv('FACEBOOK_CLIENT_SECRET'),
                'authorization_url': 'https://www.facebook.com/v18.0/dialog/oauth',
                'token_url': 'https://graph.facebook.com/v18.0/oauth/access_token',
                'scope': 'pages_manage_posts,pages_read_engagement,pages_show_list,instagram_basic,instagram_content_publish',
                'redirect_uri': os.getenv('FACEBOOK_REDIRECT_URI', 'http://localhost:3000/auth/facebook/callback')
            },
            'linkedin': {
                'client_id': os.getenv('LINKEDIN_CLIENT_ID'),
                'client_secret': os.getenv('LINKEDIN_CLIENT_SECRET'),
                'authorization_url': 'https://www.linkedin.com/oauth/v2/authorization',
                'token_url': 'https://www.linkedin.com/oauth/v2/accessToken',
                'scope': 'w_member_social,r_liteprofile,r_emailaddress',
                'redirect_uri': os.getenv('LINKEDIN_REDIRECT_URI', 'http://localhost:3000/auth/linkedin/callback')
            },
            'twitter': {
                'client_id': os.getenv('TWITTER_CLIENT_ID'),
                'client_secret': os.getenv('TWITTER_CLIENT_SECRET'),
                'authorization_url': 'https://twitter.com/i/oauth2/authorize',
                'token_url': 'https://api.twitter.com/2/oauth2/token',
                'scope': 'tweet.read tweet.write users.read offline.access',
                'redirect_uri': os.getenv('TWITTER_REDIRECT_URI', 'http://localhost:3000/auth/twitter/callback')
            },
            'tiktok': {
                'client_id': os.getenv('TIKTOK_CLIENT_ID'),
                'client_secret': os.getenv('TIKTOK_CLIENT_SECRET'),
                'authorization_url': 'https://www.tiktok.com/auth/authorize/',
                'token_url': 'https://open-api.tiktok.com/oauth/access_token/',
                'scope': 'user.info.basic,video.list,video.upload',
                'redirect_uri': os.getenv('TIKTOK_REDIRECT_URI', 'http://localhost:3000/auth/tiktok/callback')
            }
        }
    
    def encrypt_token(self, token: str) -> str:
        """Encrypt sensitive token data"""
        return self.cipher_suite.encrypt(token.encode()).decode()
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt sensitive token data"""
        return self.cipher_suite.decrypt(encrypted_token.encode()).decode()
    
    def generate_state(self, user_id: str, platform: str) -> str:
        """Generate secure state parameter for OAuth2 flow"""
        timestamp = str(int(datetime.utcnow().timestamp()))
        data = f"{user_id}:{platform}:{timestamp}:{secrets.token_urlsafe(16)}"
        return base64.urlsafe_b64encode(data.encode()).decode()
    
    def validate_state(self, state: str, user_id: str, platform: str) -> bool:
        """Validate state parameter to prevent CSRF attacks"""
        try:
            decoded = base64.urlsafe_b64decode(state.encode()).decode()
            parts = decoded.split(':')
            if len(parts) != 4:
                return False
            
            state_user_id, state_platform, timestamp, _ = parts
            
            # Check if state matches user and platform
            if state_user_id != user_id or state_platform != platform:
                return False
            
            # Check if state is not too old (10 minutes max)
            state_time = datetime.fromtimestamp(int(timestamp))
            if datetime.utcnow() - state_time > timedelta(minutes=10):
                return False
            
            return True
        except Exception:
            return False
    
    def get_authorization_url(self, platform: str, user_id: str) -> Tuple[str, str]:
        """Generate OAuth2 authorization URL for platform"""
        if platform not in self.platforms:
            raise ValueError(f"Unsupported platform: {platform}")
        
        config = self.platforms[platform]
        
        if not config['client_id']:
            raise ValueError(f"Missing client_id for {platform}")
        
        # Generate secure state parameter
        state = self.generate_state(user_id, platform)
        
        # Build authorization URL parameters
        params = {
            'client_id': config['client_id'],
            'redirect_uri': config['redirect_uri'],
            'scope': config['scope'],
            'response_type': 'code',
            'state': state
        }
        
        # Platform-specific parameters
        if platform == 'twitter':
            # Twitter requires PKCE
            code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('=')
            code_challenge = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            ).decode().rstrip('=')
            
            params.update({
                'code_challenge': code_challenge,
                'code_challenge_method': 'S256'
            })
            
            # Store code_verifier temporarily (in production, use Redis)
            # For now, we'll include it in the state (not recommended for production)
            
        elif platform == 'linkedin':
            params['response_type'] = 'code'
            
        elif platform == 'tiktok':
            params['response_type'] = 'code'
        
        authorization_url = f"{config['authorization_url']}?{urlencode(params)}"
        
        return authorization_url, state
    
    def exchange_code_for_token(self, platform: str, code: str, state: str, user_id: str) -> Dict:
        """Exchange authorization code for access token"""
        if platform not in self.platforms:
            raise ValueError(f"Unsupported platform: {platform}")
        
        # Validate state parameter
        if not self.validate_state(state, user_id, platform):
            raise ValueError("Invalid or expired state parameter")
        
        config = self.platforms[platform]
        
        # Prepare token exchange request
        data = {
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'code': code,
            'redirect_uri': config['redirect_uri'],
            'grant_type': 'authorization_code'
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        # Platform-specific adjustments
        if platform == 'instagram':
            # Instagram uses form data
            response = requests.post(config['token_url'], data=data, headers=headers)
        elif platform == 'facebook':
            response = requests.post(config['token_url'], data=data, headers=headers)
        elif platform == 'linkedin':
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            response = requests.post(config['token_url'], data=data, headers=headers)
        elif platform == 'twitter':
            # Twitter requires basic auth
            import base64
            auth_string = base64.b64encode(f"{config['client_id']}:{config['client_secret']}".encode()).decode()
            headers['Authorization'] = f'Basic {auth_string}'
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            response = requests.post(config['token_url'], data=data, headers=headers)
        elif platform == 'tiktok':
            response = requests.post(config['token_url'], data=data, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.text}")
        
        token_data = response.json()
        
        # Standardize token response format
        standardized_token = {
            'access_token': token_data.get('access_token'),
            'refresh_token': token_data.get('refresh_token'),
            'expires_in': token_data.get('expires_in'),
            'token_type': token_data.get('token_type', 'Bearer'),
            'scope': token_data.get('scope', config['scope']),
            'platform': platform,
            'raw_response': token_data
        }
        
        return standardized_token
    
    def refresh_access_token(self, platform: str, refresh_token: str) -> Dict:
        """Refresh expired access token using refresh token"""
        if platform not in self.platforms:
            raise ValueError(f"Unsupported platform: {platform}")
        
        config = self.platforms[platform]
        
        data = {
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        response = requests.post(config['token_url'], data=data, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")
        
        return response.json()
    
    def get_user_profile(self, platform: str, access_token: str) -> Dict:
        """Get user profile information from platform"""
        profile_endpoints = {
            'instagram': 'https://graph.instagram.com/me?fields=id,username,account_type',
            'facebook': 'https://graph.facebook.com/me?fields=id,name,email',
            'linkedin': 'https://api.linkedin.com/v2/me',
            'twitter': 'https://api.twitter.com/2/users/me',
            'tiktok': 'https://open-api.tiktok.com/user/info/'
        }
        
        if platform not in profile_endpoints:
            raise ValueError(f"Profile endpoint not configured for {platform}")
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        response = requests.get(profile_endpoints[platform], headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Failed to get user profile: {response.text}")
        
        return response.json()
    
    def store_account_credentials(self, user_id: str, platform: str, token_data: Dict, profile_data: Dict) -> SocialMediaAccount:
        """Store encrypted account credentials in database"""
        try:
            # Check if account already exists
            existing_account = SocialMediaAccount.query.filter_by(
                user_id=user_id,
                platform=platform,
                account_username=profile_data.get('username', profile_data.get('name', 'unknown'))
            ).first()
            
            if existing_account:
                # Update existing account
                account = existing_account
            else:
                # Create new account
                account = SocialMediaAccount(
                    user_id=user_id,
                    platform=platform
                )
                db.session.add(account)
            
            # Encrypt and store credentials
            encrypted_credentials = {
                'access_token': self.encrypt_token(token_data['access_token']),
                'refresh_token': self.encrypt_token(token_data.get('refresh_token', '')) if token_data.get('refresh_token') else None,
                'token_type': token_data.get('token_type', 'Bearer'),
                'scope': token_data.get('scope', ''),
                'expires_in': token_data.get('expires_in'),
                'platform_user_id': profile_data.get('id'),
                'raw_token_data': self.encrypt_token(json.dumps(token_data)),
                'raw_profile_data': self.encrypt_token(json.dumps(profile_data))
            }
            
            # Update account information
            account.account_name = profile_data.get('name', profile_data.get('username', 'Unknown'))
            account.account_username = profile_data.get('username', profile_data.get('name', 'unknown'))
            account.credentials = encrypted_credentials
            account.is_active = True
            account.connected_at = datetime.utcnow()
            
            # Set expiration time if provided
            if token_data.get('expires_in'):
                account.expires_at = datetime.utcnow() + timedelta(seconds=int(token_data['expires_in']))
            
            db.session.commit()
            
            return account
            
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to store account credentials: {str(e)}")
    
    def get_decrypted_credentials(self, account: SocialMediaAccount) -> Dict:
        """Get decrypted credentials for an account"""
        if not account.credentials:
            raise ValueError("No credentials found for account")
        
        decrypted_creds = {}
        
        for key, value in account.credentials.items():
            if key in ['access_token', 'refresh_token', 'raw_token_data', 'raw_profile_data'] and value:
                try:
                    decrypted_creds[key] = self.decrypt_token(value)
                except Exception:
                    # Handle decryption errors gracefully
                    decrypted_creds[key] = None
            else:
                decrypted_creds[key] = value
        
        return decrypted_creds
    
    def validate_token(self, platform: str, access_token: str) -> bool:
        """Validate if access token is still valid"""
        try:
            profile = self.get_user_profile(platform, access_token)
            return profile is not None
        except Exception:
            return False
    
    def revoke_token(self, platform: str, access_token: str) -> bool:
        """Revoke access token (logout from platform)"""
        revoke_endpoints = {
            'facebook': 'https://graph.facebook.com/me/permissions',
            'linkedin': 'https://www.linkedin.com/oauth/v2/revoke',
            'twitter': 'https://api.twitter.com/2/oauth2/revoke',
            'google': 'https://oauth2.googleapis.com/revoke'
        }
        
        if platform not in revoke_endpoints:
            # Platform doesn't support token revocation
            return True
        
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            
            if platform == 'facebook':
                response = requests.delete(revoke_endpoints[platform], headers=headers)
            else:
                data = {'token': access_token}
                response = requests.post(revoke_endpoints[platform], data=data, headers=headers)
            
            return response.status_code in [200, 204]
        except Exception:
            return False


# Service instance
oauth_service = OAuthService()

