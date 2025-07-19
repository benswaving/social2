import os
import json
import requests
import openai
from typing import Dict, List, Optional, Any
from datetime import datetime

class AIContentService:
    """Service for AI-powered content generation"""
    
    def __init__(self):
        # OpenAI configuration
        self.openai_client = openai.OpenAI(
            api_key=os.environ.get('OPENAI_API_KEY'),
            base_url=os.environ.get('OPENAI_API_BASE', 'https://api.openai.com/v1')
        )
        
        # Platform-specific configurations
        self.platform_configs = {
            'instagram': {
                'max_length': 2200,
                'tone_prompts': {
                    'creatief': 'Gebruik een creatieve, visuele en inspirerende toon met emoji en hashtags',
                    'visueel': 'Focus op visuele elementen en beschrijvingen, gebruik emoji',
                    'inspirerend': 'Schrijf inspirerend en motiverend, gebruik positieve taal',
                    'lifestyle': 'Gebruik een lifestyle-gerichte, persoonlijke toon'
                },
                'hashtag_count': 15
            },
            'linkedin': {
                'max_length': 3000,
                'tone_prompts': {
                    'zakelijk': 'Gebruik een professionele, zakelijke toon',
                    'professioneel': 'Schrijf formeel en professioneel',
                    'inhoudelijk': 'Focus op waardevolle, informatieve content',
                    'thought-leadership': 'Toon expertise en leiderschap in het vakgebied'
                },
                'hashtag_count': 3
            },
            'twitter': {
                'max_length': 280,
                'tone_prompts': {
                    'direct': 'Wees direct en to-the-point',
                    'kort': 'Houd het kort en krachtig',
                    'prikkelend': 'Gebruik een prikkelende, engaging toon',
                    'conversationeel': 'Schrijf alsof je een gesprek voert'
                },
                'hashtag_count': 3
            },
            'facebook': {
                'max_length': 63206,
                'tone_prompts': {
                    'vriendelijk': 'Gebruik een vriendelijke, toegankelijke toon',
                    'gemeenschapsgericht': 'Focus op community en verbinding',
                    'verhalen': 'Vertel verhalen en gebruik storytelling',
                    'persoonlijk': 'Maak het persoonlijk en relateerbaar'
                },
                'hashtag_count': 5
            },
            'tiktok': {
                'max_length': 150,
                'tone_prompts': {
                    'informeel': 'Gebruik informele, casual taal',
                    'speels': 'Wees speels en energiek',
                    'trending': 'Gebruik trending taal en referenties',
                    'energiek': 'Schrijf met veel energie en enthousiasme'
                },
                'hashtag_count': 8
            }
        }
    
    def generate_text_content(self, prompt: str, platform: str, tone: str = None, 
                            brand_guidelines: str = None) -> Dict[str, Any]:
        """Generate text content for a specific platform"""
        try:
            platform_config = self.platform_configs.get(platform, {})
            max_length = platform_config.get('max_length', 1000)
            
            # Build system prompt
            system_prompt = self._build_system_prompt(platform, tone, brand_guidelines)
            
            # Build user prompt
            user_prompt = f"""
            Genereer social media content voor {platform} over het volgende onderwerp:
            {prompt}
            
            Vereisten:
            - Maximaal {max_length} karakters
            - Platform: {platform}
            - Toon: {tone or 'neutraal'}
            - Voeg relevante hashtags toe
            - Maak het engaging en platform-specifiek
            """
            
            # Generate content with OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            generated_text = response.choices[0].message.content
            
            # Extract hashtags
            hashtags = self._extract_hashtags(generated_text)
            
            # Clean text (remove hashtags from main text)
            clean_text = self._clean_text(generated_text)
            
            return {
                'text': clean_text,
                'hashtags': ' '.join(hashtags),
                'character_count': len(clean_text),
                'platform': platform,
                'tone': tone,
                'model_used': 'gpt-4.1-mini',
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Failed to generate text content: {str(e)}")
    
    def generate_image_prompt(self, content_prompt: str, platform: str, 
                            style: str = None) -> str:
        """Generate an optimized image prompt for DALL-E"""
        try:
            platform_styles = {
                'instagram': 'high-quality, aesthetic, Instagram-worthy, vibrant colors',
                'linkedin': 'professional, clean, business-appropriate, modern',
                'twitter': 'eye-catching, simple, clear message',
                'facebook': 'engaging, community-focused, relatable',
                'tiktok': 'trendy, dynamic, youth-oriented, colorful'
            }
            
            base_style = platform_styles.get(platform, 'high-quality, professional')
            
            system_prompt = f"""
            Je bent een expert in het maken van prompts voor AI image generatie.
            Maak een gedetailleerde prompt voor DALL-E gebaseerd op de content.
            
            Platform: {platform}
            Basis stijl: {base_style}
            Extra stijl: {style or 'geen specifieke stijl'}
            """
            
            user_prompt = f"""
            Maak een DALL-E prompt voor een afbeelding die past bij deze content:
            {content_prompt}
            
            De prompt moet:
            - Specifiek en gedetailleerd zijn
            - Geschikt zijn voor {platform}
            - Visueel aantrekkelijk zijn
            - Professioneel overkomen
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=200,
                temperature=0.8
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"Failed to generate image prompt: {str(e)}")
    
    def analyze_content_quality(self, content: str, platform: str) -> Dict[str, Any]:
        """Analyze content quality and provide suggestions"""
        try:
            platform_config = self.platform_configs.get(platform, {})
            max_length = platform_config.get('max_length', 1000)
            
            system_prompt = f"""
            Je bent een social media expert die content analyseert voor {platform}.
            Geef een score van 1-10 en concrete verbeterpunten.
            """
            
            user_prompt = f"""
            Analyseer deze {platform} content:
            "{content}"
            
            Geef feedback op:
            - Engagement potentieel (1-10)
            - Platform geschiktheid (1-10)
            - Toon en stijl (1-10)
            - Lengte ({len(content)}/{max_length} karakters)
            - Verbeterpunten (max 3)
            
            Geef je antwoord in JSON format.
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            # Parse JSON response
            try:
                analysis = json.loads(response.choices[0].message.content)
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                analysis = {
                    'engagement_score': 7,
                    'platform_score': 8,
                    'tone_score': 7,
                    'overall_score': 7.3,
                    'suggestions': ['Content geanalyseerd maar JSON parsing gefaald']
                }
            
            return analysis
            
        except Exception as e:
            return {
                'engagement_score': 5,
                'platform_score': 5,
                'tone_score': 5,
                'overall_score': 5.0,
                'suggestions': [f'Analyse gefaald: {str(e)}']
            }
    
    def generate_hashtags(self, content: str, platform: str, count: int = None) -> List[str]:
        """Generate relevant hashtags for content"""
        try:
            platform_config = self.platform_configs.get(platform, {})
            default_count = platform_config.get('hashtag_count', 5)
            hashtag_count = count or default_count
            
            system_prompt = f"""
            Genereer relevante hashtags voor {platform} content.
            Gebruik populaire en niche hashtags die engagement verhogen.
            """
            
            user_prompt = f"""
            Genereer {hashtag_count} hashtags voor deze content:
            "{content}"
            
            Platform: {platform}
            
            Geef alleen de hashtags terug, gescheiden door spaties, beginnend met #
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=100,
                temperature=0.6
            )
            
            hashtags_text = response.choices[0].message.content.strip()
            hashtags = [tag.strip() for tag in hashtags_text.split() if tag.startswith('#')]
            
            return hashtags[:hashtag_count]
            
        except Exception as e:
            # Fallback hashtags
            return [f'#{platform}', '#ai', '#content', '#socialmedia']
    
    def _build_system_prompt(self, platform: str, tone: str, brand_guidelines: str) -> str:
        """Build system prompt for content generation"""
        platform_config = self.platform_configs.get(platform, {})
        tone_prompt = platform_config.get('tone_prompts', {}).get(tone, '')
        
        system_prompt = f"""
        Je bent een expert social media content creator gespecialiseerd in {platform}.
        
        Platform specifieke richtlijnen:
        - Maximale lengte: {platform_config.get('max_length', 1000)} karakters
        - Gebruik maximaal {platform_config.get('hashtag_count', 5)} hashtags
        
        Toon en stijl:
        {tone_prompt}
        """
        
        if brand_guidelines:
            system_prompt += f"\n\nMerk richtlijnen:\n{brand_guidelines}"
        
        system_prompt += """
        
        Algemene richtlijnen:
        - Schrijf in het Nederlands
        - Maak content engaging en actionable
        - Gebruik een natuurlijke, menselijke toon
        - Voeg relevante hashtags toe aan het einde
        - Zorg dat de content platform-specifiek is
        """
        
        return system_prompt
    
    def _extract_hashtags(self, text: str) -> List[str]:
        """Extract hashtags from generated text"""
        import re
        hashtags = re.findall(r'#\w+', text)
        return hashtags
    
    def _clean_text(self, text: str) -> str:
        """Remove hashtags from main text"""
        import re
        # Remove hashtags that are at the end of the text
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # If line consists mostly of hashtags, skip it
            hashtag_count = len(re.findall(r'#\w+', line))
            word_count = len(line.split())
            
            if hashtag_count > 0 and hashtag_count / max(word_count, 1) > 0.5:
                continue
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()


class MediaGenerationService:
    """Service for AI-powered media generation"""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(
            api_key=os.environ.get('OPENAI_API_KEY'),
            base_url=os.environ.get('OPENAI_API_BASE', 'https://api.openai.com/v1')
        )
    
    def generate_image(self, prompt: str, size: str = "1024x1024", 
                      quality: str = "standard") -> Dict[str, Any]:
        """Generate image using DALL-E"""
        try:
            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                n=1
            )
            
            image_url = response.data[0].url
            revised_prompt = response.data[0].revised_prompt
            
            return {
                'image_url': image_url,
                'revised_prompt': revised_prompt,
                'original_prompt': prompt,
                'size': size,
                'quality': quality,
                'model_used': 'dall-e-3',
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Failed to generate image: {str(e)}")
    
    def download_and_save_image(self, image_url: str, filename: str, 
                               storage_path: str = "/tmp") -> str:
        """Download and save generated image"""
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            
            file_path = os.path.join(storage_path, filename)
            
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            return file_path
            
        except Exception as e:
            raise Exception(f"Failed to download image: {str(e)}")


# Service instances
ai_content_service = AIContentService()
media_generation_service = MediaGenerationService()

