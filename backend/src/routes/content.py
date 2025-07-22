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
        print(f"DEBUG: Starting async generation for project {project_id}")
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
                                # Generate actual image using DALL-E with extensive debugging
                                print(f"🖼️  DEBUG: Starting image generation for {platform}")
                                try:
                                    # Create image prompt
                                    print(f"🖼️  DEBUG: Creating image prompt for: {prompt}")
                                    image_prompt = ai_content_service.generate_image_prompt(
                                        content_prompt=prompt,
                                        platform=platform,
                                        style=tone
                                    )
                                    print(f"🖼️  DEBUG: Generated image prompt: {image_prompt}")
                                    
                                    # Generate image with DALL-E
                                    print(f"🖼️  DEBUG: Calling DALL-E API...")
                                    try:
                                        print(f"🖼️  DEBUG: About to call media_generation_service.generate_image()")
                                        image_result = media_generation_service.generate_image(
                                            prompt=image_prompt,
                                            size="1024x1024",
                                            quality="standard"
                                        )
                                        print(f"🖼️  DEBUG: DALL-E API call completed successfully!")
                                        print(f"🖼️  DEBUG: DALL-E response: {image_result}")
                                    except Exception as dalle_error:
                                        print(f"🖼️  ERROR: DALL-E API call failed: {dalle_error}")
                                        print(f"🖼️  ERROR: DALL-E error type: {type(dalle_error)}")
                                        import traceback
                                        print(f"🖼️  ERROR: DALL-E traceback: {traceback.format_exc()}")
                                        raise dalle_error
                                    
                                    # Create media storage directory if it doesn't exist
                                    import os
                                    import uuid
                                    media_dir = "/opt/socials/media"
                                    print(f"🖼️  DEBUG: Creating media directory: {media_dir}")
                                    os.makedirs(media_dir, exist_ok=True)
                                    print(f"🖼️  DEBUG: Media directory exists: {os.path.exists(media_dir)}")
                                    
                                    # Download and save image
                                    filename = f"{uuid.uuid4()}.png"
                                    print(f"🖼️  DEBUG: Generated filename: {filename}")
                                    print(f"🖼️  DEBUG: Downloading image from: {image_result['image_url']}")
                                    
                                    local_path = media_generation_service.download_and_save_image(
                                        image_url=image_result['image_url'],
                                        filename=filename,
                                        storage_path=media_dir
                                    )
                                    print(f"🖼️  DEBUG: Image saved to: {local_path}")
                                    print(f"🖼️  DEBUG: File exists after save: {os.path.exists(local_path)}")
                                    
                                    if os.path.exists(local_path):
                                        file_size = os.path.getsize(local_path)
                                        print(f"🖼️  DEBUG: File size: {file_size} bytes")
                                    else:
                                        print(f"🖼️  ERROR: File does not exist after save!")
                                    
                                    # Create content with image URL
                                    media_url = f"/media/{filename}"
                                    print(f"🖼️  DEBUG: Storing media URL in database: {media_url}")
                                    
                                    generated_content = GeneratedContent(
                                        project_id=project_id,
                                        platform=platform,
                                        content_type=content_type,
                                        generated_text=f"AI-generated image voor {platform}: {prompt}",
                                        generated_hashtags=f"#{platform} #AIgenerated #image",
                                        media_urls=[media_url],  # Store relative path
                                        tone_of_voice=tone or 'neutraal',
                                        generation_parameters={
                                            'prompt': prompt,
                                            'image_prompt': image_prompt,
                                            'platform': platform,
                                            'content_type': content_type,
                                            'tone': tone,
                                            'local_path': local_path,
                                            'media_url': media_url
                                        },
                                        ai_model_used='dall-e-3',
                                        quality_score=0.85
                                    )
                                    print(f"🖼️  DEBUG: Created GeneratedContent with media_urls: {generated_content.media_urls}")
                                except Exception as img_error:
                                    print(f"Image generation failed: {img_error}")
                                    # Fallback to text description
                                    generated_content = GeneratedContent(
                                        project_id=project_id,
                                        platform=platform,
                                        content_type=content_type,
                                        generated_text=f"Image generatie gefaald voor {platform}: {prompt}. Error: {str(img_error)}",
                                        generated_hashtags=f"#{platform} #error",
                                        tone_of_voice=tone or 'neutraal',
                                        generation_parameters={
                                            'prompt': prompt,
                                            'platform': platform,
                                            'content_type': content_type,
                                            'tone': tone
                                        },
                                        ai_model_used='dall-e-3-failed',
                                        quality_score=0.30
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
def generate_content():
    """Generate new content for specified platforms"""
    try:
        data = request.get_json()
        print(f"DEBUG: Received data: {data}")
        
        # Validate request
        errors = validate_generation_request(data)
        if errors:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Create content project
        project = ContentProject(
            user_id="demo-user-id",
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
def get_project(project_id):
    """Get content project with generated content"""
    try:
        project = ContentProject.query.filter_by(
            id=project_id, 
            
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
def get_user_projects(current_user):
    """Get all user's content projects"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        status_filter = request.args.get('status')
        
        query = ContentProject.query.filter_by(
            
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
def regenerate_content(current_user, project_id):
    """Regenerate content for a specific project"""
    try:
        project = ContentProject.query.filter_by(
            id=project_id, 
            
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


@content_bp.route('/projects/<project_id>/content', methods=['GET'])
def get_project_content(project_id):
    """Get generated content for a specific project"""
    try:
        # Find the project
        project = ContentProject.query.filter_by(
            id=project_id, 
             
            deleted_at=None
        ).first()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Get all generated content for this project
        generated_content = GeneratedContent.query.filter_by(
            project_id=project.id
        ).order_by(GeneratedContent.created_at.desc()).all()
        
        # Convert to dict format
        content_list = []
        for content in generated_content:
            # Convert media_urls array to media_url string for frontend compatibility
            media_url = None
            if content.media_urls:
                try:
                    # Parse JSON array and get first URL
                    import json
                    print(f"🔍 DEBUG: Raw media_urls from DB: {content.media_urls} (type: {type(content.media_urls)})")
                    
                    if isinstance(content.media_urls, str):
                        # Try to parse as JSON array
                        urls = json.loads(content.media_urls)
                        print(f"🔍 DEBUG: Parsed JSON array: {urls}")
                    else:
                        # Already a list/array
                        urls = content.media_urls
                        print(f"🔍 DEBUG: Already array: {urls}")
                    
                    media_url = urls[0] if urls and len(urls) > 0 else None
                    print(f"🔍 DEBUG: Extracted media_url: {media_url}")
                    
                except Exception as parse_error:
                    print(f"🔍 ERROR: Media URL parsing failed: {parse_error}")
                    print(f"🔍 ERROR: Raw content.media_urls: {repr(content.media_urls)}")
                    # Fallback: treat as string
                    media_url = content.media_urls if content.media_urls else None
                    print(f"🔍 DEBUG: Fallback media_url: {media_url}")
            
            content_dict = {
                'id': content.id,
                'platform': content.platform,
                'content_type': content.content_type,
                'text_content': content.generated_text,
                'media_url': media_url,  # Frontend expects media_url (singular)
                'hashtags': content.generated_hashtags,
                'created_at': content.created_at.isoformat() if content.created_at else None,
                
            }
            content_list.append(content_dict)
        
        return jsonify(content_list), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve content', 'details': str(e)}), 500
