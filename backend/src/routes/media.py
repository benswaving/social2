from flask import Blueprint, jsonify, request, send_file
from src.routes.auth import token_required
from src.services.media_generation_service import media_generation_service
from src.models.user import MediaFile
import logging
import os

media_bp = Blueprint('media', __name__)

@media_bp.route('/media/generate-image', methods=['POST'])
@token_required
def generate_image(current_user):
    """Generate image using DALL-E 3 for social media content"""
    try:
        data = request.get_json()
        
        # Validate required parameters
        if not data.get('content_topic'):
            return jsonify({'error': 'Content topic is required'}), 400
        
        if not data.get('platform'):
            return jsonify({'error': 'Platform is required'}), 400
        
        content_topic = data['content_topic']
        platform = data['platform']
        tone = data.get('tone', 'professional')
        content_type = data.get('content_type', 'post')
        
        # Generate optimized prompt
        prompt = media_generation_service.generate_image_prompt(
            content_topic=content_topic,
            platform=platform,
            tone=tone,
            content_type=content_type
        )
        
        # Allow custom prompt override
        if data.get('custom_prompt'):
            prompt = data['custom_prompt']
        
        # Generate image
        result = media_generation_service.generate_image_with_dalle(
            prompt=prompt,
            platform=platform,
            content_type=content_type,
            user_id=current_user.id
        )
        
        if result['success']:
            return jsonify({
                'message': 'Image generated successfully',
                'image': result,
                'prompt_used': prompt
            }), 201
        else:
            return jsonify({
                'error': result.get('error', 'Unknown error'),
                'message': result.get('message', 'Failed to generate image')
            }), 500
            
    except Exception as e:
        logging.error(f"Image generation failed: {str(e)}")
        return jsonify({'error': 'Failed to generate image'}), 500

@media_bp.route('/media/generate-video-concept', methods=['POST'])
@token_required
def generate_video_concept(current_user):
    """Generate video concept and script for social media"""
    try:
        data = request.get_json()
        
        # Validate required parameters
        if not data.get('content_topic'):
            return jsonify({'error': 'Content topic is required'}), 400
        
        if not data.get('platform'):
            return jsonify({'error': 'Platform is required'}), 400
        
        content_topic = data['content_topic']
        platform = data['platform']
        tone = data.get('tone', 'engaging')
        duration = data.get('duration', 15)
        
        # Generate video concept
        result = media_generation_service.generate_video_concept(
            content_topic=content_topic,
            platform=platform,
            tone=tone,
            duration=duration
        )
        
        if result['success']:
            # Optionally generate thumbnail
            generate_thumbnail = data.get('generate_thumbnail', True)
            thumbnail_result = None
            
            if generate_thumbnail:
                thumbnail_result = media_generation_service.create_video_thumbnail(
                    video_concept=result['video_concept'],
                    user_id=current_user.id
                )
            
            response_data = {
                'message': 'Video concept generated successfully',
                'video_concept': result['video_concept'],
                'platform': platform,
                'duration': duration,
                'content_topic': content_topic,
                'tone': tone
            }
            
            if thumbnail_result and thumbnail_result.get('success'):
                response_data['thumbnail'] = thumbnail_result
            
            return jsonify(response_data), 201
        else:
            return jsonify({
                'error': result.get('error', 'Unknown error'),
                'message': result.get('message', 'Failed to generate video concept')
            }), 500
            
    except Exception as e:
        logging.error(f"Video concept generation failed: {str(e)}")
        return jsonify({'error': 'Failed to generate video concept'}), 500

@media_bp.route('/media/optimize-image', methods=['POST'])
@token_required
def optimize_image(current_user):
    """Optimize existing image for specific platform"""
    try:
        data = request.get_json()
        
        # Validate required parameters
        if not data.get('file_id'):
            return jsonify({'error': 'File ID is required'}), 400
        
        if not data.get('platform'):
            return jsonify({'error': 'Platform is required'}), 400
        
        file_id = data['file_id']
        platform = data['platform']
        content_type = data.get('content_type', 'post')
        
        # Get media file
        media_file = media_generation_service.get_media_file(file_id)
        
        if not media_file or media_file.user_id != current_user.id:
            return jsonify({'error': 'Media file not found'}), 404
        
        if media_file.file_type != 'image':
            return jsonify({'error': 'File is not an image'}), 400
        
        # Optimize image
        result = media_generation_service.optimize_image_for_platform(
            image_path=media_file.storage_path,
            platform=platform,
            content_type=content_type
        )
        
        if result['success']:
            return jsonify({
                'message': 'Image optimized successfully',
                'optimized_image': result
            }), 200
        else:
            return jsonify({
                'error': result.get('error', 'Unknown error'),
                'message': result.get('message', 'Failed to optimize image')
            }), 500
            
    except Exception as e:
        logging.error(f"Image optimization failed: {str(e)}")
        return jsonify({'error': 'Failed to optimize image'}), 500

@media_bp.route('/media/<file_id>', methods=['GET'])
@token_required
def get_media_file(current_user, file_id):
    """Get media file by ID"""
    try:
        media_file = media_generation_service.get_media_file(file_id)
        
        if not media_file or media_file.user_id != current_user.id:
            return jsonify({'error': 'Media file not found'}), 404
        
        # Check if file exists on disk
        if not os.path.exists(media_file.storage_path):
            return jsonify({'error': 'Media file not found on storage'}), 404
        
        # Return file info or serve file based on request
        if request.args.get('info') == 'true':
            return jsonify({
                'id': media_file.id,
                'filename': media_file.filename,
                'original_filename': media_file.original_filename,
                'file_type': media_file.file_type,
                'file_size': media_file.file_size,
                'mime_type': media_file.mime_type,
                'dimensions': media_file.dimensions,
                'duration': media_file.duration,
                'created_at': media_file.created_at.isoformat(),
                'metadata': media_file.file_metadata
            }), 200
        else:
            # Serve the actual file
            return send_file(
                media_file.storage_path,
                mimetype=media_file.mime_type,
                as_attachment=False,
                download_name=media_file.original_filename
            )
            
    except Exception as e:
        logging.error(f"Failed to get media file {file_id}: {str(e)}")
        return jsonify({'error': 'Failed to retrieve media file'}), 500

@media_bp.route('/media/<file_id>', methods=['DELETE'])
@token_required
def delete_media_file(current_user, file_id):
    """Delete media file"""
    try:
        result = media_generation_service.delete_media_file(file_id, current_user.id)
        
        if result['success']:
            return jsonify({'message': result['message']}), 200
        else:
            return jsonify({'error': result['error']}), 404 if 'not found' in result['error'] else 500
            
    except Exception as e:
        logging.error(f"Failed to delete media file {file_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete media file'}), 500

@media_bp.route('/media', methods=['GET'])
@token_required
def list_media_files(current_user):
    """List user's media files"""
    try:
        # Get query parameters
        file_type = request.args.get('type')
        limit = min(int(request.args.get('limit', 50)), 100)  # Max 100 files per request
        offset = int(request.args.get('offset', 0))
        
        result = media_generation_service.list_user_media(
            user_id=current_user.id,
            file_type=file_type,
            limit=limit,
            offset=offset
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify({
                'error': result.get('error', 'Unknown error'),
                'message': result.get('message', 'Failed to list media files')
            }), 500
            
    except Exception as e:
        logging.error(f"Failed to list media files: {str(e)}")
        return jsonify({'error': 'Failed to list media files'}), 500

@media_bp.route('/media/platform-specs', methods=['GET'])
def get_platform_specifications():
    """Get platform-specific media specifications"""
    return jsonify({
        'platform_specifications': media_generation_service.platform_specs,
        'supported_platforms': list(media_generation_service.platform_specs.keys())
    }), 200

@media_bp.route('/media/generate-prompt', methods=['POST'])
@token_required
def generate_image_prompt(current_user):
    """Generate optimized DALL-E prompt for content"""
    try:
        data = request.get_json()
        
        # Validate required parameters
        if not data.get('content_topic'):
            return jsonify({'error': 'Content topic is required'}), 400
        
        if not data.get('platform'):
            return jsonify({'error': 'Platform is required'}), 400
        
        content_topic = data['content_topic']
        platform = data['platform']
        tone = data.get('tone', 'professional')
        content_type = data.get('content_type', 'post')
        
        # Generate prompt
        prompt = media_generation_service.generate_image_prompt(
            content_topic=content_topic,
            platform=platform,
            tone=tone,
            content_type=content_type
        )
        
        return jsonify({
            'prompt': prompt,
            'content_topic': content_topic,
            'platform': platform,
            'tone': tone,
            'content_type': content_type
        }), 200
        
    except Exception as e:
        logging.error(f"Prompt generation failed: {str(e)}")
        return jsonify({'error': 'Failed to generate prompt'}), 500

