import os
import requests
import json
import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from PIL import Image
import io
import base64
from openai import OpenAI
from src.models.user import MediaFile, db

class MediaGenerationService:
    """Service for generating images and videos using AI"""
    
    def __init__(self):
        self.openai_client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')
        )
        
        # Media storage configuration
        self.storage_base_path = os.getenv('MEDIA_STORAGE_PATH', '/home/ubuntu/media_storage')
        self.ensure_storage_directory()
        
        # Platform-specific image specifications
        self.platform_specs = {
            'instagram': {
                'post': {'width': 1080, 'height': 1080, 'aspect_ratio': '1:1'},
                'story': {'width': 1080, 'height': 1920, 'aspect_ratio': '9:16'},
                'reel': {'width': 1080, 'height': 1920, 'aspect_ratio': '9:16'}
            },
            'facebook': {
                'post': {'width': 1200, 'height': 630, 'aspect_ratio': '1.91:1'},
                'cover': {'width': 820, 'height': 312, 'aspect_ratio': '2.63:1'},
                'story': {'width': 1080, 'height': 1920, 'aspect_ratio': '9:16'}
            },
            'linkedin': {
                'post': {'width': 1200, 'height': 627, 'aspect_ratio': '1.91:1'},
                'article': {'width': 1200, 'height': 627, 'aspect_ratio': '1.91:1'},
                'company_cover': {'width': 1536, 'height': 768, 'aspect_ratio': '2:1'}
            },
            'twitter': {
                'post': {'width': 1200, 'height': 675, 'aspect_ratio': '16:9'},
                'header': {'width': 1500, 'height': 500, 'aspect_ratio': '3:1'},
                'card': {'width': 1200, 'height': 628, 'aspect_ratio': '1.91:1'}
            },
            'tiktok': {
                'video': {'width': 1080, 'height': 1920, 'aspect_ratio': '9:16'},
                'thumbnail': {'width': 1080, 'height': 1920, 'aspect_ratio': '9:16'}
            }
        }
    
    def ensure_storage_directory(self):
        """Ensure media storage directory exists"""
        os.makedirs(self.storage_base_path, exist_ok=True)
        os.makedirs(os.path.join(self.storage_base_path, 'images'), exist_ok=True)
        os.makedirs(os.path.join(self.storage_base_path, 'videos'), exist_ok=True)
        os.makedirs(os.path.join(self.storage_base_path, 'temp'), exist_ok=True)
    
    def generate_image_prompt(self, content_topic: str, platform: str, tone: str, content_type: str = 'post') -> str:
        """Generate optimized DALL-E prompt based on content and platform"""
        
        # Get platform specifications
        platform_spec = self.platform_specs.get(platform, {}).get(content_type, {})
        aspect_ratio = platform_spec.get('aspect_ratio', '1:1')
        
        # Platform-specific style guidelines
        platform_styles = {
            'instagram': 'vibrant, aesthetic, Instagram-worthy, high-quality photography style, trendy, visually appealing',
            'facebook': 'engaging, community-focused, warm and inviting, professional yet approachable',
            'linkedin': 'professional, clean, business-appropriate, sophisticated, corporate-friendly',
            'twitter': 'eye-catching, concise visual message, modern, shareable, attention-grabbing',
            'tiktok': 'dynamic, youthful, trendy, colorful, engaging, Gen-Z aesthetic'
        }
        
        # Tone-specific adjustments
        tone_styles = {
            'professional': 'clean, minimalist, sophisticated, high-end',
            'casual': 'relaxed, friendly, approachable, natural',
            'playful': 'colorful, fun, energetic, whimsical',
            'elegant': 'refined, luxurious, tasteful, premium',
            'modern': 'contemporary, sleek, cutting-edge, innovative',
            'vintage': 'retro, nostalgic, classic, timeless',
            'bold': 'striking, dramatic, high-contrast, powerful'
        }
        
        base_prompt = f"""Create a {aspect_ratio} aspect ratio image for {platform} about: {content_topic}
        
Style requirements:
- {platform_styles.get(platform, 'professional and engaging')}
- {tone_styles.get(tone.lower(), tone)} aesthetic
- High resolution, professional quality
- Optimized for social media engagement
- No text overlays (text will be added separately)
- Focus on visual storytelling
        
Technical specifications:
- Aspect ratio: {aspect_ratio}
- High quality, sharp details
- Good contrast and color balance
- Social media optimized composition"""
        
        return base_prompt.strip()
    
    def generate_image_with_dalle(self, prompt: str, platform: str, content_type: str = 'post', user_id: str = None) -> Dict:
        """Generate image using DALL-E 3"""
        try:
            # Get platform specifications for sizing
            platform_spec = self.platform_specs.get(platform, {}).get(content_type, {})
            
            # Determine size based on aspect ratio
            aspect_ratio = platform_spec.get('aspect_ratio', '1:1')
            if aspect_ratio in ['9:16', '16:9']:
                size = "1024x1792" if aspect_ratio == '9:16' else "1792x1024"
            else:
                size = "1024x1024"  # Square format
            
            # Generate image with DALL-E 3
            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality="hd",
                style="vivid",
                n=1
            )
            
            # Download and save the generated image
            image_url = response.data[0].url
            image_response = requests.get(image_url)
            
            if image_response.status_code != 200:
                raise Exception("Failed to download generated image")
            
            # Generate unique filename
            file_id = str(uuid.uuid4())
            filename = f"dalle3_{file_id}.png"
            file_path = os.path.join(self.storage_base_path, 'images', filename)
            
            # Save image
            with open(file_path, 'wb') as f:
                f.write(image_response.content)
            
            # Get image dimensions
            with Image.open(file_path) as img:
                width, height = img.size
            
            # Store in database if user_id provided
            media_file = None
            if user_id:
                media_file = MediaFile(
                    user_id=user_id,
                    filename=filename,
                    original_filename=f"generated_{content_type}_{platform}.png",
                    file_type='image',
                    file_size=len(image_response.content),
                    storage_path=file_path,
                    storage_provider='local',
                    mime_type='image/png',
                    dimensions={'width': width, 'height': height},
                    file_metadata={
                        'generated_by': 'dall-e-3',
                        'prompt': prompt,
                        'platform': platform,
                        'content_type': content_type,
                        'generation_params': {
                            'model': 'dall-e-3',
                            'size': size,
                            'quality': 'hd',
                            'style': 'vivid'
                        }
                    }
                )
                db.session.add(media_file)
                db.session.commit()
            
            return {
                'success': True,
                'file_id': media_file.id if media_file else file_id,
                'filename': filename,
                'file_path': file_path,
                'url': f"/api/media/{media_file.id if media_file else file_id}",
                'dimensions': {'width': width, 'height': height},
                'file_size': len(image_response.content),
                'prompt_used': prompt,
                'platform': platform,
                'content_type': content_type
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to generate image with DALL-E 3'
            }
    
    def generate_video_concept(self, content_topic: str, platform: str, tone: str, duration: int = 15) -> Dict:
        """Generate video concept and script for social media"""
        try:
            # Platform-specific video guidelines
            platform_guidelines = {
                'tiktok': f'Create a {duration}-second TikTok video concept that is engaging, trendy, and follows current TikTok formats. Focus on quick cuts, trending audio, and viral potential.',
                'instagram': f'Create a {duration}-second Instagram Reel concept that is visually appealing, uses trending music, and encourages engagement.',
                'facebook': f'Create a {duration}-second Facebook video concept that builds community, tells a story, and encourages sharing.',
                'linkedin': f'Create a {duration}-second LinkedIn video concept that is professional, educational, and provides business value.',
                'twitter': f'Create a {duration}-second Twitter video concept that is concise, newsworthy, and encourages retweets.'
            }
            
            prompt = f"""Create a detailed video concept for {platform} about: {content_topic}
            
Platform Guidelines: {platform_guidelines.get(platform, 'Create an engaging social media video concept')}
Tone: {tone}
Duration: {duration} seconds

Please provide:
1. Video Concept (2-3 sentences describing the main idea)
2. Scene Breakdown (shot-by-shot description)
3. Visual Style (color palette, mood, aesthetic)
4. Text Overlays (if any)
5. Call-to-Action
6. Hashtag Suggestions
7. Music/Audio Recommendations

Format the response as a structured JSON object."""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a social media video production expert. Create detailed, actionable video concepts that are optimized for engagement on each platform."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=1500
            )
            
            # Parse the response
            video_concept = response.choices[0].message.content
            
            # Try to parse as JSON, fallback to text if needed
            try:
                concept_data = json.loads(video_concept)
            except json.JSONDecodeError:
                concept_data = {
                    'concept': video_concept,
                    'platform': platform,
                    'duration': duration,
                    'tone': tone
                }
            
            return {
                'success': True,
                'video_concept': concept_data,
                'platform': platform,
                'duration': duration,
                'content_topic': content_topic,
                'tone': tone
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to generate video concept'
            }
    
    def create_video_thumbnail(self, video_concept: Dict, user_id: str = None) -> Dict:
        """Create a thumbnail image for the video concept"""
        try:
            concept_text = video_concept.get('concept', '')
            platform = video_concept.get('platform', 'instagram')
            
            # Create thumbnail prompt
            thumbnail_prompt = f"""Create a compelling video thumbnail for {platform} based on this video concept: {concept_text}
            
Requirements:
- Eye-catching and click-worthy
- Represents the video content accurately  
- Optimized for {platform} thumbnail specifications
- High contrast and readable even at small sizes
- No text overlays (will be added separately)
- Professional quality and engaging composition"""
            
            return self.generate_image_with_dalle(
                prompt=thumbnail_prompt,
                platform=platform,
                content_type='thumbnail',
                user_id=user_id
            )
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to create video thumbnail'
            }
    
    def optimize_image_for_platform(self, image_path: str, platform: str, content_type: str = 'post') -> Dict:
        """Optimize existing image for specific platform requirements"""
        try:
            # Get platform specifications
            platform_spec = self.platform_specs.get(platform, {}).get(content_type, {})
            target_width = platform_spec.get('width', 1080)
            target_height = platform_spec.get('height', 1080)
            
            # Open and process image
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Calculate optimal crop/resize
                img_ratio = img.width / img.height
                target_ratio = target_width / target_height
                
                if img_ratio > target_ratio:
                    # Image is wider, crop width
                    new_height = img.height
                    new_width = int(new_height * target_ratio)
                    left = (img.width - new_width) // 2
                    img = img.crop((left, 0, left + new_width, new_height))
                elif img_ratio < target_ratio:
                    # Image is taller, crop height
                    new_width = img.width
                    new_height = int(new_width / target_ratio)
                    top = (img.height - new_height) // 2
                    img = img.crop((0, top, new_width, top + new_height))
                
                # Resize to target dimensions
                img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                
                # Generate optimized filename
                file_id = str(uuid.uuid4())
                optimized_filename = f"optimized_{platform}_{content_type}_{file_id}.jpg"
                optimized_path = os.path.join(self.storage_base_path, 'images', optimized_filename)
                
                # Save optimized image
                img.save(optimized_path, 'JPEG', quality=95, optimize=True)
                
                # Get file size
                file_size = os.path.getsize(optimized_path)
                
                return {
                    'success': True,
                    'optimized_path': optimized_path,
                    'filename': optimized_filename,
                    'dimensions': {'width': target_width, 'height': target_height},
                    'file_size': file_size,
                    'platform': platform,
                    'content_type': content_type
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to optimize image for platform'
            }
    
    def get_media_file(self, file_id: str) -> Optional[MediaFile]:
        """Get media file by ID"""
        return MediaFile.query.filter_by(id=file_id).first()
    
    def delete_media_file(self, file_id: str, user_id: str) -> Dict:
        """Delete media file"""
        try:
            media_file = MediaFile.query.filter_by(id=file_id, user_id=user_id).first()
            
            if not media_file:
                return {
                    'success': False,
                    'error': 'Media file not found'
                }
            
            # Delete physical file
            if os.path.exists(media_file.storage_path):
                os.remove(media_file.storage_path)
            
            # Delete database record
            db.session.delete(media_file)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Media file deleted successfully'
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to delete media file'
            }
    
    def list_user_media(self, user_id: str, file_type: str = None, limit: int = 50, offset: int = 0) -> Dict:
        """List user's media files"""
        try:
            query = MediaFile.query.filter_by(user_id=user_id)
            
            if file_type:
                query = query.filter_by(file_type=file_type)
            
            total_count = query.count()
            media_files = query.order_by(MediaFile.created_at.desc()).offset(offset).limit(limit).all()
            
            files_data = []
            for media_file in media_files:
                files_data.append({
                    'id': media_file.id,
                    'filename': media_file.filename,
                    'original_filename': media_file.original_filename,
                    'file_type': media_file.file_type,
                    'file_size': media_file.file_size,
                    'mime_type': media_file.mime_type,
                    'dimensions': media_file.dimensions,
                    'duration': media_file.duration,
                    'url': f"/api/media/{media_file.id}",
                    'created_at': media_file.created_at.isoformat(),
                    'metadata': media_file.file_metadata
                })
            
            return {
                'success': True,
                'files': files_data,
                'total_count': total_count,
                'limit': limit,
                'offset': offset
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to list media files'
            }


# Service instance
media_generation_service = MediaGenerationService()

