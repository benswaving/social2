from flask import Blueprint, jsonify, request
from src.models.user import ContentProject, GeneratedContent, db
from src.routes.auth import token_required
from src.services.ai_service import ai_content_service, media_generation_service
from datetime import datetime
import uuid
import asyncio
import threading

content_bp = Blueprint('content', __name__)

# Platform-specific configurations
PLATFORM_CONFIGS = {
    'instagram': {
        'max_text_length': 2200,
        'max_hashtags': 30,
        'supported_content_types': ['text', 'image', 'video', 'carousel'],
        'tone_suggestions': ['creatief', 'visueel', 'inspirerend', 'lifestyle']
    },
    'linkedin': {
        'max_text_length': 3000,
        'max_hashtags': 5,
        'supported_content_types': ['text', 'image', 'video'],
        'tone_suggestions': ['zakelijk', 'professioneel', 'inhoudelijk', 'thought-leadership']
    },
    'tiktok': {
        'max_text_length': 150,
        'max_hashtags': 10,
        'supported_content_types': ['video'],
        'tone_suggestions': ['informeel', 'speels', 'trending', 'energiek']
    },
    'twitter': {
        'max_text_length': 280,
        'max_hashtags': 5,
        'supported_content_types': ['text', 'image', 'video'],
        'tone_suggestions': ['direct', 'kort', 'prikkelend', 'conversationeel']
    },
    'facebook': {
        'max_text_length': 63206,
        'max_hashtags': 10,
        'supported_content_types': ['text', 'image', 'video'],
        'tone_suggestions': ['vriendelijk', 'gemeenschapsgericht', 'verhalen', 'persoonlijk']
    }
}

def validate_generation_request(data):
    """Validate content generation request"""
    errors = []
    
    # Required fields
    if not data.get('prompt'):
        errors.append('Prompt is required')
    elif len(data['prompt'].strip()) < 10:
        errors.append('Prompt must be at least 10 characters long')
    
    if not data.get('platforms') or not isinstance(data['platforms'], list):
        errors.append('At least one platform must be specified')
    else:
        invalid_platforms = [p for p in data['platforms'] if p not in PLATFORM_CONFIGS]
        if invalid_platforms:
            errors.append(f'Invalid platforms: {", ".join(invalid_platforms)}')
    
    # Optional validations
    if data.get('content_types'):
        if not isinstance(data['content_types'], list):
            errors.append('Content types must be a list')
        else:
            valid_types = ['text', 'image', 'video', 'carousel']
            invalid_types = [t for t in data['content_types'] if t not in valid_types]
            if invalid_types:
                errors.append(f'Invalid content types: {", ".join(invalid_types)}')
    
    return errors

def generate_content_async(app, project_id, prompt, platforms, content_types, tone, brand_guidelines):
    """Generate content asynchronously"""
    with app.app_context():
        try:
            project = ContentProject.query.get(project_id)
            if not project:
                return
        
        project.status = 'generating'
        db.session.commit()
        
        for platform in platforms:
            platform_config = PLATFORM_CONFIGS[platform]
            
            for content_type in content_types:
                if content_type in platform_config['supported_content_types']:
                    try:
                        if content_type == 'text':
                            # Generate text content using AI
                            result = ai_content_service.generate_text_content(
                                prompt=prompt,
                                platform=platform,
                                tone=tone,
                                brand_guidelines=brand_guidelines
                            )
                            
                            generated_content = GeneratedContent(
                                project_id=project_id,
                                platform=platform,
                                content_type=content_type,
                                generated_text=result['text'],
                                generated_hashtags=result['hashtags'],
                                tone_of_voice=tone or 'neutraal',
                                generation_parameters={
                                    'prompt': prompt,
                                    'platform': platform,
                                    'content_type': content_type,
                                    'tone': tone,
                                    'brand_guidelines': brand_guidelines
                                },
                                ai_model_used=result['model_used'],
                                quality_score=0.85
                            )
                            
                        elif content_type == 'image':
                            # Generate image prompt and then image
                            image_prompt = ai_content_service.generate_image_prompt(
                                content_prompt=prompt,
                                platform=platform
                            )
                            
                            # For now, just store the prompt - actual image generation would happen here
                            generated_content = GeneratedContent(
                                project_id=project_id,
                                platform=platform,
                                content_type=content_type,
                                generated_text=f"Image prompt: {image_prompt}",
                                generated_hashtags=ai_content_service.generate_hashtags(prompt, platform),
                                tone_of_voice=tone or 'neutraal',
                                generation_parameters={
                                    'prompt': prompt,
                                    'image_prompt': image_prompt,
                                    'platform': platform,
                                    'content_type': content_type
                                },
                                ai_model_used='gpt-4 + dall-e-3',
                                quality_score=0.80
                            )
                            
                        else:
                            # Placeholder for video and other content types
                            generated_content = GeneratedContent(
                                project_id=project_id,
                                platform=platform,
                                content_type=content_type,
                                generated_text=f"[{content_type.upper()}] {prompt} - optimized for {platform}",
                                generated_hashtags=' '.join(ai_content_service.generate_hashtags(prompt, platform)),
                                tone_of_voice=tone or 'neutraal',
                                generation_parameters={
                                    'prompt': prompt,
                                    'platform': platform,
                                    'content_type': content_type,
                                    'tone': tone
                                },
                                ai_model_used='gpt-4',
                                quality_score=0.75
                            )
                        
                        db.session.add(generated_content)
                        
                    except Exception as e:
                        print(f"Error generating {content_type} for {platform}: {e}")
                        # Create error content
                        error_content = GeneratedContent(
                            project_id=project_id,
                            platform=platform,
                            content_type=content_type,
                            generated_text=f"Error generating content: {str(e)}",
                            generated_hashtags=f"#{platform} #error",
                            tone_of_voice=tone or 'neutraal',
                            generation_parameters={
                                'prompt': prompt,
                                'platform': platform,
                                'content_type': content_type,
                                'error': str(e)
                            },
                            ai_model_used='error',
                            quality_score=0.0
                        )
                        db.session.add(error_content)
        
        # Update project status
        project.status = 'ready'
        db.session.commit()
        
    except Exception as e:
        print(f"Error in async content generation: {e}")
        project = ContentProject.query.get(project_id)
        if project:
            project.status = 'failed'
            db.session.commit()

@content_bp.route('/generate', methods=['POST'])
@token_required
def generate_content(current_user):
    """Generate new content for specified platforms"""
    try:
        data = request.get_json()
        
        # Validate request
        errors = validate_generation_request(data)
        if errors:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Create content project
        project = ContentProject(
            user_id=current_user.id,
            title=data.get('title', f"Content voor {', '.join(data['platforms'])}"),
            description=data.get('description'),
            original_prompt=data['prompt'].strip(),
            target_platforms=data['platforms'],
            brand_guidelines=data.get('brand_guidelines'),
            status='draft'
        )
        
        db.session.add(project)
        db.session.flush()  # Get the project ID
        
        content_types = data.get('content_types', ['text', 'image'])
        tone = data.get('tone')
        brand_guidelines = data.get('brand_guidelines')
        
        # Start async content generation
        from flask import current_app
        thread = threading.Thread(
            target=generate_content_async,
            args=(current_app._get_current_object(), project.id, data['prompt'], data['platforms'], content_types, tone, brand_guidelines)
        )
        thread.daemon = True
        thread.start()
        
        db.session.commit()
        
        return jsonify({
            'project_id': project.id,
            'status': 'draft',
            'estimated_completion': datetime.utcnow().isoformat(),
            'message': 'Content generation started'
        }), 202
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Content generation failed', 'details': str(e)}), 500

@content_bp.route('/projects/<project_id>', methods=['GET'])
@token_required
def get_project(current_user, project_id):
    """Get content project with generated content"""
    try:
        project = ContentProject.query.filter_by(
            id=project_id, 
            user_id=current_user.id,
            deleted_at=None
        ).first()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Get generated content
        generated_content = GeneratedContent.query.filter_by(project_id=project.id).all()
        
        project_data = project.to_dict()
        project_data['generated_content'] = [content.to_dict() for content in generated_content]
        
        return jsonify(project_data), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve project', 'details': str(e)}), 500

@content_bp.route('/projects', methods=['GET'])
@token_required
def get_user_projects(current_user):
    """Get all user's content projects"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        status_filter = request.args.get('status')
        
        query = ContentProject.query.filter_by(
            user_id=current_user.id,
            deleted_at=None
        )
        
        if status_filter:
            query = query.filter_by(status=status_filter)
        
        query = query.order_by(ContentProject.created_at.desc())
        
        projects = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        return jsonify({
            'projects': [project.to_dict() for project in projects.items],
            'total': projects.total,
            'pages': projects.pages,
            'current_page': page,
            'per_page': per_page,
            'has_next': projects.has_next,
            'has_prev': projects.has_prev
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve projects', 'details': str(e)}), 500

@content_bp.route('/content/<content_id>', methods=['GET'])
@token_required
def get_content(current_user, content_id):
    """Get specific generated content"""
    try:
        content = GeneratedContent.query.join(ContentProject).filter(
            GeneratedContent.id == content_id,
            ContentProject.user_id == current_user.id
        ).first()
        
        if not content:
            return jsonify({'error': 'Content not found'}), 404
        
        return jsonify(content.to_dict()), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve content', 'details': str(e)}), 500

@content_bp.route('/content/<content_id>', methods=['PUT'])
@token_required
def update_content(current_user, content_id):
    """Update generated content"""
    try:
        content = GeneratedContent.query.join(ContentProject).filter(
            GeneratedContent.id == content_id,
            ContentProject.user_id == current_user.id
        ).first()
        
        if not content:
            return jsonify({'error': 'Content not found'}), 404
        
        data = request.get_json()
        
        # Update allowed fields
        if 'generated_text' in data:
            platform_config = PLATFORM_CONFIGS.get(content.platform, {})
            max_length = platform_config.get('max_text_length', 10000)
            
            if len(data['generated_text']) > max_length:
                return jsonify({
                    'error': f'Text too long for {content.platform}. Maximum {max_length} characters allowed.'
                }), 400
            
            content.generated_text = data['generated_text']
        
        if 'generated_hashtags' in data:
            content.generated_hashtags = data['generated_hashtags']
        
        if 'media_urls' in data:
            content.media_urls = data['media_urls']
        
        db.session.commit()
        
        return jsonify(content.to_dict()), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update content', 'details': str(e)}), 500

@content_bp.route('/content/<content_id>/regenerate', methods=['POST'])
@token_required
def regenerate_content(current_user, content_id):
    """Regenerate specific content with new parameters"""
    try:
        content = GeneratedContent.query.join(ContentProject).filter(
            GeneratedContent.id == content_id,
            ContentProject.user_id == current_user.id
        ).first()
        
        if not content:
            return jsonify({'error': 'Content not found'}), 404
        
        data = request.get_json()
        
        # Update generation parameters
        new_params = content.generation_parameters.copy() if content.generation_parameters else {}
        
        if data.get('tone'):
            new_params['tone'] = data['tone']
            content.tone_of_voice = data['tone']
        
        if data.get('additional_prompt'):
            new_params['additional_prompt'] = data['additional_prompt']
        
        if data.get('style'):
            new_params['style'] = data['style']
        
        # In a real implementation, this would trigger async regeneration
        # For now, we'll just update the content with a new version
        if data.get('regenerate_text', True):
            content.generated_text = f"[REGENERATED] {content.project.original_prompt} - {data.get('additional_prompt', '')} - optimized for {content.platform}"
        
        content.generation_parameters = new_params
        content.ai_model_used = 'gpt-4-regenerated'
        
        db.session.commit()
        
        return jsonify({
            'task_id': str(uuid.uuid4()),  # Placeholder task ID
            'status': 'regenerating',
            'content': content.to_dict()
        }), 202
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to regenerate content', 'details': str(e)}), 500

@content_bp.route('/content/<content_id>/preview/<platform>', methods=['GET'])
@token_required
def preview_content(current_user, content_id, platform):
    """Generate platform-specific preview"""
    try:
        content = GeneratedContent.query.join(ContentProject).filter(
            GeneratedContent.id == content_id,
            ContentProject.user_id == current_user.id
        ).first()
        
        if not content:
            return jsonify({'error': 'Content not found'}), 404
        
        if platform not in PLATFORM_CONFIGS:
            return jsonify({'error': 'Invalid platform'}), 400
        
        platform_config = PLATFORM_CONFIGS[platform]
        
        # Generate preview data
        preview_data = {
            'platform': platform,
            'content_text': content.generated_text,
            'hashtags': content.generated_hashtags,
            'media_urls': content.media_urls or [],
            'character_count': len(content.generated_text or ''),
            'max_characters': platform_config['max_text_length'],
            'hashtag_count': len((content.generated_hashtags or '').split()) if content.generated_hashtags else 0,
            'max_hashtags': platform_config['max_hashtags'],
            'estimated_reach': 1500,  # Placeholder
            'engagement_prediction': 0.75,  # Placeholder
            'preview_html': f'<div class="{platform}-preview">{content.generated_text}</div>'
        }
        
        return jsonify(preview_data), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to generate preview', 'details': str(e)}), 500

@content_bp.route('/platforms', methods=['GET'])
def get_platforms():
    """Get available platforms and their configurations"""
    return jsonify({
        'platforms': {
            platform: {
                'name': platform.title(),
                'max_text_length': config['max_text_length'],
                'max_hashtags': config['max_hashtags'],
                'supported_content_types': config['supported_content_types'],
                'tone_suggestions': config['tone_suggestions']
            }
            for platform, config in PLATFORM_CONFIGS.items()
        }
    }), 200

@content_bp.route('/projects/<project_id>', methods=['DELETE'])
@token_required
def delete_project(current_user, project_id):
    """Soft delete a content project"""
    try:
        project = ContentProject.query.filter_by(
            id=project_id,
            user_id=current_user.id,
            deleted_at=None
        ).first()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Soft delete
        project.deleted_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Project deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete project', 'details': str(e)}), 500

