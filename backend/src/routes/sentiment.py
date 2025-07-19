from flask import Blueprint, jsonify, request
from src.routes.auth import token_required
from src.services.sentiment_scraper_service import sentiment_scraper_service
from src.services.security_service import security_service
from src.services.database_service import database_service
import logging

sentiment_bp = Blueprint('sentiment', __name__)

@sentiment_bp.route('/sentiment/analyze/twitter', methods=['POST'])
@token_required
@security_service.rate_limit_decorator('api_general')
def analyze_twitter_sentiment(current_user):
    """Analyze Twitter sentiment for a topic"""
    try:
        data = request.get_json()
        
        # Validate input
        validation_rules = {
            'query': 'required|safe_text'
        }
        
        is_valid, errors = security_service.validate_input(data, validation_rules)
        if not is_valid:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Sanitize inputs
        query = security_service.sanitize_text(data['query'], max_length=200)
        max_results = min(int(data.get('max_results', 100)), 500)  # Max 500 tweets
        days_back = min(int(data.get('days_back', 7)), 30)  # Max 30 days
        
        # Check cache first
        cache_key = f"twitter_sentiment:{query}:{max_results}:{days_back}"
        cached_result = database_service.cache_get(cache_key)
        
        if cached_result:
            return jsonify({
                'message': 'Twitter sentiment analysis (cached)',
                'result': cached_result,
                'cached': True
            }), 200
        
        # Perform sentiment analysis
        result = sentiment_scraper_service.search_twitter_sentiment(
            query=query,
            max_results=max_results,
            days_back=days_back
        )
        
        if result['success']:
            # Cache result for 30 minutes
            database_service.cache_set(cache_key, result, 1800)
            
            return jsonify({
                'message': 'Twitter sentiment analysis completed',
                'result': result
            }), 200
        else:
            return jsonify({
                'error': result.get('error', 'Twitter sentiment analysis failed'),
                'details': result.get('details', '')
            }), 500
            
    except Exception as e:
        logging.error(f"Twitter sentiment analysis failed: {str(e)}")
        return jsonify({'error': 'Failed to analyze Twitter sentiment'}), 500

@sentiment_bp.route('/sentiment/analyze/reddit', methods=['POST'])
@token_required
@security_service.rate_limit_decorator('api_general')
def analyze_reddit_sentiment(current_user):
    """Analyze Reddit sentiment for a topic"""
    try:
        data = request.get_json()
        
        # Validate input
        validation_rules = {
            'query': 'required|safe_text'
        }
        
        is_valid, errors = security_service.validate_input(data, validation_rules)
        if not is_valid:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        # Sanitize inputs
        query = security_service.sanitize_text(data['query'], max_length=200)
        subreddits = data.get('subreddits', [])
        max_posts = min(int(data.get('max_posts', 50)), 200)  # Max 200 posts
        days_back = min(int(data.get('days_back', 7)), 30)  # Max 30 days
        
        # Validate subreddits
        if subreddits:
            subreddits = [security_service.sanitize_text(sub, max_length=50) for sub in subreddits[:10]]
        
        # Check cache first
        cache_key = f"reddit_sentiment:{query}:{':'.join(subreddits)}:{max_posts}:{days_back}"
        cached_result = database_service.cache_get(cache_key)
        
        if cached_result:
            return jsonify({
                'message': 'Reddit sentiment analysis (cached)',
                'result': cached_result,
                'cached': True
            }), 200
        
        # Perform sentiment analysis
        result = sentiment_scraper_service.search_reddit_sentiment(
            query=query,
            subreddits=subreddits if subreddits else None,
            max_posts=max_posts,
            days_back=days_back
        )
        
        if result['success']:
            # Cache result for 30 minutes
            database_service.cache_set(cache_key, result, 1800)
            
            return jsonify({
                'message': 'Reddit sentiment analysis completed',
                'result': result
            }), 200
        else:
            return jsonify({
                'error': result.get('error', 'Reddit sentiment analysis failed')
            }), 500
            
    except Exception as e:
        logging.error(f"Reddit sentiment analysis failed: {str(e)}")
        return jsonify({'error': 'Failed to analyze Reddit sentiment'}), 500

@sentiment_bp.route('/sentiment/trending-topics', methods=['GET'])
@token_required
@security_service.rate_limit_decorator('api_general')
def get_trending_topics(current_user):
    """Get trending topics across platforms"""
    try:
        platform = request.args.get('platform', 'all')
        category = request.args.get('category')
        location = request.args.get('location', 'worldwide')
        
        # Validate inputs
        allowed_platforms = ['all', 'twitter', 'reddit', 'google']
        if platform not in allowed_platforms:
            return jsonify({'error': f'Platform must be one of: {", ".join(allowed_platforms)}'}), 400
        
        if category:
            category = security_service.sanitize_text(category, max_length=50)
        
        location = security_service.sanitize_text(location, max_length=50)
        
        # Check cache first
        cache_key = f"trending_topics:{platform}:{category}:{location}"
        cached_result = database_service.cache_get(cache_key)
        
        if cached_result:
            return jsonify({
                'message': 'Trending topics (cached)',
                'result': cached_result,
                'cached': True
            }), 200
        
        # Get trending topics
        result = sentiment_scraper_service.get_trending_topics(
            platform=platform,
            category=category,
            location=location
        )
        
        if result['success']:
            # Cache result for 15 minutes (trends change quickly)
            database_service.cache_set(cache_key, result, 900)
            
            return jsonify({
                'message': 'Trending topics retrieved successfully',
                'result': result
            }), 200
        else:
            return jsonify({
                'error': result.get('error', 'Failed to get trending topics')
            }), 500
            
    except Exception as e:
        logging.error(f"Trending topics fetch failed: {str(e)}")
        return jsonify({'error': 'Failed to get trending topics'}), 500

@sentiment_bp.route('/sentiment/content-opportunities', methods=['POST'])
@token_required
@security_service.rate_limit_decorator('api_general')
def get_content_opportunities(current_user):
    """Get content creation opportunities based on trends and sentiment"""
    try:
        data = request.get_json()
        
        # Validate input
        validation_rules = {
            'topic': 'required|safe_text'
        }
        
        is_valid, errors = security_service.validate_input(data, validation_rules)
        if not is_valid:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        topic = security_service.sanitize_text(data['topic'], max_length=200)
        platforms = data.get('platforms', ['all'])
        include_sentiment = data.get('include_sentiment', True)
        
        # Check cache first
        cache_key = f"content_opportunities:{topic}:{':'.join(platforms)}:{include_sentiment}"
        cached_result = database_service.cache_get(cache_key)
        
        if cached_result:
            return jsonify({
                'message': 'Content opportunities (cached)',
                'result': cached_result,
                'cached': True
            }), 200
        
        opportunities = []
        
        # Get trending topics first
        for platform in platforms:
            if platform == 'all':
                platform = 'all'
            
            trending_result = sentiment_scraper_service.get_trending_topics(platform=platform)
            
            if trending_result['success']:
                # Filter trends related to the topic
                related_trends = []
                for trend in trending_result['trending_topics']:
                    if topic.lower() in trend['topic'].lower():
                        related_trends.append(trend)
                
                if related_trends:
                    # Generate content opportunities
                    content_opps = sentiment_scraper_service.identify_content_opportunities(related_trends)
                    opportunities.extend(content_opps)
        
        # Get sentiment analysis if requested
        sentiment_data = None
        if include_sentiment:
            # Try Twitter first, then Reddit
            twitter_sentiment = sentiment_scraper_service.search_twitter_sentiment(topic, max_results=50)
            if twitter_sentiment['success']:
                sentiment_data = twitter_sentiment
            else:
                reddit_sentiment = sentiment_scraper_service.search_reddit_sentiment(topic, max_posts=30)
                if reddit_sentiment['success']:
                    sentiment_data = reddit_sentiment
        
        result = {
            'topic': topic,
            'platforms_analyzed': platforms,
            'content_opportunities': opportunities[:20],  # Top 20 opportunities
            'sentiment_analysis': sentiment_data,
            'total_opportunities': len(opportunities),
            'generated_at': sentiment_scraper_service.database_service.cache_get('current_time') or 'unknown'
        }
        
        # Cache result for 20 minutes
        database_service.cache_set(cache_key, result, 1200)
        
        return jsonify({
            'message': 'Content opportunities generated successfully',
            'result': result
        }), 200
        
    except Exception as e:
        logging.error(f"Content opportunities generation failed: {str(e)}")
        return jsonify({'error': 'Failed to generate content opportunities'}), 500

@sentiment_bp.route('/sentiment/hashtag-analysis', methods=['POST'])
@token_required
@security_service.rate_limit_decorator('api_general')
def analyze_hashtags(current_user):
    """Analyze hashtag performance and trends"""
    try:
        data = request.get_json()
        
        # Validate input
        validation_rules = {
            'hashtags': 'required'
        }
        
        is_valid, errors = security_service.validate_input(data, validation_rules)
        if not is_valid:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        hashtags = data['hashtags']
        platform = data.get('platform', 'twitter')
        
        if not isinstance(hashtags, list) or len(hashtags) == 0:
            return jsonify({'error': 'Hashtags must be a non-empty list'}), 400
        
        # Sanitize hashtags
        hashtags = [security_service.sanitize_text(tag, max_length=100) for tag in hashtags[:20]]
        
        hashtag_analysis = []
        
        for hashtag in hashtags:
            # Remove # if present
            clean_hashtag = hashtag.lstrip('#')
            
            # Analyze each hashtag
            if platform == 'twitter':
                analysis = sentiment_scraper_service.search_twitter_sentiment(
                    query=f"#{clean_hashtag}",
                    max_results=50,
                    days_back=7
                )
            else:
                analysis = sentiment_scraper_service.search_reddit_sentiment(
                    query=clean_hashtag,
                    max_posts=30,
                    days_back=7
                )
            
            if analysis['success']:
                hashtag_analysis.append({
                    'hashtag': f"#{clean_hashtag}",
                    'platform': platform,
                    'sentiment': analysis.get('sentiment_summary', {}),
                    'engagement_metrics': analysis.get('engagement_metrics', {}),
                    'total_mentions': analysis.get('total_tweets', analysis.get('total_posts', 0)),
                    'insights': analysis.get('insights', {})
                })
        
        return jsonify({
            'message': 'Hashtag analysis completed',
            'hashtag_analysis': hashtag_analysis,
            'platform': platform,
            'total_analyzed': len(hashtag_analysis)
        }), 200
        
    except Exception as e:
        logging.error(f"Hashtag analysis failed: {str(e)}")
        return jsonify({'error': 'Failed to analyze hashtags'}), 500

@sentiment_bp.route('/sentiment/competitor-analysis', methods=['POST'])
@token_required
@security_service.rate_limit_decorator('api_general')
def analyze_competitors(current_user):
    """Analyze competitor content and sentiment"""
    try:
        data = request.get_json()
        
        # Validate input
        validation_rules = {
            'competitors': 'required',
            'industry': 'required|safe_text'
        }
        
        is_valid, errors = security_service.validate_input(data, validation_rules)
        if not is_valid:
            return jsonify({'error': 'Validation failed', 'details': errors}), 400
        
        competitors = data['competitors']
        industry = security_service.sanitize_text(data['industry'], max_length=100)
        platforms = data.get('platforms', ['twitter'])
        
        if not isinstance(competitors, list) or len(competitors) == 0:
            return jsonify({'error': 'Competitors must be a non-empty list'}), 400
        
        # Sanitize competitor names
        competitors = [security_service.sanitize_text(comp, max_length=100) for comp in competitors[:10]]
        
        competitor_analysis = []
        
        for competitor in competitors:
            comp_data = {
                'competitor': competitor,
                'platforms': {},
                'overall_sentiment': 'neutral',
                'content_themes': [],
                'engagement_metrics': {}
            }
            
            for platform in platforms:
                if platform == 'twitter':
                    analysis = sentiment_scraper_service.search_twitter_sentiment(
                        query=competitor,
                        max_results=100,
                        days_back=14
                    )
                elif platform == 'reddit':
                    analysis = sentiment_scraper_service.search_reddit_sentiment(
                        query=competitor,
                        max_posts=50,
                        days_back=14
                    )
                else:
                    continue
                
                if analysis['success']:
                    comp_data['platforms'][platform] = {
                        'sentiment_summary': analysis.get('sentiment_summary', {}),
                        'engagement_metrics': analysis.get('engagement_metrics', {}),
                        'key_themes': analysis.get('insights', {}).get('content_strategy', {}).get('primary_themes', [])
                    }
            
            competitor_analysis.append(comp_data)
        
        # Generate competitive insights
        competitive_insights = {
            'industry_sentiment_overview': 'neutral',  # Would be calculated from all competitors
            'common_themes': [],  # Would extract common themes across competitors
            'content_gaps': [],  # Would identify opportunities
            'recommended_strategy': 'Focus on unique value proposition and authentic engagement'
        }
        
        return jsonify({
            'message': 'Competitor analysis completed',
            'industry': industry,
            'competitor_analysis': competitor_analysis,
            'competitive_insights': competitive_insights,
            'platforms_analyzed': platforms
        }), 200
        
    except Exception as e:
        logging.error(f"Competitor analysis failed: {str(e)}")
        return jsonify({'error': 'Failed to analyze competitors'}), 500

@sentiment_bp.route('/sentiment/platforms', methods=['GET'])
def get_supported_platforms():
    """Get list of supported platforms for sentiment analysis"""
    try:
        platforms = {
            'twitter': {
                'name': 'Twitter/X',
                'capabilities': ['sentiment_analysis', 'trending_topics', 'hashtag_analysis'],
                'rate_limits': '100 requests per hour',
                'data_freshness': 'Real-time'
            },
            'reddit': {
                'name': 'Reddit',
                'capabilities': ['sentiment_analysis', 'trending_topics', 'community_analysis'],
                'rate_limits': '60 requests per hour',
                'data_freshness': 'Near real-time'
            },
            'google_trends': {
                'name': 'Google Trends',
                'capabilities': ['trending_topics', 'search_volume'],
                'rate_limits': 'Unlimited',
                'data_freshness': 'Daily updates'
            }
        }
        
        return jsonify({
            'supported_platforms': platforms,
            'total_platforms': len(platforms)
        }), 200
        
    except Exception as e:
        logging.error(f"Failed to get supported platforms: {str(e)}")
        return jsonify({'error': 'Failed to get supported platforms'}), 500

