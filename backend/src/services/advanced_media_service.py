import os
import requests
import json
import uuid
import base64
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from PIL import Image
import io
from openai import OpenAI
from src.models.user import MediaFile, db
from src.services.database_service import database_service

class AdvancedMediaService:
    """Advanced media generation service with multiple AI providers"""
    
    def __init__(self):
        # API clients and configurations
        self.openai_client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')
        )
        
        # Provider configurations
        self.providers = {
            'openai': {
                'name': 'OpenAI DALL-E 3',
                'capabilities': ['image'],
                'api_key': os.getenv('OPENAI_API_KEY'),
                'base_url': 'https://api.openai.com/v1'
            },
            'stability': {
                'name': 'Stability AI',
                'capabilities': ['image', 'video'],
                'api_key': os.getenv('STABILITY_API_KEY'),
                'base_url': 'https://api.stability.ai'
            },
            'runway': {
                'name': 'Runway ML',
                'capabilities': ['video', 'image'],
                'api_key': os.getenv('RUNWAY_API_KEY'),
                'base_url': 'https://api.runwayml.com'
            },
            'google_veo': {
                'name': 'Google Veo 3',
                'capabilities': ['video'],
                'api_key': os.getenv('GOOGLE_API_KEY'),
                'base_url': 'https://generativelanguage.googleapis.com'
            },
            'midjourney': {
                'name': 'Midjourney',
                'capabilities': ['image'],
                'api_key': os.getenv('MIDJOURNEY_API_KEY'),
                'base_url': 'https://api.midjourney.com'
            },
            'leonardo': {
                'name': 'Leonardo AI',
                'capabilities': ['image'],
                'api_key': os.getenv('LEONARDO_API_KEY'),
                'base_url': 'https://cloud.leonardo.ai/api'
            }
        }
        
        # Media storage
        self.storage_base_path = os.getenv('MEDIA_STORAGE_PATH', '/home/ubuntu/media_storage')
        self.ensure_storage_directory()
        
        # Quality and style presets
        self.quality_presets = {
            'draft': {'quality': 'standard', 'steps': 20, 'guidance': 7.5},
            'standard': {'quality': 'hd', 'steps': 30, 'guidance': 10},
            'premium': {'quality': 'ultra', 'steps': 50, 'guidance': 12},
            'professional': {'quality': 'ultra', 'steps': 75, 'guidance': 15}
        }
        
        # Style templates for different providers
        self.style_templates = {
            'photorealistic': {
                'openai': 'photorealistic, high resolution, professional photography',
                'stability': 'photorealistic, ultra detailed, 8k resolution, professional lighting',
                'midjourney': 'photorealistic --style raw --quality 2',
                'leonardo': 'photorealistic, hyperrealistic, ultra detailed'
            },
            'artistic': {
                'openai': 'artistic, creative, stylized, vibrant colors',
                'stability': 'artistic style, creative composition, vibrant palette',
                'midjourney': 'artistic --stylize 750',
                'leonardo': 'artistic style, creative interpretation'
            },
            'minimalist': {
                'openai': 'minimalist, clean, simple, modern design',
                'stability': 'minimalist design, clean composition, simple',
                'midjourney': 'minimalist --style raw',
                'leonardo': 'minimalist, clean design, simple composition'
            },
            'cinematic': {
                'openai': 'cinematic, dramatic lighting, movie-like quality',
                'stability': 'cinematic lighting, dramatic composition, film quality',
                'midjourney': 'cinematic --ar 16:9',
                'leonardo': 'cinematic style, dramatic lighting'
            }
        }
    
    def ensure_storage_directory(self):
        """Ensure media storage directories exist"""
        directories = ['images', 'videos', 'temp', 'stability', 'runway', 'veo', 'midjourney', 'leonardo']
        for directory in directories:
            os.makedirs(os.path.join(self.storage_base_path, directory), exist_ok=True)
    
    def get_available_providers(self, media_type: str = None) -> List[Dict[str, Any]]:
        """Get list of available providers"""
        available = []
        
        for provider_id, config in self.providers.items():
            if config['api_key']:  # Only include configured providers
                if not media_type or media_type in config['capabilities']:
                    available.append({
                        'id': provider_id,
                        'name': config['name'],
                        'capabilities': config['capabilities'],
                        'status': 'available'
                    })
        
        return available
    
    def generate_with_stability_ai(self, prompt: str, style: str = 'photorealistic', 
                                 quality: str = 'standard', aspect_ratio: str = '1:1',
                                 user_id: str = None) -> Dict[str, Any]:
        """Generate image using Stability AI"""
        try:
            api_key = self.providers['stability']['api_key']
            if not api_key:
                return {'success': False, 'error': 'Stability AI API key not configured'}
            
            # Prepare style-enhanced prompt
            style_prompt = self.style_templates.get(style, {}).get('stability', '')
            enhanced_prompt = f"{prompt}, {style_prompt}" if style_prompt else prompt
            
            # Map aspect ratio to dimensions
            dimension_map = {
                '1:1': {'width': 1024, 'height': 1024},
                '16:9': {'width': 1344, 'height': 768},
                '9:16': {'width': 768, 'height': 1344},
                '4:3': {'width': 1152, 'height': 896},
                '3:4': {'width': 896, 'height': 1152}
            }
            
            dimensions = dimension_map.get(aspect_ratio, dimension_map['1:1'])
            quality_config = self.quality_presets.get(quality, self.quality_presets['standard'])
            
            # API request
            url = f"{self.providers['stability']['base_url']}/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
            
            headers = {
                'Authorization': f"Bearer {api_key}",
                'Content-Type': 'application/json'
            }
            
            payload = {
                'text_prompts': [
                    {'text': enhanced_prompt, 'weight': 1.0}
                ],
                'cfg_scale': quality_config['guidance'],
                'height': dimensions['height'],
                'width': dimensions['width'],
                'steps': quality_config['steps'],
                'samples': 1,
                'style_preset': 'photographic' if style == 'photorealistic' else 'enhance'
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f'Stability AI API error: {response.status_code}',
                    'details': response.text
                }
            
            # Process response
            result = response.json()
            if 'artifacts' not in result or not result['artifacts']:
                return {'success': False, 'error': 'No image generated'}
            
            # Save image
            image_data = base64.b64decode(result['artifacts'][0]['base64'])
            file_id = str(uuid.uuid4())
            filename = f"stability_{file_id}.png"
            file_path = os.path.join(self.storage_base_path, 'stability', filename)
            
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            # Store in database
            media_file = None
            if user_id:
                media_file = MediaFile(
                    user_id=user_id,
                    filename=filename,
                    original_filename=f"stability_{style}_{quality}.png",
                    file_type='image',
                    file_size=len(image_data),
                    storage_path=file_path,
                    storage_provider='stability',
                    mime_type='image/png',
                    dimensions=dimensions,
                    file_metadata={
                        'provider': 'stability_ai',
                        'model': 'stable-diffusion-xl-1024-v1-0',
                        'prompt': enhanced_prompt,
                        'style': style,
                        'quality': quality,
                        'aspect_ratio': aspect_ratio,
                        'generation_params': payload
                    }
                )
                db.session.add(media_file)
                db.session.commit()
            
            return {
                'success': True,
                'provider': 'stability_ai',
                'file_id': media_file.id if media_file else file_id,
                'filename': filename,
                'file_path': file_path,
                'url': f"/api/media/{media_file.id if media_file else file_id}",
                'dimensions': dimensions,
                'file_size': len(image_data),
                'prompt_used': enhanced_prompt,
                'style': style,
                'quality': quality
            }
            
        except Exception as e:
            logging.error(f"Stability AI generation failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def generate_video_with_runway(self, prompt: str, duration: int = 10, 
                                 style: str = 'cinematic', quality: str = 'standard',
                                 reference_image: str = None, user_id: str = None) -> Dict[str, Any]:
        """Generate video using Runway ML Gen-3"""
        try:
            api_key = self.providers['runway']['api_key']
            if not api_key:
                return {'success': False, 'error': 'Runway ML API key not configured'}
            
            # Prepare style-enhanced prompt
            style_prompt = self.style_templates.get(style, {}).get('runway', '')
            enhanced_prompt = f"{prompt}, {style_prompt}" if style_prompt else prompt
            
            headers = {
                'Authorization': f"Bearer {api_key}",
                'Content-Type': 'application/json'
            }
            
            # Create generation request
            payload = {
                'prompt': enhanced_prompt,
                'duration': min(duration, 10),  # Max 10 seconds for Gen-3
                'ratio': '16:9',
                'watermark': False
            }
            
            # Add reference image if provided
            if reference_image:
                payload['image'] = reference_image
            
            # Start generation
            url = f"{self.providers['runway']['base_url']}/v1/generate"
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f'Runway ML API error: {response.status_code}',
                    'details': response.text
                }
            
            result = response.json()
            task_id = result.get('id')
            
            if not task_id:
                return {'success': False, 'error': 'No task ID received'}
            
            # Poll for completion (simplified - in production use webhooks)
            import time
            max_attempts = 60  # 5 minutes max
            attempt = 0
            
            while attempt < max_attempts:
                status_url = f"{self.providers['runway']['base_url']}/v1/tasks/{task_id}"
                status_response = requests.get(status_url, headers=headers)
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    
                    if status_data.get('status') == 'completed':
                        video_url = status_data.get('output', {}).get('url')
                        if video_url:
                            # Download video
                            video_response = requests.get(video_url)
                            if video_response.status_code == 200:
                                file_id = str(uuid.uuid4())
                                filename = f"runway_{file_id}.mp4"
                                file_path = os.path.join(self.storage_base_path, 'runway', filename)
                                
                                with open(file_path, 'wb') as f:
                                    f.write(video_response.content)
                                
                                # Store in database
                                media_file = None
                                if user_id:
                                    media_file = MediaFile(
                                        user_id=user_id,
                                        filename=filename,
                                        original_filename=f"runway_{style}_{duration}s.mp4",
                                        file_type='video',
                                        file_size=len(video_response.content),
                                        storage_path=file_path,
                                        storage_provider='runway',
                                        mime_type='video/mp4',
                                        duration=duration,
                                        file_metadata={
                                            'provider': 'runway_ml',
                                            'model': 'gen-3-alpha',
                                            'prompt': enhanced_prompt,
                                            'style': style,
                                            'quality': quality,
                                            'duration': duration,
                                            'reference_image': reference_image,
                                            'task_id': task_id
                                        }
                                    )
                                    db.session.add(media_file)
                                    db.session.commit()
                                
                                return {
                                    'success': True,
                                    'provider': 'runway_ml',
                                    'file_id': media_file.id if media_file else file_id,
                                    'filename': filename,
                                    'file_path': file_path,
                                    'url': f"/api/media/{media_file.id if media_file else file_id}",
                                    'duration': duration,
                                    'file_size': len(video_response.content),
                                    'prompt_used': enhanced_prompt,
                                    'style': style,
                                    'quality': quality
                                }
                        
                    elif status_data.get('status') == 'failed':
                        return {
                            'success': False,
                            'error': 'Video generation failed',
                            'details': status_data.get('error', 'Unknown error')
                        }
                
                time.sleep(5)  # Wait 5 seconds before next check
                attempt += 1
            
            return {'success': False, 'error': 'Video generation timeout'}
            
        except Exception as e:
            logging.error(f"Runway ML generation failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def generate_video_with_veo3(self, prompt: str, duration: int = 15,
                               style: str = 'cinematic', user_id: str = None) -> Dict[str, Any]:
        """Generate video using Google Veo 3"""
        try:
            api_key = self.providers['google_veo']['api_key']
            if not api_key:
                return {'success': False, 'error': 'Google Veo 3 API key not configured'}
            
            # Note: This is a placeholder implementation as Veo 3 API details may vary
            # In production, you would use the actual Google Veo 3 API
            
            headers = {
                'Authorization': f"Bearer {api_key}",
                'Content-Type': 'application/json'
            }
            
            payload = {
                'prompt': prompt,
                'duration_seconds': min(duration, 60),  # Veo 3 supports longer videos
                'resolution': '1080p',
                'style': style,
                'model': 'veo-3'
            }
            
            # This would be the actual API call
            # url = f"{self.providers['google_veo']['base_url']}/v1/videos:generate"
            # response = requests.post(url, headers=headers, json=payload)
            
            # For now, return a placeholder response
            return {
                'success': False,
                'error': 'Google Veo 3 integration pending API availability',
                'message': 'This feature will be available when Google Veo 3 API is released'
            }
            
        except Exception as e:
            logging.error(f"Google Veo 3 generation failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def generate_with_midjourney(self, prompt: str, style: str = 'artistic',
                               aspect_ratio: str = '1:1', user_id: str = None) -> Dict[str, Any]:
        """Generate image using Midjourney API"""
        try:
            api_key = self.providers['midjourney']['api_key']
            if not api_key:
                return {'success': False, 'error': 'Midjourney API key not configured'}
            
            # Prepare Midjourney-specific prompt
            style_suffix = self.style_templates.get(style, {}).get('midjourney', '')
            mj_prompt = f"{prompt} {style_suffix} --ar {aspect_ratio}"
            
            headers = {
                'Authorization': f"Bearer {api_key}",
                'Content-Type': 'application/json'
            }
            
            # Submit generation request
            payload = {
                'prompt': mj_prompt,
                'webhook_url': f"{os.getenv('BASE_URL', 'http://localhost:5000')}/api/webhooks/midjourney"
            }
            
            url = f"{self.providers['midjourney']['base_url']}/v1/imagine"
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f'Midjourney API error: {response.status_code}',
                    'details': response.text
                }
            
            result = response.json()
            task_id = result.get('task_id')
            
            # Store task for webhook processing
            if user_id and task_id:
                cache_key = f"midjourney_task:{task_id}"
                task_data = {
                    'user_id': user_id,
                    'prompt': mj_prompt,
                    'style': style,
                    'aspect_ratio': aspect_ratio,
                    'status': 'pending',
                    'created_at': datetime.utcnow().isoformat()
                }
                database_service.cache_set(cache_key, task_data, 3600)  # 1 hour
            
            return {
                'success': True,
                'provider': 'midjourney',
                'task_id': task_id,
                'status': 'pending',
                'message': 'Image generation started. You will be notified when complete.',
                'prompt_used': mj_prompt,
                'estimated_time': '60-120 seconds'
            }
            
        except Exception as e:
            logging.error(f"Midjourney generation failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def generate_with_leonardo(self, prompt: str, style: str = 'photorealistic',
                             model: str = 'leonardo-vision-xl', user_id: str = None) -> Dict[str, Any]:
        """Generate image using Leonardo AI"""
        try:
            api_key = self.providers['leonardo']['api_key']
            if not api_key:
                return {'success': False, 'error': 'Leonardo AI API key not configured'}
            
            # Prepare style-enhanced prompt
            style_prompt = self.style_templates.get(style, {}).get('leonardo', '')
            enhanced_prompt = f"{prompt}, {style_prompt}" if style_prompt else prompt
            
            headers = {
                'Authorization': f"Bearer {api_key}",
                'Content-Type': 'application/json'
            }
            
            # Create generation request
            payload = {
                'prompt': enhanced_prompt,
                'modelId': model,
                'width': 1024,
                'height': 1024,
                'num_images': 1,
                'guidance_scale': 7,
                'num_inference_steps': 30
            }
            
            url = f"{self.providers['leonardo']['base_url']}/rest/v1/generations"
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f'Leonardo AI API error: {response.status_code}',
                    'details': response.text
                }
            
            result = response.json()
            generation_id = result.get('sdGenerationJob', {}).get('generationId')
            
            if not generation_id:
                return {'success': False, 'error': 'No generation ID received'}
            
            # Poll for completion
            import time
            max_attempts = 30
            attempt = 0
            
            while attempt < max_attempts:
                status_url = f"{self.providers['leonardo']['base_url']}/rest/v1/generations/{generation_id}"
                status_response = requests.get(status_url, headers=headers)
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    generation = status_data.get('generations_by_pk', {})
                    
                    if generation.get('status') == 'COMPLETE':
                        images = generation.get('generated_images', [])
                        if images:
                            image_url = images[0].get('url')
                            if image_url:
                                # Download image
                                image_response = requests.get(image_url)
                                if image_response.status_code == 200:
                                    file_id = str(uuid.uuid4())
                                    filename = f"leonardo_{file_id}.jpg"
                                    file_path = os.path.join(self.storage_base_path, 'leonardo', filename)
                                    
                                    with open(file_path, 'wb') as f:
                                        f.write(image_response.content)
                                    
                                    # Store in database
                                    media_file = None
                                    if user_id:
                                        media_file = MediaFile(
                                            user_id=user_id,
                                            filename=filename,
                                            original_filename=f"leonardo_{style}.jpg",
                                            file_type='image',
                                            file_size=len(image_response.content),
                                            storage_path=file_path,
                                            storage_provider='leonardo',
                                            mime_type='image/jpeg',
                                            dimensions={'width': 1024, 'height': 1024},
                                            file_metadata={
                                                'provider': 'leonardo_ai',
                                                'model': model,
                                                'prompt': enhanced_prompt,
                                                'style': style,
                                                'generation_id': generation_id
                                            }
                                        )
                                        db.session.add(media_file)
                                        db.session.commit()
                                    
                                    return {
                                        'success': True,
                                        'provider': 'leonardo_ai',
                                        'file_id': media_file.id if media_file else file_id,
                                        'filename': filename,
                                        'file_path': file_path,
                                        'url': f"/api/media/{media_file.id if media_file else file_id}",
                                        'dimensions': {'width': 1024, 'height': 1024},
                                        'file_size': len(image_response.content),
                                        'prompt_used': enhanced_prompt,
                                        'style': style,
                                        'model': model
                                    }
                    
                    elif generation.get('status') == 'FAILED':
                        return {'success': False, 'error': 'Image generation failed'}
                
                time.sleep(2)
                attempt += 1
            
            return {'success': False, 'error': 'Image generation timeout'}
            
        except Exception as e:
            logging.error(f"Leonardo AI generation failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def generate_media_multi_provider(self, prompt: str, media_type: str = 'image',
                                    providers: List[str] = None, style: str = 'photorealistic',
                                    quality: str = 'standard', user_id: str = None) -> Dict[str, Any]:
        """Generate media using multiple providers for comparison"""
        try:
            if not providers:
                # Auto-select best providers for media type
                if media_type == 'image':
                    providers = ['openai', 'stability', 'leonardo']
                elif media_type == 'video':
                    providers = ['runway', 'google_veo']
                else:
                    return {'success': False, 'error': 'Unsupported media type'}
            
            results = []
            
            for provider in providers:
                if provider not in self.providers:
                    continue
                
                if not self.providers[provider]['api_key']:
                    continue
                
                if media_type not in self.providers[provider]['capabilities']:
                    continue
                
                try:
                    if provider == 'openai' and media_type == 'image':
                        from src.services.media_generation_service import media_generation_service
                        result = media_generation_service.generate_image_with_dalle(
                            prompt=prompt, platform='instagram', user_id=user_id
                        )
                    elif provider == 'stability' and media_type == 'image':
                        result = self.generate_with_stability_ai(
                            prompt=prompt, style=style, quality=quality, user_id=user_id
                        )
                    elif provider == 'leonardo' and media_type == 'image':
                        result = self.generate_with_leonardo(
                            prompt=prompt, style=style, user_id=user_id
                        )
                    elif provider == 'runway' and media_type == 'video':
                        result = self.generate_video_with_runway(
                            prompt=prompt, style=style, quality=quality, user_id=user_id
                        )
                    elif provider == 'google_veo' and media_type == 'video':
                        result = self.generate_video_with_veo3(
                            prompt=prompt, style=style, user_id=user_id
                        )
                    else:
                        continue
                    
                    result['provider'] = provider
                    results.append(result)
                    
                except Exception as e:
                    logging.error(f"Provider {provider} failed: {str(e)}")
                    results.append({
                        'success': False,
                        'provider': provider,
                        'error': str(e)
                    })
            
            successful_results = [r for r in results if r.get('success')]
            
            return {
                'success': len(successful_results) > 0,
                'results': results,
                'successful_count': len(successful_results),
                'total_providers': len(providers),
                'media_type': media_type,
                'prompt': prompt,
                'style': style,
                'quality': quality
            }
            
        except Exception as e:
            logging.error(f"Multi-provider generation failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_generation_cost_estimate(self, media_type: str, provider: str, 
                                   quality: str = 'standard', duration: int = None) -> Dict[str, Any]:
        """Get cost estimate for media generation"""
        # Cost estimates in USD (approximate)
        cost_matrix = {
            'openai': {
                'image': {'standard': 0.040, 'hd': 0.080}
            },
            'stability': {
                'image': {'draft': 0.020, 'standard': 0.040, 'premium': 0.080, 'professional': 0.120}
            },
            'runway': {
                'video': {'standard': 0.50, 'premium': 1.00}  # per second
            },
            'leonardo': {
                'image': {'standard': 0.030, 'premium': 0.060}
            },
            'midjourney': {
                'image': {'standard': 0.025, 'premium': 0.050}
            }
        }
        
        try:
            provider_costs = cost_matrix.get(provider, {})
            media_costs = provider_costs.get(media_type, {})
            base_cost = media_costs.get(quality, 0.050)  # Default fallback
            
            if media_type == 'video' and duration:
                total_cost = base_cost * duration
            else:
                total_cost = base_cost
            
            return {
                'provider': provider,
                'media_type': media_type,
                'quality': quality,
                'duration': duration,
                'estimated_cost_usd': round(total_cost, 3),
                'currency': 'USD'
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'estimated_cost_usd': 0.050
            }


# Service instance
advanced_media_service = AdvancedMediaService()

