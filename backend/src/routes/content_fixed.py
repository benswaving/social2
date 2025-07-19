from flask import Blueprint, request, jsonify
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
                                        'tone': tone
                                    },
                                    ai_model_used=result.get('model_used', 'gpt-4'),
                                    quality_score=0.75
                                )
                            
                            elif content_type == 'image':
                                # Generate placeholder image content for now
                                generated_content = GeneratedContent(
                                    project_id=project_id,
                                    platform=platform,
                                    content_type=content_type,
                                    generated_text=f"Image content voor {platform}: {prompt}",
                                    generated_hashtags=f"#{platform} #image",
                                    tone_of_voice=tone or 'neutraal',
                                    generation_parameters={
                                        'prompt': prompt,
                                        'platform': platform,
                                        'content_type': content_type,
                                        'tone': tone
                                    },
                                    ai_model_used='dalle-3-placeholder',
                                    quality_score=0.70
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
            try:
                project = ContentProject.query.get(project_id)
                if project:
                    project.status = 'failed'
                    db.session.commit()
            except:
                pass

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
        
        content_types = data.get('content_types', ['text'])
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
            'per_page': per_page
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve projects', 'details': str(e)}), 500

@content_bp.route('/platforms', methods=['GET'])
def get_platforms():
    """Get supported platforms and their configurations"""
    return jsonify({'platforms': PLATFORM_CONFIGS}), 200

@content_bp.route('/projects/<project_id>/regenerate', methods=['POST'])
@token_required
def regenerate_content(current_user, project_id):
    """Regenerate content for a specific project"""
    try:
        project = ContentProject.query.filter_by(
            id=project_id, 
            user_id=current_user.id,
            deleted_at=None
        ).first()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        data = request.get_json() or {}
        content_types = data.get('content_types', ['text'])
        tone = data.get('tone', project.generation_parameters.get('tone') if project.generation_parameters else None)
        
        # Delete existing generated content
        GeneratedContent.query.filter_by(project_id=project.id).delete()
        
        # Start async regeneration
        from flask import current_app
        thread = threading.Thread(
            target=generate_content_async,
            args=(current_app._get_current_object(), project.id, project.original_prompt, project.target_platforms, content_types, tone, project.brand_guidelines)
        )
        thread.daemon = True
        thread.start()
        
        db.session.commit()
        
        return jsonify({
            'project_id': project.id,
            'status': 'regenerating',
            'message': 'Content regeneration started'
        }), 202
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Content regeneration failed', 'details': str(e)}), 500

