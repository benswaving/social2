from flask import Blueprint, jsonify, request
from src.routes.auth import token_required
from src.services.advanced_media_service import advanced_media_service
from src.services.security_service import security_service
import logging

advanced_media_bp = Blueprint('advanced_media', __name__)

@advanced_media_bp.route('/advanced-media/providers', methods=['GET'])
def get_available_providers():
    """Get list of available media generation providers"""
    try:
        media_type = request.args.get('type')  # 'image' or 'video'
        providers = advanced_media_service.get_available_providers(media_type)
        
        return jsonify({
            'providers': providers,
            'total_count': len(providers),
            'media_type': media_type
        }), 200
        
    except Exception as e:
        logging.error(f"Failed to get providers: {str(e)}")
        return jsonify({'error': 'Failed to get available providers'}), 500

@advanced_media_bp.route('/advanced-media/generate/stability', methods=['POST'])
@token_required
@security_service.rate_limit_decorator('api_media')
def generate_with_stability(current_user):
    """Generate image using Stability AI"""
    try:
        data = request.get_json()
        
        # Validate input
        validation_rules = {
            'prompt': 'required|safe_text',
            'style': 'safe_text',
            'quality': 'safe_text',
            'aspect_ratio': 'safe_text'
        }
        
        is_valid, errors = security_service.validate_input(data, validation_rules)
        if not is_valid:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Sanitize inputs
        prompt = security_service.sanitize_text(data['prompt'], max_length=1000)
        style = data.get('style', 'photorealistic')
        quality = data.get('quality', 'standard')
        aspect_ratio = data.get('aspect_ratio', '1:1')
        
        # Generate image
        result = advanced_media_service.generate_with_stability_ai(
            prompt=prompt,
            style=style,
            quality=quality,
            aspect_ratio=aspect_ratio,
            user_id=current_user.id
        )
        
        if result['success']:
            return jsonify({
                'message': 'Image generated successfully with Stability AI',
                'result': result
            }), 201
        else:
            return jsonify({
                'error': result.get('error', 'Generation failed'),
                'details': result.get('details', '')
            }), 500
            
    except Exception as e:
        logging.error(f"Stability AI generation failed: {str(e)}")
        return jsonify({'error': 'Failed to generate image with Stability AI'}), 500

@advanced_media_bp.route('/advanced-media/generate/runway', methods=['POST'])
@token_required
@security_service.rate_limit_decorator('api_media')
def generate_with_runway(current_user):
    """Generate video using Runway ML"""
    try:
        data = request.get_json()
        
        # Validate input
        validation_rules = {
            'prompt': 'required|safe_text',
            'style': 'safe_text',
            'quality': 'safe_text'
        }
        
        is_valid, errors = security_service.validate_input(data, validation_rules)
        if not is_valid:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Sanitize inputs
        prompt = security_service.sanitize_text(data['prompt'], max_length=1000)
        duration = min(int(data.get('duration', 10)), 10)  # Max 10 seconds
        style = data.get('style', 'cinematic')
        quality = data.get('quality', 'standard')
        reference_image = data.get('reference_image')
        
        # Generate video
        result = advanced_media_service.generate_video_with_runway(
            prompt=prompt,
            duration=duration,
            style=style,
            quality=quality,
            reference_image=reference_image,
            user_id=current_user.id
        )
        
        if result['success']:
            return jsonify({
                'message': 'Video generation started with Runway ML',
                'result': result
            }), 202  # Accepted - processing
        else:
            return jsonify({
                'error': result.get('error', 'Generation failed'),
                'details': result.get('details', '')
            }), 500
            
    except Exception as e:
        logging.error(f"Runway ML generation failed: {str(e)}")
        return jsonify({'error': 'Failed to generate video with Runway ML'}), 500

@advanced_media_bp.route('/advanced-media/generate/veo3', methods=['POST'])
@token_required
@security_service.rate_limit_decorator('api_media')
def generate_with_veo3(current_user):
    """Generate video using Google Veo 3"""
    try:
        data = request.get_json()
        
        # Validate input
        validation_rules = {
            'prompt': 'required|safe_text',
            'style': 'safe_text'
        }
        
        is_valid, errors = security_service.validate_input(data, validation_rules)
        if not is_valid:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Sanitize inputs
        prompt = security_service.sanitize_text(data['prompt'], max_length=1000)
        duration = min(int(data.get('duration', 15)), 60)  # Max 60 seconds for Veo 3
        style = data.get('style', 'cinematic')
        
        # Generate video
        result = advanced_media_service.generate_video_with_veo3(
            prompt=prompt,
            duration=duration,
            style=style,
            user_id=current_user.id
        )
        
        if result['success']:
            return jsonify({
                'message': 'Video generation started with Google Veo 3',
                'result': result
            }), 202
        else:
            return jsonify({
                'error': result.get('error', 'Generation failed'),
                'message': result.get('message', '')
            }), 500
            
    except Exception as e:
        logging.error(f"Google Veo 3 generation failed: {str(e)}")
        return jsonify({'error': 'Failed to generate video with Google Veo 3'}), 500

@advanced_media_bp.route('/advanced-media/generate/midjourney', methods=['POST'])
@token_required
@security_service.rate_limit_decorator('api_media')
def generate_with_midjourney(current_user):
    """Generate image using Midjourney"""
    try:
        data = request.get_json()
        
        # Validate input
        validation_rules = {
            'prompt': 'required|safe_text',
            'style': 'safe_text',
            'aspect_ratio': 'safe_text'
        }
        
        is_valid, errors = security_service.validate_input(data, validation_rules)
        if not is_valid:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Sanitize inputs
        prompt = security_service.sanitize_text(data['prompt'], max_length=1000)
        style = data.get('style', 'artistic')
        aspect_ratio = data.get('aspect_ratio', '1:1')
        
        # Generate image
        result = advanced_media_service.generate_with_midjourney(
            prompt=prompt,
            style=style,
            aspect_ratio=aspect_ratio,
            user_id=current_user.id
        )
        
        if result['success']:
            return jsonify({
                'message': 'Image generation started with Midjourney',
                'result': result
            }), 202
        else:
            return jsonify({
                'error': result.get('error', 'Generation failed')
            }), 500
            
    except Exception as e:
        logging.error(f"Midjourney generation failed: {str(e)}")
        return jsonify({'error': 'Failed to generate image with Midjourney'}), 500

@advanced_media_bp.route('/advanced-media/generate/leonardo', methods=['POST'])
@token_required
@security_service.rate_limit_decorator('api_media')
def generate_with_leonardo(current_user):
    """Generate image using Leonardo AI"""
    try:
        data = request.get_json()
        
        # Validate input
        validation_rules = {
            'prompt': 'required|safe_text',
            'style': 'safe_text',
            'model': 'safe_text'
        }
        
        is_valid, errors = security_service.validate_input(data, validation_rules)
        if not is_valid:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Sanitize inputs
        prompt = security_service.sanitize_text(data['prompt'], max_length=1000)
        style = data.get('style', 'photorealistic')
        model = data.get('model', 'leonardo-vision-xl')
        
        # Generate image
        result = advanced_media_service.generate_with_leonardo(
            prompt=prompt,
            style=style,
            model=model,
            user_id=current_user.id
        )
        
        if result['success']:
            return jsonify({
                'message': 'Image generated successfully with Leonardo AI',
                'result': result
            }), 201
        else:
            return jsonify({
                'error': result.get('error', 'Generation failed')
            }), 500
            
    except Exception as e:
        logging.error(f"Leonardo AI generation failed: {str(e)}")
        return jsonify({'error': 'Failed to generate image with Leonardo AI'}), 500

@advanced_media_bp.route('/advanced-media/generate/multi-provider', methods=['POST'])
@token_required
@security_service.rate_limit_decorator('api_media')
def generate_multi_provider(current_user):
    """Generate media using multiple providers for comparison"""
    try:
        data = request.get_json()
        
        # Validate input
        validation_rules = {
            'prompt': 'required|safe_text',
            'media_type': 'required|safe_text',
            'style': 'safe_text',
            'quality': 'safe_text'
        }
        
        is_valid, errors = security_service.validate_input(data, validation_rules)
        if not is_valid:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Sanitize inputs
        prompt = security_service.sanitize_text(data['prompt'], max_length=1000)
        media_type = data['media_type']
        providers = data.get('providers', [])
        style = data.get('style', 'photorealistic')
        quality = data.get('quality', 'standard')
        
        if media_type not in ['image', 'video']:
            return jsonify({'error': 'Media type must be "image" or "video"'}), 400
        
        # Generate with multiple providers
        result = advanced_media_service.generate_media_multi_provider(
            prompt=prompt,
            media_type=media_type,
            providers=providers,
            style=style,
            quality=quality,
            user_id=current_user.id
        )
        
        if result['success']:
            return jsonify({
                'message': f'Multi-provider {media_type} generation completed',
                'result': result
            }), 201
        else:
            return jsonify({
                'error': result.get('error', 'Multi-provider generation failed'),
                'partial_results': result.get('results', [])
            }), 500
            
    except Exception as e:
        logging.error(f"Multi-provider generation failed: {str(e)}")
        return jsonify({'error': 'Failed to generate with multiple providers'}), 500

@advanced_media_bp.route('/advanced-media/cost-estimate', methods=['POST'])
@token_required
def get_cost_estimate(current_user):
    """Get cost estimate for media generation"""
    try:
        data = request.get_json()
        
        # Validate input
        validation_rules = {
            'media_type': 'required|safe_text',
            'provider': 'required|safe_text',
            'quality': 'safe_text'
        }
        
        is_valid, errors = security_service.validate_input(data, validation_rules)
        if not is_valid:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        media_type = data['media_type']
        provider = data['provider']
        quality = data.get('quality', 'standard')
        duration = data.get('duration')
        
        # Get cost estimate
        estimate = advanced_media_service.get_generation_cost_estimate(
            media_type=media_type,
            provider=provider,
            quality=quality,
            duration=duration
        )
        
        return jsonify({
            'cost_estimate': estimate,
            'currency': 'USD'
        }), 200
        
    except Exception as e:
        logging.error(f"Cost estimate failed: {str(e)}")
        return jsonify({'error': 'Failed to get cost estimate'}), 500

@advanced_media_bp.route('/advanced-media/styles', methods=['GET'])
def get_available_styles():
    """Get available styles for media generation"""
    try:
        provider = request.args.get('provider', 'all')
        
        if provider == 'all':
            styles = list(advanced_media_service.style_templates.keys())
        else:
            styles = list(advanced_media_service.style_templates.keys())
        
        return jsonify({
            'styles': styles,
            'provider': provider,
            'style_descriptions': {
                'photorealistic': 'High-quality, realistic photography style',
                'artistic': 'Creative, stylized artistic interpretation',
                'minimalist': 'Clean, simple, modern design',
                'cinematic': 'Movie-like quality with dramatic lighting'
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Failed to get styles: {str(e)}")
        return jsonify({'error': 'Failed to get available styles'}), 500

@advanced_media_bp.route('/advanced-media/quality-presets', methods=['GET'])
def get_quality_presets():
    """Get available quality presets"""
    try:
        return jsonify({
            'quality_presets': advanced_media_service.quality_presets,
            'descriptions': {
                'draft': 'Fast generation, lower quality',
                'standard': 'Balanced quality and speed',
                'premium': 'High quality, slower generation',
                'professional': 'Highest quality, longest generation time'
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Failed to get quality presets: {str(e)}")
        return jsonify({'error': 'Failed to get quality presets'}), 500

