import os
import requests
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import quote_plus
import time
from openai import OpenAI
from src.services.database_service import database_service

class SentimentScraperService:
    """Service for scraping social media sentiment and trending topics"""
    
    def __init__(self):
        self.openai_client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')
        )
        
        # API configurations
        self.apis = {
            'twitter': {
                'bearer_token': os.getenv('TWITTER_BEARER_TOKEN'),
                'base_url': 'https://api.twitter.com/2'
            },
            'reddit': {
                'client_id': os.getenv('REDDIT_CLIENT_ID'),
                'client_secret': os.getenv('REDDIT_CLIENT_SECRET'),
                'user_agent': 'SocialMediaCreator/1.0',
                'base_url': 'https://www.reddit.com'
            },
            'youtube': {
                'api_key': os.getenv('YOUTUBE_API_KEY'),
                'base_url': 'https://www.googleapis.com/youtube/v3'
            },
            'google_trends': {
                'base_url': 'https://trends.googleapis.com/trends/api'
            }
        }
        
        # Sentiment analysis models
        self.sentiment_models = {
            'openai': 'gpt-4',
            'local': 'vader'  # Could integrate VADER or other local models
        }
        
        # Platform-specific hashtag patterns
        self.hashtag_patterns = {
            'instagram': r'#[a-zA-Z0-9_]{1,30}',
            'twitter': r'#[a-zA-Z0-9_]{1,280}',
            'linkedin': r'#[a-zA-Z0-9_]{1,100}',
            'tiktok': r'#[a-zA-Z0-9_]{1,100}',
            'facebook': r'#[a-zA-Z0-9_]{1,50}'
        }
        
        # Content categories for analysis
        self.content_categories = [
            'business', 'technology', 'lifestyle', 'food', 'travel', 'fashion',
            'fitness', 'entertainment', 'education', 'news', 'sports', 'gaming',
            'art', 'music', 'photography', 'marketing', 'startup', 'finance'
        ]
    
    def search_twitter_sentiment(self, query: str, max_results: int = 100, 
                               days_back: int = 7) -> Dict[str, Any]:
        """Search Twitter for sentiment about a topic"""
        try:
            bearer_token = self.apis['twitter']['bearer_token']
            if not bearer_token:
                return {'success': False, 'error': 'Twitter API token not configured'}
            
            # Calculate date range
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days_back)
            
            # Prepare search query
            search_query = f"{query} -is:retweet lang:en"
            
            headers = {
                'Authorization': f'Bearer {bearer_token}',
                'Content-Type': 'application/json'
            }
            
            params = {
                'query': search_query,
                'max_results': min(max_results, 100),
                'start_time': start_time.isoformat() + 'Z',
                'end_time': end_time.isoformat() + 'Z',
                'tweet.fields': 'created_at,public_metrics,context_annotations,lang',
                'user.fields': 'verified,public_metrics',
                'expansions': 'author_id'
            }
            
            url = f"{self.apis['twitter']['base_url']}/tweets/search/recent"
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f'Twitter API error: {response.status_code}',
                    'details': response.text
                }
            
            data = response.json()
            tweets = data.get('data', [])
            users = {user['id']: user for user in data.get('includes', {}).get('users', [])}
            
            # Process tweets for sentiment analysis
            processed_tweets = []
            for tweet in tweets:
                author = users.get(tweet['author_id'], {})
                processed_tweets.append({
                    'id': tweet['id'],
                    'text': tweet['text'],
                    'created_at': tweet['created_at'],
                    'metrics': tweet.get('public_metrics', {}),
                    'author': {
                        'verified': author.get('verified', False),
                        'followers': author.get('public_metrics', {}).get('followers_count', 0)
                    }
                })
            
            # Analyze sentiment
            sentiment_analysis = self.analyze_sentiment_batch(
                [tweet['text'] for tweet in processed_tweets]
            )
            
            # Extract hashtags and mentions
            hashtags = self.extract_hashtags([tweet['text'] for tweet in processed_tweets])
            
            # Calculate engagement metrics
            total_engagement = sum(
                tweet['metrics'].get('like_count', 0) + 
                tweet['metrics'].get('retweet_count', 0) + 
                tweet['metrics'].get('reply_count', 0)
                for tweet in processed_tweets
            )
            
            return {
                'success': True,
                'platform': 'twitter',
                'query': query,
                'total_tweets': len(processed_tweets),
                'date_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                },
                'sentiment_summary': sentiment_analysis['summary'],
                'tweets': processed_tweets[:20],  # Return top 20 for preview
                'hashtags': hashtags[:50],  # Top 50 hashtags
                'engagement_metrics': {
                    'total_engagement': total_engagement,
                    'average_engagement': total_engagement / len(processed_tweets) if processed_tweets else 0
                },
                'insights': self.generate_content_insights(query, sentiment_analysis, hashtags)
            }
            
        except Exception as e:
            logging.error(f"Twitter sentiment search failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def search_reddit_sentiment(self, query: str, subreddits: List[str] = None,
                              max_posts: int = 50, days_back: int = 7) -> Dict[str, Any]:
        """Search Reddit for sentiment about a topic"""
        try:
            if not subreddits:
                subreddits = ['all']
            
            all_posts = []
            
            for subreddit in subreddits:
                try:
                    # Search Reddit posts
                    url = f"{self.apis['reddit']['base_url']}/r/{subreddit}/search.json"
                    params = {
                        'q': query,
                        'sort': 'relevance',
                        'limit': max_posts // len(subreddits),
                        't': 'week' if days_back <= 7 else 'month'
                    }
                    
                    headers = {
                        'User-Agent': self.apis['reddit']['user_agent']
                    }
                    
                    response = requests.get(url, headers=headers, params=params, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        posts = data.get('data', {}).get('children', [])
                        
                        for post in posts:
                            post_data = post.get('data', {})
                            all_posts.append({
                                'id': post_data.get('id'),
                                'title': post_data.get('title', ''),
                                'text': post_data.get('selftext', ''),
                                'subreddit': post_data.get('subreddit'),
                                'score': post_data.get('score', 0),
                                'num_comments': post_data.get('num_comments', 0),
                                'created_utc': post_data.get('created_utc'),
                                'url': post_data.get('url')
                            })
                    
                    time.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    logging.warning(f"Failed to search subreddit {subreddit}: {str(e)}")
                    continue
            
            if not all_posts:
                return {'success': False, 'error': 'No Reddit posts found'}
            
            # Analyze sentiment
            texts = [f"{post['title']} {post['text']}" for post in all_posts]
            sentiment_analysis = self.analyze_sentiment_batch(texts)
            
            # Calculate metrics
            total_score = sum(post['score'] for post in all_posts)
            total_comments = sum(post['num_comments'] for post in all_posts)
            
            return {
                'success': True,
                'platform': 'reddit',
                'query': query,
                'subreddits': subreddits,
                'total_posts': len(all_posts),
                'sentiment_summary': sentiment_analysis['summary'],
                'posts': all_posts[:20],  # Top 20 for preview
                'engagement_metrics': {
                    'total_score': total_score,
                    'total_comments': total_comments,
                    'average_score': total_score / len(all_posts) if all_posts else 0
                },
                'insights': self.generate_content_insights(query, sentiment_analysis, [])
            }
            
        except Exception as e:
            logging.error(f"Reddit sentiment search failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_trending_topics(self, platform: str = 'all', category: str = None,
                          location: str = 'worldwide') -> Dict[str, Any]:
        """Get trending topics across platforms"""
        try:
            trending_data = {}
            
            # Get Twitter trends
            if platform in ['all', 'twitter'] and self.apis['twitter']['bearer_token']:
                twitter_trends = self.get_twitter_trends(location)
                if twitter_trends['success']:
                    trending_data['twitter'] = twitter_trends['trends']
            
            # Get Google Trends
            if platform in ['all', 'google']:
                google_trends = self.get_google_trends(category, location)
                if google_trends['success']:
                    trending_data['google'] = google_trends['trends']
            
            # Get Reddit trending
            if platform in ['all', 'reddit']:
                reddit_trends = self.get_reddit_trending(category)
                if reddit_trends['success']:
                    trending_data['reddit'] = reddit_trends['trends']
            
            # Combine and analyze trends
            combined_trends = self.combine_trending_topics(trending_data)
            
            return {
                'success': True,
                'platform': platform,
                'category': category,
                'location': location,
                'trending_topics': combined_trends,
                'content_opportunities': self.identify_content_opportunities(combined_trends),
                'updated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Trending topics fetch failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def analyze_sentiment_batch(self, texts: List[str]) -> Dict[str, Any]:
        """Analyze sentiment for a batch of texts using AI"""
        try:
            if not texts:
                return {'summary': {'positive': 0, 'neutral': 0, 'negative': 0}, 'details': []}
            
            # Prepare batch for analysis
            batch_text = "\n---\n".join(texts[:50])  # Limit to 50 texts to avoid token limits
            
            prompt = f"""Analyze the sentiment of the following social media posts/comments. 
            For each post (separated by ---), classify as positive, negative, or neutral.
            Also provide an overall sentiment summary and key themes.
            
            Posts:
            {batch_text}
            
            Please respond in JSON format:
            {{
                "individual_sentiments": ["positive/negative/neutral", ...],
                "overall_sentiment": "positive/negative/neutral",
                "sentiment_distribution": {{"positive": 0.0, "negative": 0.0, "neutral": 0.0}},
                "key_themes": ["theme1", "theme2", ...],
                "emotional_tone": "description",
                "confidence_score": 0.0
            }}"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert social media sentiment analyst. Provide accurate, unbiased sentiment analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            # Parse response
            try:
                analysis = json.loads(response.choices[0].message.content)
            except json.JSONDecodeError:
                # Fallback to simple analysis
                analysis = {
                    "overall_sentiment": "neutral",
                    "sentiment_distribution": {"positive": 0.33, "negative": 0.33, "neutral": 0.34},
                    "key_themes": ["general discussion"],
                    "emotional_tone": "mixed",
                    "confidence_score": 0.5
                }
            
            # Calculate summary statistics
            distribution = analysis.get('sentiment_distribution', {})
            summary = {
                'positive': int(distribution.get('positive', 0) * len(texts)),
                'negative': int(distribution.get('negative', 0) * len(texts)),
                'neutral': int(distribution.get('neutral', 0) * len(texts))
            }
            
            return {
                'summary': summary,
                'overall_sentiment': analysis.get('overall_sentiment', 'neutral'),
                'key_themes': analysis.get('key_themes', []),
                'emotional_tone': analysis.get('emotional_tone', 'mixed'),
                'confidence_score': analysis.get('confidence_score', 0.5),
                'total_analyzed': len(texts)
            }
            
        except Exception as e:
            logging.error(f"Sentiment analysis failed: {str(e)}")
            return {
                'summary': {'positive': 0, 'neutral': len(texts), 'negative': 0},
                'overall_sentiment': 'neutral',
                'error': str(e)
            }
    
    def extract_hashtags(self, texts: List[str], platform: str = 'twitter') -> List[Dict[str, Any]]:
        """Extract and count hashtags from texts"""
        try:
            pattern = self.hashtag_patterns.get(platform, r'#[a-zA-Z0-9_]+')
            hashtag_counts = {}
            
            for text in texts:
                hashtags = re.findall(pattern, text.lower())
                for hashtag in hashtags:
                    hashtag_counts[hashtag] = hashtag_counts.get(hashtag, 0) + 1
            
            # Sort by frequency
            sorted_hashtags = sorted(hashtag_counts.items(), key=lambda x: x[1], reverse=True)
            
            return [
                {
                    'hashtag': hashtag,
                    'count': count,
                    'percentage': round((count / len(texts)) * 100, 2)
                }
                for hashtag, count in sorted_hashtags
            ]
            
        except Exception as e:
            logging.error(f"Hashtag extraction failed: {str(e)}")
            return []
    
    def get_twitter_trends(self, location: str = 'worldwide') -> Dict[str, Any]:
        """Get Twitter trending topics"""
        try:
            bearer_token = self.apis['twitter']['bearer_token']
            if not bearer_token:
                return {'success': False, 'error': 'Twitter API token not configured'}
            
            # Location mapping (simplified)
            location_ids = {
                'worldwide': 1,
                'united_states': 23424977,
                'united_kingdom': 23424975,
                'canada': 23424775,
                'australia': 23424748
            }
            
            woeid = location_ids.get(location.lower(), 1)
            
            headers = {
                'Authorization': f'Bearer {bearer_token}'
            }
            
            url = f"{self.apis['twitter']['base_url']}/trends/place.json"
            params = {'id': woeid}
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                return {'success': False, 'error': f'Twitter trends API error: {response.status_code}'}
            
            data = response.json()
            trends = data[0]['trends'] if data else []
            
            processed_trends = []
            for trend in trends[:20]:  # Top 20 trends
                processed_trends.append({
                    'name': trend['name'],
                    'url': trend.get('url', ''),
                    'tweet_volume': trend.get('tweet_volume'),
                    'promoted_content': trend.get('promoted_content')
                })
            
            return {
                'success': True,
                'trends': processed_trends,
                'location': location,
                'updated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Twitter trends fetch failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_google_trends(self, category: str = None, location: str = 'worldwide') -> Dict[str, Any]:
        """Get Google trending topics (simplified implementation)"""
        try:
            # Note: This is a simplified implementation
            # In production, you might use pytrends library or Google Trends API
            
            # For now, return mock trending data
            mock_trends = [
                {'name': 'AI Technology', 'interest': 95, 'category': 'technology'},
                {'name': 'Social Media Marketing', 'interest': 87, 'category': 'business'},
                {'name': 'Sustainable Living', 'interest': 82, 'category': 'lifestyle'},
                {'name': 'Remote Work', 'interest': 78, 'category': 'business'},
                {'name': 'Digital Art', 'interest': 75, 'category': 'art'}
            ]
            
            if category:
                mock_trends = [t for t in mock_trends if t['category'] == category]
            
            return {
                'success': True,
                'trends': mock_trends,
                'category': category,
                'location': location,
                'note': 'Mock data - integrate with actual Google Trends API'
            }
            
        except Exception as e:
            logging.error(f"Google trends fetch failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_reddit_trending(self, category: str = None) -> Dict[str, Any]:
        """Get Reddit trending topics"""
        try:
            trending_subreddits = [
                'popular', 'all', 'technology', 'business', 'marketing',
                'entrepreneur', 'socialmedia', 'startups'
            ]
            
            if category:
                trending_subreddits = [category] if category in trending_subreddits else ['all']
            
            trends = []
            
            for subreddit in trending_subreddits[:3]:  # Limit to avoid rate limits
                try:
                    url = f"{self.apis['reddit']['base_url']}/r/{subreddit}/hot.json"
                    params = {'limit': 10}
                    headers = {'User-Agent': self.apis['reddit']['user_agent']}
                    
                    response = requests.get(url, headers=headers, params=params, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        posts = data.get('data', {}).get('children', [])
                        
                        for post in posts[:5]:  # Top 5 from each subreddit
                            post_data = post.get('data', {})
                            trends.append({
                                'name': post_data.get('title', ''),
                                'subreddit': post_data.get('subreddit'),
                                'score': post_data.get('score', 0),
                                'num_comments': post_data.get('num_comments', 0),
                                'url': f"https://reddit.com{post_data.get('permalink', '')}"
                            })
                    
                    time.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    logging.warning(f"Failed to get trends from r/{subreddit}: {str(e)}")
                    continue
            
            # Sort by score
            trends.sort(key=lambda x: x['score'], reverse=True)
            
            return {
                'success': True,
                'trends': trends[:20],  # Top 20
                'category': category
            }
            
        except Exception as e:
            logging.error(f"Reddit trends fetch failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def combine_trending_topics(self, trending_data: Dict[str, List]) -> List[Dict[str, Any]]:
        """Combine trending topics from multiple platforms"""
        try:
            combined = []
            
            for platform, trends in trending_data.items():
                for trend in trends:
                    combined.append({
                        'topic': trend.get('name', trend.get('title', '')),
                        'platform': platform,
                        'metrics': {
                            'score': trend.get('score', trend.get('interest', trend.get('tweet_volume', 0))),
                            'engagement': trend.get('num_comments', trend.get('engagement', 0))
                        },
                        'url': trend.get('url', ''),
                        'category': trend.get('category', 'general')
                    })
            
            # Remove duplicates and sort by relevance
            seen_topics = set()
            unique_trends = []
            
            for trend in combined:
                topic_key = trend['topic'].lower().strip()
                if topic_key not in seen_topics and len(topic_key) > 3:
                    seen_topics.add(topic_key)
                    unique_trends.append(trend)
            
            # Sort by combined score
            unique_trends.sort(key=lambda x: x['metrics']['score'], reverse=True)
            
            return unique_trends[:50]  # Top 50 combined trends
            
        except Exception as e:
            logging.error(f"Trend combination failed: {str(e)}")
            return []
    
    def identify_content_opportunities(self, trends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify content creation opportunities from trends"""
        try:
            opportunities = []
            
            for trend in trends[:20]:  # Analyze top 20 trends
                topic = trend['topic']
                
                # Generate content ideas using AI
                prompt = f"""Based on the trending topic "{topic}", suggest 3 creative social media content ideas that would be engaging and relevant. 
                
                For each idea, provide:
                1. Content type (post, story, reel, etc.)
                2. Platform recommendation
                3. Brief description
                4. Suggested tone/style
                5. Potential hashtags
                
                Format as JSON array."""
                
                try:
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "You are a creative social media strategist. Generate engaging, trend-aware content ideas."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.8,
                        max_tokens=800
                    )
                    
                    content_ideas = json.loads(response.choices[0].message.content)
                    
                    opportunities.append({
                        'trending_topic': topic,
                        'platform_source': trend['platform'],
                        'trend_score': trend['metrics']['score'],
                        'content_ideas': content_ideas,
                        'opportunity_score': self.calculate_opportunity_score(trend),
                        'best_platforms': self.recommend_platforms_for_topic(topic)
                    })
                    
                except Exception as e:
                    logging.warning(f"Failed to generate content ideas for {topic}: {str(e)}")
                    continue
            
            # Sort by opportunity score
            opportunities.sort(key=lambda x: x['opportunity_score'], reverse=True)
            
            return opportunities
            
        except Exception as e:
            logging.error(f"Content opportunity identification failed: {str(e)}")
            return []
    
    def calculate_opportunity_score(self, trend: Dict[str, Any]) -> float:
        """Calculate content opportunity score for a trend"""
        try:
            base_score = trend['metrics']['score']
            engagement = trend['metrics'].get('engagement', 0)
            
            # Normalize scores (simplified scoring algorithm)
            score = (base_score * 0.7) + (engagement * 0.3)
            
            # Boost score for certain categories
            category = trend.get('category', 'general')
            category_multipliers = {
                'technology': 1.2,
                'business': 1.1,
                'lifestyle': 1.0,
                'entertainment': 0.9,
                'general': 0.8
            }
            
            score *= category_multipliers.get(category, 1.0)
            
            return min(score / 1000, 10.0)  # Normalize to 0-10 scale
            
        except Exception as e:
            logging.error(f"Opportunity score calculation failed: {str(e)}")
            return 5.0  # Default score
    
    def recommend_platforms_for_topic(self, topic: str) -> List[str]:
        """Recommend best platforms for a topic"""
        try:
            # Simple keyword-based platform recommendation
            topic_lower = topic.lower()
            
            platform_keywords = {
                'linkedin': ['business', 'professional', 'career', 'industry', 'b2b', 'corporate'],
                'instagram': ['visual', 'lifestyle', 'fashion', 'food', 'travel', 'art', 'photography'],
                'tiktok': ['trending', 'viral', 'entertainment', 'music', 'dance', 'comedy', 'young'],
                'twitter': ['news', 'politics', 'tech', 'breaking', 'discussion', 'opinion'],
                'facebook': ['community', 'family', 'local', 'events', 'groups', 'sharing']
            }
            
            recommended = []
            for platform, keywords in platform_keywords.items():
                if any(keyword in topic_lower for keyword in keywords):
                    recommended.append(platform)
            
            # Default recommendations if no matches
            if not recommended:
                recommended = ['instagram', 'twitter', 'linkedin']
            
            return recommended[:3]  # Top 3 recommendations
            
        except Exception as e:
            logging.error(f"Platform recommendation failed: {str(e)}")
            return ['instagram', 'twitter', 'linkedin']
    
    def generate_content_insights(self, query: str, sentiment_analysis: Dict[str, Any], 
                                hashtags: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate actionable content insights"""
        try:
            insights = {
                'sentiment_insights': [],
                'hashtag_recommendations': [],
                'content_strategy': {},
                'timing_recommendations': {},
                'engagement_predictions': {}
            }
            
            # Sentiment insights
            overall_sentiment = sentiment_analysis.get('overall_sentiment', 'neutral')
            if overall_sentiment == 'positive':
                insights['sentiment_insights'].append("Positive sentiment detected - great opportunity for promotional content")
            elif overall_sentiment == 'negative':
                insights['sentiment_insights'].append("Negative sentiment detected - consider addressing concerns or providing solutions")
            else:
                insights['sentiment_insights'].append("Neutral sentiment - opportunity to create engaging, informative content")
            
            # Hashtag recommendations
            top_hashtags = hashtags[:10]
            insights['hashtag_recommendations'] = [h['hashtag'] for h in top_hashtags]
            
            # Content strategy based on themes
            key_themes = sentiment_analysis.get('key_themes', [])
            insights['content_strategy'] = {
                'primary_themes': key_themes[:3],
                'recommended_tone': self.get_recommended_tone(overall_sentiment),
                'content_types': self.get_recommended_content_types(key_themes)
            }
            
            return insights
            
        except Exception as e:
            logging.error(f"Content insights generation failed: {str(e)}")
            return {}
    
    def get_recommended_tone(self, sentiment: str) -> str:
        """Get recommended tone based on sentiment"""
        tone_map = {
            'positive': 'enthusiastic and engaging',
            'negative': 'empathetic and solution-focused',
            'neutral': 'informative and balanced'
        }
        return tone_map.get(sentiment, 'professional and friendly')
    
    def get_recommended_content_types(self, themes: List[str]) -> List[str]:
        """Get recommended content types based on themes"""
        content_types = ['educational posts', 'behind-the-scenes content', 'user-generated content']
        
        # Add theme-specific content types
        for theme in themes:
            if 'technology' in theme.lower():
                content_types.append('tech tutorials')
            elif 'business' in theme.lower():
                content_types.append('industry insights')
            elif 'lifestyle' in theme.lower():
                content_types.append('lifestyle tips')
        
        return list(set(content_types))[:5]  # Return unique types, max 5


# Service instance
sentiment_scraper_service = SentimentScraperService()

