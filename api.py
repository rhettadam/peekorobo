from flask import jsonify, request, abort
from functools import wraps
import os
import requests
import random
from datetime import datetime
from datagather import load_year_data, get_team_avatar
from utils import DatabaseConnection

# Import your global data (will be set from peekorobo.py)
TEAM_DATABASE = None
EVENT_DATABASE = None
EVENT_TEAMS = None
EVENT_RANKINGS = None
EVENT_AWARDS = None
EVENT_MATCHES = None

def init_api_data(team_db, event_db, event_teams, event_rankings, event_awards, event_matches):
    """Initialize the API with the global data from peekorobo.py"""
    global TEAM_DATABASE, EVENT_DATABASE, EVENT_TEAMS, EVENT_RANKINGS, EVENT_AWARDS, EVENT_MATCHES
    TEAM_DATABASE = team_db
    EVENT_DATABASE = event_db
    EVENT_TEAMS = event_teams
    EVENT_RANKINGS = event_rankings
    EVENT_AWARDS = event_awards
    EVENT_MATCHES = event_matches

def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        
        # For now, we'll use a simple API key check
        # You can enhance this with database lookup later
        valid_keys = os.environ.get("API_KEYS", "").split(",")
        valid_keys = [k.strip() for k in valid_keys if k.strip()]
        
        if not valid_keys or api_key not in valid_keys:
            return jsonify({'error': 'Invalid API key'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

def rate_limit(f):
    """Simple rate limiting decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # For now, we'll implement basic rate limiting
        # You can enhance this with Redis or database tracking
        return f(*args, **kwargs)
    return decorated_function

# API Routes

def register_api_routes(app):
    """Register all API routes with the Flask app"""
    
    # ===== TEAMS ENDPOINTS =====
    
    @app.route('/api/v1/teams')
    @require_api_key
    @rate_limit
    def get_teams_page():
        """Get paginated teams with optional filtering"""
        # Get query parameters
        year = request.args.get('year', '2025')
        district = request.args.get('district')
        state = request.args.get('state')
        country = request.args.get('country')
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(int(request.args.get('per_page', 50)), 100)  # Max 100 per page
        offset = (page - 1) * per_page
        
        try:
            year = int(year)
        except ValueError:
            return jsonify({'error': 'Invalid year'}), 400
        
        # Get teams for the specified year
        if year == 2025:
            teams_data = TEAM_DATABASE.get(2025, {})
        else:
            try:
                year_team_data, _, _, _, _, _ = load_year_data(year)
                teams_data = year_team_data
            except Exception as e:
                return jsonify({'error': f'Data not available for year {year}'}), 404
        
        # Filter teams
        filtered_teams = []
        for team_num, team_data in teams_data.items():
            if district and team_data.get('district') != district:
                continue
            if state and team_data.get('state_prov') != state:
                continue
            if country and team_data.get('country') != country:
                continue
            
            filtered_teams.append({
                'team_number': team_num,
                'nickname': team_data.get('nickname', 'Unknown'),
                'city': team_data.get('city', ''),
                'state_prov': team_data.get('state_prov', ''),
                'country': team_data.get('country', ''),
                'epa': team_data.get('epa', 0),
                'district': team_data.get('district', '')
            })
        
        # Sort by team number
        filtered_teams.sort(key=lambda x: x['team_number'])
        
        # Paginate
        total_count = len(filtered_teams)
        paginated_teams = filtered_teams[offset:offset + per_page]
        
        return jsonify({
            'teams': paginated_teams,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': (total_count + per_page - 1) // per_page,
                'has_next': offset + per_page < total_count,
                'has_prev': page > 1
            },
            'year': year,
            'last_updated': datetime.now().isoformat()
        })
    
    @app.route('/api/v1/team/<team_key>')
    @require_api_key
    @rate_limit
    def get_team(team_key):
        """Get team information by team key"""
        try:
            team_number = int(team_key)
        except ValueError:
            return jsonify({'error': 'Invalid team key'}), 400
        
        # Get team data from 2025 database
        team_data = TEAM_DATABASE.get(2025, {}).get(team_number)
        
        if not team_data:
            return jsonify({'error': 'Team not found'}), 404
        
        # Get team avatar
        avatar_url = get_team_avatar(team_number, 2025)
        
        response = {
            'team_number': team_number,
            'nickname': team_data.get('nickname', 'Unknown'),
            'city': team_data.get('city', ''),
            'state_prov': team_data.get('state_prov', ''),
            'country': team_data.get('country', ''),
            'epa': team_data.get('epa', 0),
            'auto_epa': team_data.get('auto_epa', 0),
            'teleop_epa': team_data.get('teleop_epa', 0),
            'endgame_epa': team_data.get('endgame_epa', 0),
            'confidence': team_data.get('confidence', 0),
            'avatar_url': avatar_url,
            'last_updated': datetime.now().isoformat()
        }
        
        return jsonify(response)
    
    @app.route('/api/v1/team/<team_key>/matches')
    @require_api_key
    @rate_limit
    def get_team_matches(team_key):
        """Get all matches for a team"""
        try:
            team_number = int(team_key)
        except ValueError:
            return jsonify({'error': 'Invalid team key'}), 400
        
        # Get all matches and filter by team
        all_matches = EVENT_MATCHES.get(2025, [])
        team_matches = []
        
        for match in all_matches:
            if isinstance(match, dict):
                red_teams_str = match.get('rt', '')
                blue_teams_str = match.get('bt', '')
                
                red_teams = []
                blue_teams = []
                
                if red_teams_str:
                    red_teams = [int(t) for t in red_teams_str.split(',') if t.strip().isdigit()]
                if blue_teams_str:
                    blue_teams = [int(t) for t in blue_teams_str.split(',') if t.strip().isdigit()]
                
                if team_number in red_teams or team_number in blue_teams:
                    team_matches.append({
                        'match_key': match.get('k', ''),
                        'event_key': match.get('ek', ''),
                        'match_number': match.get('mn', ''),
                        'comp_level': match.get('cl', ''),
                        'red_teams': red_teams,
                        'blue_teams': blue_teams,
                        'red_score': match.get('rs', 0),
                        'blue_score': match.get('bs', 0),
                        'winner': match.get('wa', ''),
                        'alliance': 'red' if team_number in red_teams else 'blue',
                        'time': match.get('t', '')
                    })
        
        return jsonify({
            'team_key': team_key,
            'matches': team_matches,
            'count': len(team_matches),
            'last_updated': datetime.now().isoformat()
        })
    
    @app.route('/api/v1/team/<team_key>/events')
    @require_api_key
    @rate_limit
    def get_team_events(team_key):
        """Get all events for a team"""
        try:
            team_number = int(team_key)
        except ValueError:
            return jsonify({'error': 'Invalid team key'}), 400
        
        # Get events where team participated
        team_events = []
        event_teams_data = EVENT_TEAMS.get(2025, {})
        
        for event_key, teams in event_teams_data.items():
            if any(team.get('tk') == team_number for team in teams):
                event_data = EVENT_DATABASE.get(2025, {}).get(event_key, {})
                team_events.append({
                    'event_key': event_key,
                    'name': event_data.get('n', 'Unknown'),
                    'start_date': event_data.get('sd', ''),
                    'end_date': event_data.get('ed', ''),
                    'city': event_data.get('c', ''),
                    'state_prov': event_data.get('st', ''),
                    'country': event_data.get('cy', ''),
                    'event_type': event_data.get('et', ''),
                    'week': event_data.get('w', '')
                })
        
        return jsonify({
            'team_key': team_key,
            'events': team_events,
            'count': len(team_events),
            'last_updated': datetime.now().isoformat()
        })
    
    @app.route('/api/v1/team/<team_key>/<event_key>/matches')
    @require_api_key
    @rate_limit
    def get_team_event_matches(team_key, event_key):
        """Get matches for a specific team at a specific event"""
        try:
            team_number = int(team_key)
        except ValueError:
            return jsonify({'error': 'Invalid team key'}), 400
        
        # Get matches for the event
        all_matches = EVENT_MATCHES.get(2025, [])
        event_matches = [match for match in all_matches if match.get('ek') == event_key]
        
        if not event_matches:
            return jsonify({'error': 'No matches found for this event'}), 404
        
        team_matches = []
        for match in event_matches:
            if isinstance(match, dict):
                red_teams_str = match.get('rt', '')
                blue_teams_str = match.get('bt', '')
                
                red_teams = []
                blue_teams = []
                
                if red_teams_str:
                    red_teams = [int(t) for t in red_teams_str.split(',') if t.strip().isdigit()]
                if blue_teams_str:
                    blue_teams = [int(t) for t in blue_teams_str.split(',') if t.strip().isdigit()]
                
                if team_number in red_teams or team_number in blue_teams:
                    team_matches.append({
                        'match_key': match.get('k', ''),
                        'match_number': match.get('mn', ''),
                        'comp_level': match.get('cl', ''),
                        'red_teams': red_teams,
                        'blue_teams': blue_teams,
                        'red_score': match.get('rs', 0),
                        'blue_score': match.get('bs', 0),
                        'winner': match.get('wa', ''),
                        'alliance': 'red' if team_number in red_teams else 'blue',
                        'time': match.get('t', '')
                    })
        
        return jsonify({
            'team_key': team_key,
            'event_key': event_key,
            'matches': team_matches,
            'count': len(team_matches),
            'last_updated': datetime.now().isoformat()
        })
    
    @app.route('/api/v1/team/<team_key>/<event_key>/awards')
    @require_api_key
    @rate_limit
    def get_team_event_awards(team_key, event_key):
        """Get awards for a specific team at a specific event"""
        try:
            team_number = int(team_key)
        except ValueError:
            return jsonify({'error': 'Invalid team key'}), 400
        
        # Get awards for the team at this event
        team_awards = []
        for award in EVENT_AWARDS:
            if (award.get('ek') == event_key and 
                award.get('tk') == team_number and 
                award.get('y') == 2025):
                team_awards.append({
                    'award_name': award.get('an', ''),
                    'event_key': award.get('ek', ''),
                    'year': award.get('y', '')
                })
        
        return jsonify({
            'team_key': team_key,
            'event_key': event_key,
            'awards': team_awards,
            'count': len(team_awards),
            'last_updated': datetime.now().isoformat()
        })
    
    @app.route('/api/v1/team/<team_key>/<event_key>/rankings')
    @require_api_key
    @rate_limit
    def get_team_event_rankings(team_key, event_key):
        """Get ranking for a specific team at a specific event"""
        try:
            team_number = int(team_key)
        except ValueError:
            return jsonify({'error': 'Invalid team key'}), 400
        
        # Get ranking for the team at this event
        event_rankings_data = EVENT_RANKINGS.get(2025, {}).get(event_key, {})
        team_ranking = event_rankings_data.get(team_number)
        
        if not team_ranking:
            return jsonify({'error': 'No ranking found for this team at this event'}), 404
        
        response = {
            'team_key': team_key,
            'event_key': event_key,
            'rank': team_ranking.get('rk', 0),
            'wins': team_ranking.get('w', 0),
            'losses': team_ranking.get('l', 0),
            'ties': team_ranking.get('t', 0),
            'dq': team_ranking.get('dq', 0),
            'matches_played': team_ranking.get('mp', 0),
            'ranking_score': team_ranking.get('rs', 0),
            'auto_ranking_score': team_ranking.get('ars', 0),
            'teleop_ranking_score': team_ranking.get('trs', 0),
            'endgame_ranking_score': team_ranking.get('ers', 0),
            'last_updated': datetime.now().isoformat()
        }
        
        return jsonify(response)
    
    @app.route('/api/v1/team/<team_key>/awards')
    @require_api_key
    @rate_limit
    def get_team_awards(team_key):
        """Get all awards for a team"""
        try:
            team_number = int(team_key)
        except ValueError:
            return jsonify({'error': 'Invalid team key'}), 400
        
        # Get all awards for the team
        team_awards = []
        for award in EVENT_AWARDS:
            if (award.get('tk') == team_number and 
                award.get('y') == 2025):
                team_awards.append({
                    'award_name': award.get('an', ''),
                    'event_key': award.get('ek', ''),
                    'year': award.get('y', '')
                })
        
        return jsonify({
            'team_key': team_key,
            'awards': team_awards,
            'count': len(team_awards),
            'last_updated': datetime.now().isoformat()
        })
    
    # ===== EVENTS ENDPOINTS =====
    
    @app.route('/api/v1/events')
    @require_api_key
    @rate_limit
    def get_events_page():
        """Get paginated events with optional filtering"""
        year = request.args.get('year', '2025')
        event_type = request.args.get('event_type')
        week = request.args.get('week')
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(int(request.args.get('per_page', 50)), 100)  # Max 100 per page
        offset = (page - 1) * per_page
        
        try:
            year = int(year)
        except ValueError:
            return jsonify({'error': 'Invalid year'}), 400
        
        # Get events for the specified year
        if year == 2025:
            events_data = EVENT_DATABASE.get(2025, {})
        else:
            try:
                _, year_event_data, _, _, _, _ = load_year_data(year)
                events_data = year_event_data
            except Exception as e:
                return jsonify({'error': f'Data not available for year {year}'}), 404
        
        # Filter events
        filtered_events = []
        for event_key, event_data in events_data.items():
            if event_type and event_data.get('et') != event_type:
                continue
            if week and str(event_data.get('w', '')) != str(week):
                continue
            
            filtered_events.append({
                'event_key': event_key,
                'name': event_data.get('n', 'Unknown'),
                'start_date': event_data.get('sd', ''),
                'end_date': event_data.get('ed', ''),
                'city': event_data.get('c', ''),
                'state_prov': event_data.get('st', ''),
                'country': event_data.get('cy', ''),
                'event_type': event_data.get('et', ''),
                'week': event_data.get('w', '')
            })
        
        # Sort by event key
        filtered_events.sort(key=lambda x: x['event_key'])
        
        # Paginate
        total_count = len(filtered_events)
        paginated_events = filtered_events[offset:offset + per_page]
        
        return jsonify({
            'events': paginated_events,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': (total_count + per_page - 1) // per_page,
                'has_next': offset + per_page < total_count,
                'has_prev': page > 1
            },
            'year': year,
            'last_updated': datetime.now().isoformat()
        })
    
    @app.route('/api/v1/event/<event_key>')
    @require_api_key
    @rate_limit
    def get_event(event_key):
        """Get event information by event key"""
        # Get event data from 2025 database
        event_data = EVENT_DATABASE.get(2025, {}).get(event_key)
        
        if not event_data:
            return jsonify({'error': 'Event not found'}), 404
        
        # Get event teams
        event_teams = EVENT_TEAMS.get(2025, {}).get(event_key, [])
        
        response = {
            'event_key': event_key,
            'name': event_data.get('n', 'Unknown'),
            'start_date': event_data.get('sd', ''),
            'end_date': event_data.get('ed', ''),
            'city': event_data.get('c', ''),
            'state_prov': event_data.get('st', ''),
            'country': event_data.get('cy', ''),
            'event_type': event_data.get('et', ''),
            'week': event_data.get('w', ''),
            'team_count': len(event_teams),
            'teams': [int(team.get('tk', 0)) for team in event_teams if team.get('tk')],
            'last_updated': datetime.now().isoformat()
        }
        
        return jsonify(response)
    
    @app.route('/api/v1/event/<event_key>/matches')
    @require_api_key
    @rate_limit
    def get_event_matches(event_key):
        """Get all matches for an event"""
        # Get matches for the event from the flat list
        all_matches = EVENT_MATCHES.get(2025, [])
        event_matches = [match for match in all_matches if match.get('ek') == event_key]
        
        if not event_matches:
            return jsonify({'error': 'No matches found for this event'}), 404
        
        matches = []
        for match in event_matches:
            # Handle different match data structures
            if isinstance(match, dict):
                # Standard match format
                red_teams_str = match.get('rt', '')
                blue_teams_str = match.get('bt', '')
                
                red_teams = []
                blue_teams = []
                
                if red_teams_str:
                    red_teams = [int(t) for t in red_teams_str.split(',') if t.strip().isdigit()]
                if blue_teams_str:
                    blue_teams = [int(t) for t in blue_teams_str.split(',') if t.strip().isdigit()]
                
                matches.append({
                    'match_key': match.get('k', ''),
                    'match_number': match.get('mn', ''),
                    'comp_level': match.get('cl', ''),
                    'red_teams': red_teams,
                    'blue_teams': blue_teams,
                    'red_score': match.get('rs', 0),
                    'blue_score': match.get('bs', 0),
                    'winner': match.get('wa', ''),
                    'time': match.get('t', '')
                })
            else:
                # Skip non-dict matches
                continue
        
        return jsonify({
            'event_key': event_key,
            'matches': matches,
            'count': len(matches),
            'last_updated': datetime.now().isoformat()
        })
    
    @app.route('/api/v1/event/<event_key>/<team_key>/matches')
    @require_api_key
    @rate_limit
    def get_event_team_matches(event_key, team_key):
        """Get matches for a specific team at a specific event"""
        try:
            team_number = int(team_key)
        except ValueError:
            return jsonify({'error': 'Invalid team key'}), 400
        
        # Get matches for the event
        all_matches = EVENT_MATCHES.get(2025, [])
        event_matches = [match for match in all_matches if match.get('ek') == event_key]
        
        if not event_matches:
            return jsonify({'error': 'No matches found for this event'}), 404
        
        team_matches = []
        for match in event_matches:
            if isinstance(match, dict):
                red_teams_str = match.get('rt', '')
                blue_teams_str = match.get('bt', '')
                
                red_teams = []
                blue_teams = []
                
                if red_teams_str:
                    red_teams = [int(t) for t in red_teams_str.split(',') if t.strip().isdigit()]
                if blue_teams_str:
                    blue_teams = [int(t) for t in blue_teams_str.split(',') if t.strip().isdigit()]
                
                if team_number in red_teams or team_number in blue_teams:
                    team_matches.append({
                        'match_key': match.get('k', ''),
                        'match_number': match.get('mn', ''),
                        'comp_level': match.get('cl', ''),
                        'red_teams': red_teams,
                        'blue_teams': blue_teams,
                        'red_score': match.get('rs', 0),
                        'blue_score': match.get('bs', 0),
                        'winner': match.get('wa', ''),
                        'alliance': 'red' if team_number in red_teams else 'blue',
                        'time': match.get('t', '')
                    })
        
        return jsonify({
            'event_key': event_key,
            'team_key': team_key,
            'matches': team_matches,
            'count': len(team_matches),
            'last_updated': datetime.now().isoformat()
        })
    
    @app.route('/api/v1/event/<event_key>/rankings')
    @require_api_key
    @rate_limit
    def get_event_rankings(event_key):
        """Get rankings for an event"""
        # Get rankings for the event
        event_rankings_data = EVENT_RANKINGS.get(2025, {}).get(event_key, {})
        
        if not event_rankings_data:
            return jsonify({'error': 'No rankings found for this event'}), 404
        
        rankings = []
        for team_key, rank_data in event_rankings_data.items():
            # Handle different team_key formats
            if isinstance(team_key, str):
                team_number = team_key.replace('frc', '')
            else:
                team_number = str(team_key)
            
            try:
                team_number_int = int(team_number)
            except ValueError:
                continue  # Skip invalid team numbers
            
            rankings.append({
                'team_number': team_number_int,
                'rank': rank_data.get('rk', 0),
                'wins': rank_data.get('w', 0),
                'losses': rank_data.get('l', 0),
                'ties': rank_data.get('t', 0),
                'dq': rank_data.get('dq', 0),
                'matches_played': rank_data.get('mp', 0),
                'ranking_score': rank_data.get('rs', 0),
                'auto_ranking_score': rank_data.get('ars', 0),
                'teleop_ranking_score': rank_data.get('trs', 0),
                'endgame_ranking_score': rank_data.get('ers', 0)
            })
        
        # Sort by rank
        rankings.sort(key=lambda x: x['rank'])
        
        return jsonify({
            'event_key': event_key,
            'rankings': rankings,
            'count': len(rankings),
            'last_updated': datetime.now().isoformat()
        })
    
    @app.route('/api/v1/event/<event_key>/<team_key>/rankings')
    @require_api_key
    @rate_limit
    def get_event_team_rankings(event_key, team_key):
        """Get ranking for a specific team at a specific event"""
        try:
            team_number = int(team_key)
        except ValueError:
            return jsonify({'error': 'Invalid team key'}), 400
        
        # Get ranking for the team at this event
        event_rankings_data = EVENT_RANKINGS.get(2025, {}).get(event_key, {})
        team_ranking = event_rankings_data.get(team_number)
        
        if not team_ranking:
            return jsonify({'error': 'No ranking found for this team at this event'}), 404
        
        response = {
            'event_key': event_key,
            'team_key': team_key,
            'rank': team_ranking.get('rk', 0),
            'wins': team_ranking.get('w', 0),
            'losses': team_ranking.get('l', 0),
            'ties': team_ranking.get('t', 0),
            'dq': team_ranking.get('dq', 0),
            'matches_played': team_ranking.get('mp', 0),
            'ranking_score': team_ranking.get('rs', 0),
            'auto_ranking_score': team_ranking.get('ars', 0),
            'teleop_ranking_score': team_ranking.get('trs', 0),
            'endgame_ranking_score': team_ranking.get('ers', 0),
            'last_updated': datetime.now().isoformat()
        }
        
        return jsonify(response)
    
    @app.route('/api/v1/event/<event_key>/awards')
    @require_api_key
    @rate_limit
    def get_event_awards(event_key):
        """Get all awards for an event"""
        # Get awards for this event
        event_awards = []
        for award in EVENT_AWARDS:
            if (award.get('ek') == event_key and 
                award.get('y') == 2025):
                event_awards.append({
                    'team_key': award.get('tk', ''),
                    'award_name': award.get('an', ''),
                    'year': award.get('y', '')
                })
        
        return jsonify({
            'event_key': event_key,
            'awards': event_awards,
            'count': len(event_awards),
            'last_updated': datetime.now().isoformat()
        })
    
    @app.route('/api/v1/event/<event_key>/<team_key>/awards')
    @require_api_key
    @rate_limit
    def get_event_team_awards(event_key, team_key):
        """Get awards for a specific team at a specific event"""
        try:
            team_number = int(team_key)
        except ValueError:
            return jsonify({'error': 'Invalid team key'}), 400
        
        # Get awards for the team at this event
        team_awards = []
        for award in EVENT_AWARDS:
            if (award.get('ek') == event_key and 
                award.get('tk') == team_number and 
                award.get('y') == 2025):
                team_awards.append({
                    'award_name': award.get('an', ''),
                    'year': award.get('y', '')
                })
        
        return jsonify({
            'event_key': event_key,
            'team_key': team_key,
            'awards': team_awards,
            'count': len(team_awards),
            'last_updated': datetime.now().isoformat()
        })
    
    # ===== UTILITY ENDPOINTS =====
    
    @app.route('/api/v1/health')
    def health_check():
        """Health check endpoint (no authentication required)"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0'
        })
    
    @app.route('/api/v1/')
    def api_info():
        """API information endpoint (no authentication required)"""
        return jsonify({
            'name': 'Peekorobo API',
            'version': '1.0.0',
            'description': 'API for FRC team and event data',
            'endpoints': {
                # Teams
                'teams': '/api/v1/teams',
                'team': '/api/v1/team/{team_key}',
                'team_matches': '/api/v1/team/{team_key}/matches',
                'team_events': '/api/v1/team/{team_key}/events',
                'team_event_matches': '/api/v1/team/{team_key}/{event_key}/matches',
                'team_event_awards': '/api/v1/team/{team_key}/{event_key}/awards',
                'team_event_rankings': '/api/v1/team/{team_key}/{event_key}/rankings',
                'team_awards': '/api/v1/team/{team_key}/awards',
                # Events
                'events': '/api/v1/events',
                'event': '/api/v1/event/{event_key}',
                'event_matches': '/api/v1/event/{event_key}/matches',
                'event_team_matches': '/api/v1/event/{event_key}/{team_key}/matches',
                'event_rankings': '/api/v1/event/{event_key}/rankings',
                'event_team_rankings': '/api/v1/event/{event_key}/{team_key}/rankings',
                'event_awards': '/api/v1/event/{event_key}/awards',
                'event_team_awards': '/api/v1/event/{event_key}/{team_key}/awards',
                # Utility
                'health': '/api/v1/health'
            },
            'authentication': 'X-API-Key header required for most endpoints',
            'rate_limiting': 'Basic rate limiting applied',
            'pagination': 'Use page and per_page parameters for paginated endpoints',
            'last_updated': datetime.now().isoformat()
        }) 