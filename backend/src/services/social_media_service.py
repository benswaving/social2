import requests
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from src.models.user import SocialMediaAccount, ScheduledPost, db

class SocialMediaPublisher:
    """Base class for social media publishing"""
    
    def __init__(self, platform: str):
        self.platform = platform
    
    def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate social media credentials"""
        raise NotImplementedError
    
    def publish_text(self, credentials: Dict[str, str], content: str, 
                    hashtags: str = None) -> Dict[str, Any]:
        """Publish text content"""
        raise NotImplementedError
    
    def publish_image(self, credentials: Dict[str, str], content: str, 
                     image_path: str, hashtags: str = None) -> Dict[str, Any]:
        """Publish image with text"""
        raise NotImplementedError
    
    def publish_video(self, credentials: Dict[str, str], content: str, 
                     video_path: str, hashtags: str = None) -> Dict[str, Any]:
        """Publish video with text"""
        raise NotImplementedError
    
    def schedule_post(self, credentials: Dict[str, str], content: str, 
                     scheduled_time: datetime, media_path: str = None) -> Dict[str, Any]:
        """Schedule a post for later"""
        raise NotImplementedError


class InstagramPublisher(SocialMediaPublisher):
    """Instagram publishing via Meta Graph API"""
    
    def __init__(self):
        super().__init__('instagram')
        self.base_url = 'https://graph.facebook.com/v18.0'
    
    def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate Instagram credentials"""
        try:
            access_token = credentials.get('access_token')
            instagram_account_id = credentials.get('instagram_account_id')
            
            if not access_token or not instagram_account_id:
                return False
            
            # Test API call to validate credentials
            url = f"{self.base_url}/{instagram_account_id}"
            params = {
                'fields': 'id,username',
                'access_token': access_token
            }
            
            response = requests.get(url, params=params)
            return response.status_code == 200
            
        except Exception as e:
            print(f"Instagram credential validation error: {e}")
            return False
    
    def publish_text(self, credentials: Dict[str, str], content: str, 
                    hashtags: str = None) -> Dict[str, Any]:
        """Publish text content to Instagram (as story or note)"""
        try:
            # Instagram requires media for feed posts, so text-only goes to stories
            access_token = credentials.get('access_token')
            instagram_account_id = credentials.get('instagram_account_id')
            
            full_content = f"{content}\n\n{hashtags}" if hashtags else content
            
            # For demo purposes, we'll simulate the API call
            return {
                'success': True,
                'platform': 'instagram',
                'post_id': f'ig_story_{datetime.utcnow().timestamp()}',
                'post_type': 'story',
                'content': full_content,
                'published_at': datetime.utcnow().isoformat(),
                'message': 'Text content published as Instagram story (simulated)'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'platform': 'instagram'
            }
    
    def publish_image(self, credentials: Dict[str, str], content: str, 
                     image_path: str, hashtags: str = None) -> Dict[str, Any]:
        """Publish image with caption to Instagram"""
        try:
            access_token = credentials.get('access_token')
            instagram_account_id = credentials.get('instagram_account_id')
            
            full_content = f"{content}\n\n{hashtags}" if hashtags else content
            
            # Step 1: Create media container (simulated)
            container_data = {
                'image_url': image_path,  # In real implementation, this would be a public URL
                'caption': full_content,
                'access_token': access_token
            }
            
            # Step 2: Publish media container (simulated)
            return {
                'success': True,
                'platform': 'instagram',
                'post_id': f'ig_post_{datetime.utcnow().timestamp()}',
                'post_type': 'image',
                'content': full_content,
                'media_path': image_path,
                'published_at': datetime.utcnow().isoformat(),
                'message': 'Image post published to Instagram (simulated)'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'platform': 'instagram'
            }


class LinkedInPublisher(SocialMediaPublisher):
    """LinkedIn publishing via LinkedIn API"""
    
    def __init__(self):
        super().__init__('linkedin')
        self.base_url = 'https://api.linkedin.com/v2'
    
    def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate LinkedIn credentials"""
        try:
            access_token = credentials.get('access_token')
            person_id = credentials.get('person_id')
            
            if not access_token:
                return False
            
            # Test API call to validate credentials
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(f"{self.base_url}/me", headers=headers)
            return response.status_code == 200
            
        except Exception as e:
            print(f"LinkedIn credential validation error: {e}")
            return False
    
    def publish_text(self, credentials: Dict[str, str], content: str, 
                    hashtags: str = None) -> Dict[str, Any]:
        """Publish text content to LinkedIn"""
        try:
            access_token = credentials.get('access_token')
            person_id = credentials.get('person_id', 'me')
            
            full_content = f"{content}\n\n{hashtags}" if hashtags else content
            
            # LinkedIn post data structure
            post_data = {
                'author': f'urn:li:person:{person_id}',
                'lifecycleState': 'PUBLISHED',
                'specificContent': {
                    'com.linkedin.ugc.ShareContent': {
                        'shareCommentary': {
                            'text': full_content
                        },
                        'shareMediaCategory': 'NONE'
                    }
                },
                'visibility': {
                    'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC'
                }
            }
            
            # For demo purposes, simulate the API call
            return {
                'success': True,
                'platform': 'linkedin',
                'post_id': f'li_post_{datetime.utcnow().timestamp()}',
                'post_type': 'text',
                'content': full_content,
                'published_at': datetime.utcnow().isoformat(),
                'message': 'Text post published to LinkedIn (simulated)'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'platform': 'linkedin'
            }


class TwitterPublisher(SocialMediaPublisher):
    """Twitter/X publishing via Twitter API v2"""
    
    def __init__(self):
        super().__init__('twitter')
        self.base_url = 'https://api.twitter.com/2'
    
    def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate Twitter credentials"""
        try:
            bearer_token = credentials.get('bearer_token')
            
            if not bearer_token:
                return False
            
            # Test API call to validate credentials
            headers = {
                'Authorization': f'Bearer {bearer_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(f"{self.base_url}/users/me", headers=headers)
            return response.status_code == 200
            
        except Exception as e:
            print(f"Twitter credential validation error: {e}")
            return False
    
    def publish_text(self, credentials: Dict[str, str], content: str, 
                    hashtags: str = None) -> Dict[str, Any]:
        """Publish text content to Twitter"""
        try:
            bearer_token = credentials.get('bearer_token')
            
            full_content = f"{content} {hashtags}" if hashtags else content
            
            # Ensure content fits Twitter's character limit
            if len(full_content) > 280:
                full_content = full_content[:277] + "..."
            
            tweet_data = {
                'text': full_content
            }
            
            # For demo purposes, simulate the API call
            return {
                'success': True,
                'platform': 'twitter',
                'post_id': f'tw_post_{datetime.utcnow().timestamp()}',
                'post_type': 'text',
                'content': full_content,
                'published_at': datetime.utcnow().isoformat(),
                'message': 'Tweet published to Twitter (simulated)'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'platform': 'twitter'
            }


class FacebookPublisher(SocialMediaPublisher):
    """Facebook publishing via Meta Graph API"""
    
    def __init__(self):
        super().__init__('facebook')
        self.base_url = 'https://graph.facebook.com/v18.0'
    
    def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate Facebook credentials"""
        try:
            access_token = credentials.get('access_token')
            page_id = credentials.get('page_id')
            
            if not access_token or not page_id:
                return False
            
            # Test API call to validate credentials
            url = f"{self.base_url}/{page_id}"
            params = {
                'fields': 'id,name',
                'access_token': access_token
            }
            
            response = requests.get(url, params=params)
            return response.status_code == 200
            
        except Exception as e:
            print(f"Facebook credential validation error: {e}")
            return False
    
    def publish_text(self, credentials: Dict[str, str], content: str, 
                    hashtags: str = None) -> Dict[str, Any]:
        """Publish text content to Facebook"""
        try:
            access_token = credentials.get('access_token')
            page_id = credentials.get('page_id')
            
            full_content = f"{content}\n\n{hashtags}" if hashtags else content
            
            post_data = {
                'message': full_content,
                'access_token': access_token
            }
            
            # For demo purposes, simulate the API call
            return {
                'success': True,
                'platform': 'facebook',
                'post_id': f'fb_post_{datetime.utcnow().timestamp()}',
                'post_type': 'text',
                'content': full_content,
                'published_at': datetime.utcnow().isoformat(),
                'message': 'Post published to Facebook (simulated)'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'platform': 'facebook'
            }


class TikTokPublisher(SocialMediaPublisher):
    """TikTok publishing via TikTok API"""
    
    def __init__(self):
        super().__init__('tiktok')
        self.base_url = 'https://open-api.tiktok.com'
    
    def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate TikTok credentials"""
        try:
            access_token = credentials.get('access_token')
            
            if not access_token:
                return False
            
            # TikTok API validation would go here
            # For demo purposes, return True
            return True
            
        except Exception as e:
            print(f"TikTok credential validation error: {e}")
            return False
    
    def publish_video(self, credentials: Dict[str, str], content: str, 
                     video_path: str, hashtags: str = None) -> Dict[str, Any]:
        """Publish video to TikTok"""
        try:
            access_token = credentials.get('access_token')
            
            full_content = f"{content} {hashtags}" if hashtags else content
            
            # TikTok video upload would go here
            # For demo purposes, simulate the API call
            return {
                'success': True,
                'platform': 'tiktok',
                'post_id': f'tt_post_{datetime.utcnow().timestamp()}',
                'post_type': 'video',
                'content': full_content,
                'media_path': video_path,
                'published_at': datetime.utcnow().isoformat(),
                'message': 'Video published to TikTok (simulated)'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'platform': 'tiktok'
            }


class SocialMediaService:
    """Main service for social media operations"""
    
    def __init__(self):
        self.publishers = {
            'instagram': InstagramPublisher(),
            'linkedin': LinkedInPublisher(),
            'twitter': TwitterPublisher(),
            'facebook': FacebookPublisher(),
            'tiktok': TikTokPublisher()
        }
    
    def get_publisher(self, platform: str) -> SocialMediaPublisher:
        """Get publisher for specific platform"""
        return self.publishers.get(platform)
    
    def validate_account_credentials(self, platform: str, credentials: Dict[str, str]) -> bool:
        """Validate credentials for a platform"""
        publisher = self.get_publisher(platform)
        if not publisher:
            return False
        
        return publisher.validate_credentials(credentials)
    
    def publish_content(self, account_id: str, content: str, content_type: str = 'text',
                       media_path: str = None, hashtags: str = None) -> Dict[str, Any]:
        """Publish content to a social media account"""
        try:
            # Get account from database
            account = SocialMediaAccount.query.get(account_id)
            if not account or not account.is_active:
                return {
                    'success': False,
                    'error': 'Account not found or inactive'
                }
            
            publisher = self.get_publisher(account.platform)
            if not publisher:
                return {
                    'success': False,
                    'error': f'Publisher not available for {account.platform}'
                }
            
            # Decrypt credentials (in real implementation)
            credentials = account.credentials
            
            # Publish based on content type
            if content_type == 'text':
                result = publisher.publish_text(credentials, content, hashtags)
            elif content_type == 'image' and media_path:
                result = publisher.publish_image(credentials, content, media_path, hashtags)
            elif content_type == 'video' and media_path:
                result = publisher.publish_video(credentials, content, media_path, hashtags)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported content type: {content_type}'
                }
            
            # Update account stats if successful
            if result.get('success'):
                account.posts_count += 1
                account.last_post_at = datetime.utcnow()
                db.session.commit()
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Publishing failed: {str(e)}'
            }
    
    def schedule_content(self, account_id: str, content: str, scheduled_time: datetime,
                        content_type: str = 'text', media_path: str = None, 
                        hashtags: str = None) -> Dict[str, Any]:
        """Schedule content for later publishing"""
        try:
            # Get account from database
            account = SocialMediaAccount.query.get(account_id)
            if not account or not account.is_active:
                return {
                    'success': False,
                    'error': 'Account not found or inactive'
                }
            
            # Create scheduled post
            scheduled_post = ScheduledPost(
                user_id=account.user_id,
                social_account_id=account_id,
                platform=account.platform,
                content_text=content,
                content_type=content_type,
                media_url=media_path,
                hashtags=hashtags,
                scheduled_time=scheduled_time,
                status='scheduled'
            )
            
            db.session.add(scheduled_post)
            db.session.commit()
            
            return {
                'success': True,
                'scheduled_post_id': scheduled_post.id,
                'platform': account.platform,
                'scheduled_time': scheduled_time.isoformat(),
                'message': 'Content scheduled successfully'
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': f'Scheduling failed: {str(e)}'
            }
    
    def get_scheduled_posts(self, user_id: str, platform: str = None) -> List[Dict[str, Any]]:
        """Get scheduled posts for a user"""
        try:
            query = ScheduledPost.query.filter_by(user_id=user_id)
            
            if platform:
                query = query.filter_by(platform=platform)
            
            scheduled_posts = query.filter_by(status='scheduled').all()
            
            return [
                {
                    'id': post.id,
                    'platform': post.platform,
                    'content': post.content_text,
                    'content_type': post.content_type,
                    'scheduled_time': post.scheduled_time.isoformat(),
                    'created_at': post.created_at.isoformat()
                }
                for post in scheduled_posts
            ]
            
        except Exception as e:
            return []
    
    def cancel_scheduled_post(self, post_id: str, user_id: str) -> Dict[str, Any]:
        """Cancel a scheduled post"""
        try:
            scheduled_post = ScheduledPost.query.filter_by(
                id=post_id, 
                user_id=user_id,
                status='scheduled'
            ).first()
            
            if not scheduled_post:
                return {
                    'success': False,
                    'error': 'Scheduled post not found'
                }
            
            scheduled_post.status = 'cancelled'
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Scheduled post cancelled'
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': f'Cancellation failed: {str(e)}'
            }


# Service instance
social_media_service = SocialMediaService()

