from flask import Blueprint, jsonify, request
from src.routes.auth import token_required
from src.services.ai_service import ai_content_service, media_generation_service
from src.models.user import GeneratedContent, ContentProject, db
import uuid

ai_analysis_bp = Blueprint('ai_analysis', __name__)

@ai_analysis_bp.route('/analyze-content', methods=['POST'])
@token_required
def analyze_content(current_user):
    """Analyze content quality and provide suggestions"""
    try:
        data = request.get_json()
        
        if not data.get('content'):
            return jsonify({'error': 'Content is required'}), 400
        
        if not data.get('platform'):
            return jsonify({'error': 'Platform is required'}), 400
        
        content = data['content']
        platform = data['platform']
        
        # Analyze content using AI service
        analysis = ai_content_service.analyze_content_quality(content, platform)
        
        return jsonify({
            'analysis': analysis,
            'content_length': len(content),
            'platform': platform,
            'analyzed_at': ai_content_service.datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Content analysis failed', 'details': str(e)}), 500

@ai_analysis_bp.route('/generate-hashtags', methods=['POST'])
@token_required
def generate_hashtags(current_user):
    """Generate hashtags for content"""
    try:
        data = request.get_json()
        
        if not data.get('content'):
            return jsonify({'error': 'Content is required'}), 400
        
        if not data.get('platform'):
            return jsonify({'error': 'Platform is required'}), 400
        
        content = data['content']
        platform = data['platform']
        count = data.get('count', 5)
        
        # Generate hashtags using AI service
        hashtags = ai_content_service.generate_hashtags(content, platform, count)
        
        return jsonify({
            'hashtags': hashtags,
            'hashtag_string': ' '.join(hashtags),
            'count': len(hashtags),
            'platform': platform
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Hashtag generation failed', 'details': str(e)}), 500

@ai_analysis_bp.route('/generate-image-prompt', methods=['POST'])
@token_required
def generate_image_prompt(current_user):
    """Generate optimized image prompt for content"""
    try:
        data = request.get_json()
        
        if not data.get('content'):
            return jsonify({'error': 'Content is required'}), 400
        
        if not data.get('platform'):
            return jsonify({'error': 'Platform is required'}), 400
        
        content = data['content']
        platform = data['platform']
        style = data.get('style')
        
        # Generate image prompt using AI service
        image_prompt = ai_content_service.generate_image_prompt(
            content_prompt=content,
            platform=platform,
            style=style
        )
        
        return jsonify({
            'image_prompt': image_prompt,
            'original_content': content,
            'platform': platform,
            'style': style
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Image prompt generation failed', 'details': str(e)}), 500

@ai_analysis_bp.route('/generate-image', methods=['POST'])
@token_required
def generate_image(current_user):
    """Generate image using DALL-E"""
    try:
        data = request.get_json()
        
        if not data.get('prompt'):
            return jsonify({'error': 'Prompt is required'}), 400
        
        prompt = data['prompt']
        size = data.get('size', '1024x1024')
        quality = data.get('quality', 'standard')
        
        # Generate image using AI service
        result = media_generation_service.generate_image(
            prompt=prompt,
            size=size,
            quality=quality
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': 'Image generation failed', 'details': str(e)}), 500

@ai_analysis_bp.route('/content/<content_id>/analyze', methods=['POST'])
@token_required
def analyze_generated_content(current_user, content_id):
    """Analyze specific generated content"""
    try:
        content = GeneratedContent.query.join(ContentProject).filter(
            GeneratedContent.id == content_id,
            ContentProject.user_id == current_user.id
        ).first()
        
        if not content:
            return jsonify({'error': 'Content not found'}), 404
        
        if not content.generated_text:
            return jsonify({'error': 'No text content to analyze'}), 400
        
        # Analyze content using AI service
        analysis = ai_content_service.analyze_content_quality(
            content.generated_text, 
            content.platform
        )
        
        # Update content with analysis results
        if content.generation_parameters:
            content.generation_parameters['analysis'] = analysis
        else:
            content.generation_parameters = {'analysis': analysis}
        
        # Update quality score based on analysis
        if 'overall_score' in analysis:
            content.quality_score = analysis['overall_score'] / 10.0
        
        db.session.commit()
        
        return jsonify({
            'content_id': content_id,
            'analysis': analysis,
            'updated_quality_score': content.quality_score
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Content analysis failed', 'details': str(e)}), 500

@ai_analysis_bp.route('/content/<content_id>/improve', methods=['POST'])
@token_required
def improve_content(current_user, content_id):
    """Get AI suggestions to improve content"""
    try:
        content = GeneratedContent.query.join(ContentProject).filter(
            GeneratedContent.id == content_id,
            ContentProject.user_id == current_user.id
        ).first()
        
        if not content:
            return jsonify({'error': 'Content not found'}), 404
        
        if not content.generated_text:
            return jsonify({'error': 'No text content to improve'}), 400
        
        data = request.get_json() or {}
        focus_areas = data.get('focus_areas', ['engagement', 'clarity', 'platform_optimization'])
        
        # Generate improvement suggestions
        try:
            system_prompt = f"""
            Je bent een social media expert die content verbetert voor {content.platform}.
            Geef concrete, actionable verbeterpunten.
            """
            
            user_prompt = f"""
            Verbeter deze {content.platform} content:
            "{content.generated_text}"
            
            Focus op: {', '.join(focus_areas)}
            
            Geef:
            1. Verbeterde versie van de content
            2. 3 specifieke verbeterpunten
            3. Waarom deze verbeteringen helpen
            
            Geef je antwoord in JSON format met keys: improved_content, improvements, reasoning
            """
            
            response = ai_content_service.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=800,
                temperature=0.7
            )
            
            # Try to parse JSON response
            import json
            try:
                suggestions = json.loads(response.choices[0].message.content)
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                suggestions = {
                    'improved_content': response.choices[0].message.content,
                    'improvements': ['AI response kon niet worden geparseerd'],
                    'reasoning': 'Zie improved_content voor suggesties'
                }
            
            return jsonify({
                'content_id': content_id,
                'original_content': content.generated_text,
                'suggestions': suggestions,
                'focus_areas': focus_areas
            }), 200
            
        except Exception as ai_error:
            return jsonify({
                'error': 'AI improvement failed',
                'details': str(ai_error),
                'fallback_suggestions': [
                    'Voeg meer emotie toe aan de tekst',
                    'Gebruik een duidelijkere call-to-action',
                    'Maak de content meer platform-specifiek'
                ]
            }), 500
        
    except Exception as e:
        return jsonify({'error': 'Content improvement failed', 'details': str(e)}), 500

@ai_analysis_bp.route('/tone-check', methods=['POST'])
@token_required
def check_tone(current_user):
    """Check if content matches the intended tone"""
    try:
        data = request.get_json()
        
        if not data.get('content'):
            return jsonify({'error': 'Content is required'}), 400
        
        if not data.get('intended_tone'):
            return jsonify({'error': 'Intended tone is required'}), 400
        
        content = data['content']
        intended_tone = data['intended_tone']
        platform = data.get('platform', 'general')
        
        system_prompt = f"""
        Je bent een toon-expert die analyseert of content de juiste toon heeft.
        Beoordeel of de content past bij de gewenste toon voor {platform}.
        """
        
        user_prompt = f"""
        Analyseer of deze content de juiste toon heeft:
        
        Content: "{content}"
        Gewenste toon: "{intended_tone}"
        Platform: {platform}
        
        Geef een score van 1-10 en leg uit waarom.
        Geef ook suggesties als de toon niet klopt.
        
        Antwoord in JSON format met keys: tone_match_score, explanation, suggestions
        """
        
        response = ai_content_service.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=400,
            temperature=0.3
        )
        
        # Try to parse JSON response
        import json
        try:
            tone_analysis = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            tone_analysis = {
                'tone_match_score': 7,
                'explanation': 'Toon analyse uitgevoerd maar JSON parsing gefaald',
                'suggestions': ['Controleer de toon handmatig']
            }
        
        return jsonify({
            'content': content,
            'intended_tone': intended_tone,
            'platform': platform,
            'analysis': tone_analysis
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Tone check failed', 'details': str(e)}), 500

