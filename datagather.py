from dotenv import load_dotenv
import os
import random
import requests
import numpy as np
from urllib.parse import urlparse
import psycopg2
import json

load_dotenv()

TBA_BASE_URL = "https://www.thebluealliance.com/api/v3"

API_KEYS = os.getenv("TBA_API_KEYS").split(',')

def tba_get(endpoint: str):
    # Cycle through keys by selecting one randomly or using a round-robin approach.
    api_key = random.choice(API_KEYS)
    headers = {"X-TBA-Auth-Key": api_key}
    url = f"{TBA_BASE_URL}/{endpoint}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    return None

def load_data():
    def compress_dict(d):
        """Remove any None or empty string values. Keep empty lists and dictionaries."""
        return {k: v for k, v in d.items() if v not in (None, "")}

    # === Load team EPA data from PostgreSQL ===
    conn = get_pg_connection()
    team_cursor = conn.cursor()
    
    # Get all team EPA data
    team_cursor.execute("""
        SELECT team_number, year, nickname, city, state_prov, country, website,
               normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa,
               wins, losses, event_epas
        FROM team_epas
        ORDER BY year, team_number
    """)
    
    team_data = {}
    for row in team_cursor.fetchall():
        team_number, year, nickname, city, state_prov, country, website, \
        normal_epa, epa, confidence, auto_epa, teleop_epa, endgame_epa, \
        wins, losses, event_epas = row
        
        raw_team_data = {
            "team_number": team_number,
            "year": year,
            "nickname": nickname,
            "city": city,
            "state_prov": state_prov,
            "country": country,
            "website": website,
            "normal_epa": normal_epa,
            "epa": epa,
            "confidence": confidence,
            "auto_epa": auto_epa,
            "teleop_epa": teleop_epa,
            "endgame_epa": endgame_epa,
            "wins": wins,
            "losses": losses,
            "event_epas": event_epas
        }
        
        # Parse event_epas from JSON if it's a string
        if raw_team_data["event_epas"] is None:
            raw_team_data["event_epas"] = []
        elif isinstance(raw_team_data["event_epas"], str):
            try:
                raw_team_data["event_epas"] = json.loads(raw_team_data["event_epas"])
            except json.JSONDecodeError:
                raw_team_data["event_epas"] = []
        
        # Compress the dictionary
        team = compress_dict(raw_team_data)
        team_data.setdefault(year, {})[team_number] = team

    # === Load event data from PostgreSQL ===
    # Events
    event_cursor = conn.cursor()
    event_cursor.execute("""
        SELECT event_key, name, year, start_date, end_date, event_type, city, state_prov, country, website
        FROM events
        ORDER BY year, event_key
    """)
    
    event_data = {}
    for row in event_cursor.fetchall():
        event_key, name, year, start_date, end_date, event_type, city, state_prov, country, website = row
        ev = compress_dict({
            "k": event_key,
            "n": name,
            "y": year,
            "sd": start_date,
            "ed": end_date,
            "et": event_type,
            "c": city,
            "s": state_prov,
            "co": country,
            "w": website
        })
        event_data.setdefault(year, {})[event_key] = ev

    # Event Teams
    event_cursor.execute("""
        SELECT event_key, team_number, nickname, city, state_prov, country
        FROM event_teams
        ORDER BY event_key, team_number
    """)
    
    EVENT_TEAMS = {}
    for row in event_cursor.fetchall():
        event_key, team_number, nickname, city, state_prov, country = row
        year = int(event_key[:4])
        team = compress_dict({
            "ek": event_key,
            "tk": team_number,
            "nn": nickname,
            "c": city,
            "s": state_prov,
            "co": country
        })
        EVENT_TEAMS.setdefault(year, {}).setdefault(event_key, []).append(team)

    # Rankings
    event_cursor.execute("""
        SELECT event_key, team_number, rank, wins, losses, ties, dq
        FROM event_rankings
        ORDER BY event_key, team_number
    """)
    
    EVENT_RANKINGS = {}
    for row in event_cursor.fetchall():
        event_key, team_number, rank, wins, losses, ties, dq = row
        year = int(event_key[:4])
        ranking = compress_dict({
            "ek": event_key,
            "tk": team_number,
            "rk": rank,
            "w": wins,
            "l": losses,
            "t": ties,
            "dq": dq
        })
        EVENT_RANKINGS.setdefault(year, {}).setdefault(event_key, {})[team_number] = ranking

    # Awards
    event_cursor.execute("""
        SELECT event_key, team_number, award_name, year
        FROM event_awards
        ORDER BY year, event_key, team_number
    """)
    
    EVENTS_AWARDS = []
    for row in event_cursor.fetchall():
        event_key, team_number, award_name, year = row
        award = compress_dict({
            "ek": event_key,
            "tk": team_number,
            "an": award_name,
            "y": year
        })
        EVENTS_AWARDS.append(award)

    # Matches
    event_cursor.execute("""
        SELECT match_key, event_key, comp_level, match_number, set_number, 
               red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key
        FROM event_matches
        ORDER BY event_key, match_number
    """)
    
    EVENT_MATCHES = {}
    for row in event_cursor.fetchall():
        match_key, event_key, comp_level, match_number, set_number, \
        red_teams, blue_teams, red_score, blue_score, winning_alliance, youtube_key = row
        year = int(event_key[:4])
        match_data = compress_dict({
            "k": match_key,
            "ek": event_key,
            "cl": comp_level,
            "mn": match_number,
            "sn": set_number,
            "rt": red_teams,
            "bt": blue_teams,
            "rs": red_score,
            "bs": blue_score,
            "wa": winning_alliance,
            "yt": youtube_key
        })
        EVENT_MATCHES.setdefault(year, []).append(match_data)

    event_cursor.close()
    team_cursor.close()
    conn.close()

    return team_data, event_data, EVENT_TEAMS, EVENT_RANKINGS, EVENTS_AWARDS, EVENT_MATCHES

def get_team_avatar(team_number, year=2025):
    """
    Returns the relative URL path to a team's avatar image if it exists,
    otherwise returns the path to a stock avatar.
    """
    avatar_path = f"assets/avatars/{team_number}.png"
    if os.path.exists(avatar_path):
        return f"/assets/avatars/{team_number}.png?v=1"
    return "/assets/avatars/stock.png"

def get_pg_connection():
    url = os.environ.get("DATABASE_URL")
    if url is None:
        raise Exception("DATABASE_URL not set in environment.")

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    result = urlparse(url)
    conn = psycopg2.connect(
        database=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port
    )
    return conn

# locations.py

COUNTRIES = [
    {"label": "All Countries", "value": "All"},
    {"label": "USA", "value": "USA"},
    {"label": "Canada", "value": "Canada"},
    {"label": "Mexico", "value": "Mexico"},
    {"label": "Australia", "value": "Australia"},
    {"label": "China", "value": "China"},
    {"label": "India", "value": "India"},
    {"label": "Israel", "value": "Israel"},
    {"label": "Brazil", "value": "Brazil"},
    {"label": "Türkiye", "value": "Türkiye"},
    {"label": "Chinese Taipei", "value": "Chinese Taipei"},
    {"label": "Argentina", "value": "Argentina"},
    {"label": "Azerbaijan", "value": "Azerbaijan"},
    {"label": "Belize", "value": "Belize"},
    {"label": "Bulgaria", "value": "Bulgaria"},
    {"label": "Colombia", "value": "Colombia"},
    {"label": "Croatia", "value": "Croatia"},
    {"label": "Czech Republic", "value": "Czech Republic"},
    {"label": "Dominican Republic", "value": "Dominican Republic"},
    {"label": "France", "value": "France"},
    {"label": "Greece", "value": "Greece"},
    {"label": "Hungary", "value": "Hungary"},
    {"label": "Japan", "value": "Japan"},
    {"label": "Netherlands", "value": "Netherlands"},
    {"label": "Panama", "value": "Panama"},
    {"label": "Philippines", "value": "Philippines"},
    {"label": "Poland", "value": "Poland"},
    {"label": "Singapore", "value": "Singapore"},
    {"label": "South Africa", "value": "South Africa"},
    {"label": "Switzerland", "value": "Switzerland"},
    {"label": "United Kingdom", "value": "United Kingdom"},
]

STATES = {
    "USA": [
        {"label": "Alabama", "value": "Alabama"},
        {"label": "Alaska", "value": "Alaska"},
        {"label": "Arizona", "value": "Arizona"},
        {"label": "Arkansas", "value": "Arkansas"},
        {"label": "California", "value": "California"},
        {"label": "Colorado", "value": "Colorado"},
        {"label": "Connecticut", "value": "Connecticut"},
        {"label": "Delaware", "value": "Delaware"},
        {"label": "Florida", "value": "Florida"},
        {"label": "Georgia", "value": "Georgia"},
        {"label": "Hawaii", "value": "Hawaii"},
        {"label": "Idaho", "value": "Idaho"},
        {"label": "Illinois", "value": "Illinois"},
        {"label": "Indiana", "value": "Indiana"},
        {"label": "Iowa", "value": "Iowa"},
        {"label": "Kansas", "value": "Kansas"},
        {"label": "Kentucky", "value": "Kentucky"},
        {"label": "Louisiana", "value": "Louisiana"},
        {"label": "Maine", "value": "Maine"},
        {"label": "Maryland", "value": "Maryland"},
        {"label": "Massachusetts", "value": "Massachusetts"},
        {"label": "Michigan", "value": "Michigan"},
        {"label": "Minnesota", "value": "Minnesota"},
        {"label": "Mississippi", "value": "Mississippi"},
        {"label": "Missouri", "value": "Missouri"},
        {"label": "Montana", "value": "Montana"},
        {"label": "Nebraska", "value": "Nebraska"},
        {"label": "Nevada", "value": "Nevada"},
        {"label": "New Hampshire", "value": "New Hampshire"},
        {"label": "New Jersey", "value": "New Jersey"},
        {"label": "New Mexico", "value": "New Mexico"},
        {"label": "New York", "value": "New York"},
        {"label": "North Carolina", "value": "North Carolina"},
        {"label": "North Dakota", "value": "North Dakota"},
        {"label": "Ohio", "value": "Ohio"},
        {"label": "Oklahoma", "value": "Oklahoma"},
        {"label": "Oregon", "value": "Oregon"},
        {"label": "Pennsylvania", "value": "Pennsylvania"},
        {"label": "Rhode Island", "value": "Rhode Island"},
        {"label": "South Carolina", "value": "South Carolina"},
        {"label": "South Dakota", "value": "South Dakota"},
        {"label": "Tennessee", "value": "Tennessee"},
        {"label": "Texas", "value": "Texas"},
        {"label": "Utah", "value": "Utah"},
        {"label": "Vermont", "value": "Vermont"},
        {"label": "Virginia", "value": "Virginia"},
        {"label": "Washington", "value": "Washington"},
        {"label": "West Virginia", "value": "West Virginia"},
        {"label": "Wisconsin", "value": "Wisconsin"},
        {"label": "Wyoming", "value": "Wyoming"},
    ],
    "Canada": [
        {"label": "Alberta", "value": "Alberta"},
        {"label": "British Columbia", "value": "British Columbia"},
        {"label": "Manitoba", "value": "Manitoba"},
        {"label": "New Brunswick", "value": "New Brunswick"},
        {"label": "Newfoundland and Labrador", "value": "Newfoundland and Labrador"},
        {"label": "Nova Scotia", "value": "Nova Scotia"},
        {"label": "Ontario", "value": "Ontario"},
        {"label": "Prince Edward Island", "value": "Prince Edward Island"},
        {"label": "Quebec", "value": "Quebec"},
        {"label": "Saskatchewan", "value": "Saskatchewan"},
    ],
    "Mexico": [
        {"label": "Aguascalientes", "value": "Aguascalientes"},
        {"label": "Baja California", "value": "Baja California"},
        {"label": "Chihuahua", "value": "Chihuahua"},
        {"label": "Coahuila", "value": "Coahuila"},
        {"label": "Jalisco", "value": "Jalisco"},
        {"label": "Mexico City", "value": "Mexico City"},
        {"label": "Nuevo León", "value": "Nuevo León"},
        {"label": "Puebla", "value": "Puebla"},
        {"label": "Querétaro", "value": "Querétaro"},
        {"label": "Yucatán", "value": "Yucatán"},
    ],
    "Australia": [
        {"label": "New South Wales", "value": "New South Wales"},
        {"label": "Queensland", "value": "Queensland"},
        {"label": "South Australia", "value": "South Australia"},
        {"label": "Tasmania", "value": "Tasmania"},
        {"label": "Victoria", "value": "Victoria"},
        {"label": "Western Australia", "value": "Western Australia"},
    ],
    "India": [
        {"label": "Delhi", "value": "Delhi"},
        {"label": "Karnataka", "value": "Karnataka"},
        {"label": "Maharashtra", "value": "Maharashtra"},
        {"label": "Tamil Nadu", "value": "Tamil Nadu"},
        {"label": "Uttar Pradesh", "value": "Uttar Pradesh"},
    ],
}

STATES.update({
    "Israel": [
        {"label": "Central District", "value": "Central District"},
        {"label": "Haifa District", "value": "Haifa District"},
        {"label": "Jerusalem District", "value": "Jerusalem District"},
        {"label": "Northern District", "value": "Northern District"},
        {"label": "Southern District", "value": "Southern District"},
        {"label": "Tel Aviv District", "value": "Tel Aviv District"},
    ],
    "Türkiye": [
        {"label": "Adana", "value": "Adana"},
        {"label": "Ankara", "value": "Ankara"},
        {"label": "Antalya", "value": "Antalya"},
        {"label": "Bursa", "value": "Bursa"},
        {"label": "Istanbul", "value": "Istanbul"},
        {"label": "Izmir", "value": "Izmir"},
        {"label": "Konya", "value": "Konya"},
        {"label": "Gaziantep", "value": "Gaziantep"},
        {"label": "Mersin", "value": "Mersin"},
        {"label": "Kayseri", "value": "Kayseri"},
        {"label": "Eskisehir", "value": "Eskisehir"},
    ],
    "Brazil": [
        {"label": "Acre", "value": "Acre"},
        {"label": "Alagoas", "value": "Alagoas"},
        {"label": "Amapá", "value": "Amapá"},
        {"label": "Amazonas", "value": "Amazonas"},
        {"label": "Bahia", "value": "Bahia"},
        {"label": "Ceará", "value": "Ceará"},
        {"label": "Distrito Federal", "value": "Distrito Federal"},
        {"label": "Espírito Santo", "value": "Espírito Santo"},
        {"label": "Goiás", "value": "Goiás"},
        {"label": "Maranhão", "value": "Maranhão"},
        {"label": "Mato Grosso", "value": "Mato Grosso"},
        {"label": "Mato Grosso do Sul", "value": "Mato Grosso do Sul"},
        {"label": "Minas Gerais", "value": "Minas Gerais"},
        {"label": "Pará", "value": "Pará"},
        {"label": "Paraíba", "value": "Paraíba"},
        {"label": "Paraná", "value": "Paraná"},
        {"label": "Pernambuco", "value": "Pernambuco"},
        {"label": "Piauí", "value": "Piauí"},
        {"label": "Rio de Janeiro", "value": "Rio de Janeiro"},
        {"label": "Rio Grande do Norte", "value": "Rio Grande do Norte"},
        {"label": "Rio Grande do Sul", "value": "Rio Grande do Sul"},
        {"label": "Rondônia", "value": "Rondônia"},
        {"label": "Roraima", "value": "Roraima"},
        {"label": "Santa Catarina", "value": "Santa Catarina"},
        {"label": "São Paulo", "value": "São Paulo"},
        {"label": "Sergipe", "value": "Sergipe"},
        {"label": "Tocantins", "value": "Tocantins"},
    ],
    "China": [
        {"label": "Anhui", "value": "Anhui"},
        {"label": "Beijing", "value": "Beijing"},
        {"label": "Chongqing", "value": "Chongqing"},
        {"label": "Fujian", "value": "Fujian"},
        {"label": "Gansu", "value": "Gansu"},
        {"label": "Guangdong", "value": "Guangdong"},
        {"label": "Guangxi", "value": "Guangxi"},
        {"label": "Guizhou", "value": "Guizhou"},
        {"label": "Hainan", "value": "Hainan"},
        {"label": "Hebei", "value": "Hebei"},
        {"label": "Heilongjiang", "value": "Heilongjiang"},
        {"label": "Henan", "value": "Henan"},
        {"label": "Hubei", "value": "Hubei"},
        {"label": "Hunan", "value": "Hunan"},
        {"label": "Inner Mongolia", "value": "Inner Mongolia"},
        {"label": "Jiangsu", "value": "Jiangsu"},
        {"label": "Jiangxi", "value": "Jiangxi"},
        {"label": "Jilin", "value": "Jilin"},
        {"label": "Liaoning", "value": "Liaoning"},
        {"label": "Ningxia", "value": "Ningxia"},
        {"label": "Qinghai", "value": "Qinghai"},
        {"label": "Shaanxi", "value": "Shaanxi"},
        {"label": "Shandong", "value": "Shandong"},
        {"label": "Shanghai", "value": "Shanghai"},
        {"label": "Shanxi", "value": "Shanxi"},
        {"label": "Sichuan", "value": "Sichuan"},
        {"label": "Tianjin", "value": "Tianjin"},
        {"label": "Tibet", "value": "Tibet"},
        {"label": "Xinjiang", "value": "Xinjiang"},
        {"label": "Yunnan", "value": "Yunnan"},
        {"label": "Zhejiang", "value": "Zhejiang"},
    ],
    "Chinese Taipei": [
        {"label": "Taipei", "value": "Taipei"},
        {"label": "New Taipei", "value": "New Taipei"},
        {"label": "Taichung", "value": "Taichung"},
        {"label": "Tainan", "value": "Tainan"},
        {"label": "Kaohsiung", "value": "Kaohsiung"},
        {"label": "Hsinchu", "value": "Hsinchu"},
        {"label": "Keelung", "value": "Keelung"},
        {"label": "Taoyuan", "value": "Taoyuan"},
        {"label": "Chiayi", "value": "Chiayi"},
    ],
})
STATES.update({
    "Argentina": [
        {"label": "Buenos Aires", "value": "Buenos Aires"},
        {"label": "Córdoba", "value": "Córdoba"},
        {"label": "Santa Fe", "value": "Santa Fe"},
        {"label": "Mendoza", "value": "Mendoza"},
        {"label": "Tucumán", "value": "Tucumán"},
    ],
    "Azerbaijan": [
        {"label": "Baku", "value": "Baku"},
        {"label": "Ganja", "value": "Ganja"},
        {"label": "Sumqayit", "value": "Sumqayit"},
        {"label": "Mingachevir", "value": "Mingachevir"},
    ],
    "Belize": [
        {"label": "Belize District", "value": "Belize District"},
        {"label": "Cayo", "value": "Cayo"},
        {"label": "Orange Walk", "value": "Orange Walk"},
        {"label": "Stann Creek", "value": "Stann Creek"},
        {"label": "Toledo", "value": "Toledo"},
    ],
    "Brazil": [
        {"label": "São Paulo", "value": "São Paulo"},
        {"label": "Rio de Janeiro", "value": "Rio de Janeiro"},
        {"label": "Minas Gerais", "value": "Minas Gerais"},
        {"label": "Bahia", "value": "Bahia"},
        {"label": "Paraná", "value": "Paraná"},
    ],
    "Bulgaria": [
        {"label": "Sofia", "value": "Sofia"},
        {"label": "Plovdiv", "value": "Plovdiv"},
        {"label": "Varna", "value": "Varna"},
        {"label": "Burgas", "value": "Burgas"},
        {"label": "Ruse", "value": "Ruse"},
    ],
    "Colombia": [
        {"label": "Bogotá", "value": "Bogotá"},
        {"label": "Antioquia", "value": "Antioquia"},
        {"label": "Valle del Cauca", "value": "Valle del Cauca"},
        {"label": "Atlántico", "value": "Atlántico"},
        {"label": "Santander", "value": "Santander"},
    ],
    "Croatia": [
        {"label": "Zagreb", "value": "Zagreb"},
        {"label": "Split-Dalmatia", "value": "Split-Dalmatia"},
        {"label": "Istria", "value": "Istria"},
        {"label": "Dubrovnik-Neretva", "value": "Dubrovnik-Neretva"},
    ],
    "Czech Republic": [
        {"label": "Prague", "value": "Prague"},
        {"label": "South Moravian", "value": "South Moravian"},
        {"label": "Central Bohemian", "value": "Central Bohemian"},
        {"label": "Moravian-Silesian", "value": "Moravian-Silesian"},
    ],
    "Dominican Republic": [
        {"label": "Santo Domingo", "value": "Santo Domingo"},
        {"label": "Santiago", "value": "Santiago"},
        {"label": "La Vega", "value": "La Vega"},
        {"label": "Puerto Plata", "value": "Puerto Plata"},
    ],
    "France": [
        {"label": "Île-de-France", "value": "Île-de-France"},
        {"label": "Provence-Alpes-Côte d'Azur", "value": "Provence-Alpes-Côte d'Azur"},
        {"label": "Auvergne-Rhône-Alpes", "value": "Auvergne-Rhône-Alpes"},
        {"label": "Occitanie", "value": "Occitanie"},
        {"label": "Nouvelle-Aquitaine", "value": "Nouvelle-Aquitaine"},
    ],
    "Greece": [
        {"label": "Attica", "value": "Attica"},
        {"label": "Central Macedonia", "value": "Central Macedonia"},
        {"label": "Crete", "value": "Crete"},
        {"label": "Western Greece", "value": "Western Greece"},
    ],
    "Hungary": [
        {"label": "Budapest", "value": "Budapest"},
        {"label": "Pest", "value": "Pest"},
        {"label": "Győr-Moson-Sopron", "value": "Győr-Moson-Sopron"},
        {"label": "Hajdú-Bihar", "value": "Hajdú-Bihar"},
    ],
    "Japan": [
        {"label": "Tokyo", "value": "Tokyo"},
        {"label": "Osaka", "value": "Osaka"},
        {"label": "Kyoto", "value": "Kyoto"},
        {"label": "Hokkaido", "value": "Hokkaido"},
        {"label": "Fukuoka", "value": "Fukuoka"},
    ],
    "Netherlands": [
        {"label": "North Holland", "value": "North Holland"},
        {"label": "South Holland", "value": "South Holland"},
        {"label": "Utrecht", "value": "Utrecht"},
        {"label": "Gelderland", "value": "Gelderland"},
    ],
    "Panama": [
        {"label": "Panamá", "value": "Panamá"},
        {"label": "Colón", "value": "Colón"},
        {"label": "Chiriquí", "value": "Chiriquí"},
        {"label": "Veraguas", "value": "Veraguas"},
    ],
    "Philippines": [
        {"label": "Metro Manila", "value": "Metro Manila"},
        {"label": "Central Luzon", "value": "Central Luzon"},
        {"label": "Calabarzon", "value": "Calabarzon"},
        {"label": "Davao Region", "value": "Davao Region"},
        {"label": "Western Visayas", "value": "Western Visayas"},
    ],
    "Poland": [
        {"label": "Mazovia", "value": "Mazovia"},
        {"label": "Silesia", "value": "Silesia"},
        {"label": "Lesser Poland", "value": "Lesser Poland"},
        {"label": "Greater Poland", "value": "Greater Poland"},
    ],
    "Singapore": [],
    "South Africa": [
        {"label": "Gauteng", "value": "Gauteng"},
        {"label": "Western Cape", "value": "Western Cape"},
        {"label": "KwaZulu-Natal", "value": "KwaZulu-Natal"},
        {"label": "Eastern Cape", "value": "Eastern Cape"},
        {"label": "Free State", "value": "Free State"},
    ],
    "Switzerland": [
        {"label": "Zurich", "value": "Zurich"},
        {"label": "Bern", "value": "Bern"},
        {"label": "Vaud", "value": "Vaud"},
        {"label": "Geneva", "value": "Geneva"},
    ],
    "United Kingdom": [
        {"label": "England", "value": "England"},
        {"label": "Scotland", "value": "Scotland"},
        {"label": "Wales", "value": "Wales"},
        {"label": "Northern Ireland", "value": "Northern Ireland"},
    ],
})

frc_games = {
        2025: {"name": "Reefscape", 
               "video": "https://www.youtube.com/watch?v=YWbxcjlY9JY", 
               "logo": "/assets/logos/2025.png", 
               "manual": "https://firstfrc.blob.core.windows.net/frc2025/Manual/2025GameManual.pdf",
               "summary": "In REEFSCAPE, alliances of three teams compete to score points by harvesting algae, placing coral on their reef, and attaching to their barge before time runs out. This game rewards creativity, strategy, and cooperation with opponents, emphasizing the core value of Coopertition."},
    
        2024: {"name": "Crescendo", 
               "video": "https://www.youtube.com/watch?v=9keeDyFxzY4", 
               "logo": "/assets/logos/2024.png", 
               "manual": "https://firstfrc.blob.core.windows.net/frc2024/Manual/2024GameManual.pdf",
               "summary": "In CRESCENDO SM presented by Haas, two competing alliances are invited to score notes, amplify their speaker, harmonize onstage, and take the spotlight before time runs out. Alliances earn additional rewards for meeting specific scoring thresholds and for cooperating with their opponents."},
    
        2023: {"name": "Charged Up", 
               "video": "https://www.youtube.com/watch?v=0zpflsYc4PA", 
               "logo": "/assets/logos/2023.png", 
               "manual": "https://firstfrc.blob.core.windows.net/frc2023/Manual/2023FRCGameManual.pdf",
               "summary": "In CHARGED UP, two competing alliances are invited to process game pieces (cubes and cones) to bring energy to their community. Each alliance brings energy to their community by retrieving their game pieces from substations and scoring it into the grid. Human players provide the game pieces to the robots from the substations. In the final moments of each match, alliance robots race to dock or engage with their charge station, a seesaw structure!"},
    
        2022: {"name": "Rapid React", 
               "video": "https://www.youtube.com/watch?v=LgniEjI9cCM", 
               "logo": "/assets/logos/2022.png", 
               "manual": "https://firstfrc.blob.core.windows.net/frc2022/Manual/2022FRCGameManual.pdf",
               "summary": "In RAPID REACT, two competing alliances process cargo for transportation. Each alliance is assigned a cargo color (red or blue) to process by retrieving their assigned cargo and scoring it into the hub. Human players assist the cargo retrieval and scoring efforts from within their terminals. In the final moments of each match, alliance robots race to engage with their hangar to prepare for transport!"},
    
        2021: {"name": "Infinite Recharge 2", 
               "video": "https://www.youtube.com/watch?v=I77Dz9pfds4", 
               "logo": "/assets/logos/2021.png", 
               "manual": "https://firstfrc.blob.core.windows.net/frc2021/Manual/2021AtHomeChallengesManual.pdf",
               "summary": "In INFINITE RECHARGE, two alliances work to protect FIRST City from approaching asteroids caused by a distant space skirmish. Each Alliance, along with their trusty droids, race to collect and score Power Cells in order to energize their Shield Generator for maximum protection. To activate stages of the Shield Generator, droids manipulate their Control Panels after scoring a specific number of Power Cells. Near the end of the match, droids race to their Rendezvous Point to get their Shield Generator operational in order to protect the city!"},
    
        2020: {"name": "Infinite Recharge", 
               "video": "https://www.youtube.com/watch?v=gmiYWTmFRVE", 
               "logo": "/assets/logos/2020.png", 
               "manual": "https://firstfrc.blob.core.windows.net/frc2020/Manual/2020FRCGameSeasonManual.pdf",
               "summary": "In INFINITE RECHARGE, two alliances work to protect FIRST City from approaching asteroids caused by a distant space skirmish. Each Alliance, along with their trusty droids, race to collect and score Power Cells in order to energize their Shield Generator for maximum protection. To activate stages of the Shield Generator, droids manipulate their Control Panels after scoring a specific number of Power Cells. Near the end of the match, droids race to their Rendezvous Point to get their Shield Generator operational in order to protect the city!"},
    
        2019: {"name": "Destination: Deep Space", 
               "video": "https://www.youtube.com/watch?v=Mew6G_og-PI", 
               "logo": "/assets/logos/2019.png", 
               "manual": "https://firstfrc.blob.core.windows.net/frc2019/Manual/2019FRCGameSeasonManual.pdf",
               "summary": "Destination: Deep Space involves two alliances of three teams each, with each team controlling a robot and performing specific tasks on a field to score points. The game centers around an outer space theme involving two alliances consisting of three teams each competing to place poly-carbonate hatch panels and orange rubber balls or cargo on rockets and cargo ships before returning to their HAB platform to climb at the end of the match."},
    
        2018: {"name": "FIRST Power Up", 
               "video": "https://www.youtube.com/watch?v=HZbdwYiCY74", 
               "logo": "/assets/logos/2018.png", 
               "manual": "https://firstfrc.blob.core.windows.net/frc2018/Manual/2018FRCGameSeasonManual.pdf",
               "summary": "FIRST Power Up involves two alliances of three teams each, with each team controlling a robot and performing specific tasks on a field to score points. The game has a retro 8-bit theme and teams are required to place milk crates, or power cubes, on large balancing scales to tip the scale and gain ownership. Alliances can also trade power cubes for power ups, giving them a temporary advantage in a match. At the end of the match, robots can climb the tower attached to the centre balancing scale using a rung attached to the tower, giving them additional points."},
    
        2017: {"name": "FIRST Steamworks", 
               "video": "https://www.youtube.com/watch?v=EMiNmJW7enI", 
               "logo": "/assets/logos/2017.png", 
               "manual": "https://firstfrc.blob.core.windows.net/frc2017/Manual/2017FRCGameSeasonManual.pdf",
               "summary": "FIRST Steamworks has a steampunk theme and teams are required to shoot wiffle balls which represent fuel into a simulated boiler which transfers the generated steam into an airship in the middle of the field. Each alliance has one airship, which they pressurize with steam from the boiler and load with plastic gears from the field. At the end of the match, robots can climb and hang on team-supplied ropes (or standard ropes supplied by FIRST) attached to the airship for additional points."},
    
        2016: {"name": "FIRST Stronghold", 
               "video": "https://www.youtube.com/watch?v=VqOKzoHJDjA", 
               "logo": "/assets/logos/2016.png", 
               "manual": "https://firstfrc.blob.core.windows.net/frc2016manuals/GameManual/FRC-2016-game-manual.pdf",
               "summary": "FIRST Stronghold was played by two alliances of up to three teams each, and involves breaching the opponents' defenses, known as outer work as well as capturing their tower by first firing boulders (small foam balls) at it, and then surrounding or scaling the tower using a singular rung on the tower wall. Points were scored by crossing elements of the tower's outer works, shooting boulders into the opposing tower's five goals in order to lower the tower strength, and by surrounding and scaling the tower."},
    
        2015: {"name": "Recycle Rush", 
               "video": "https://www.youtube.com/watch?v=W6UYFKNGHJ8", 
               "logo": "/assets/logos/2015.png", 
               "manual": "https://www.firstinspires.org/sites/default/files/uploads/resource_library/frc/game-and-season-info/archive/2015/GameManual20150407.pdf",
               "summary": "Recycle Rush involves picking up and stacking totes on scoring platforms, putting pool noodles (litter) inside recycling containers, and putting the containers on top of scoring stacks of totes. There is also a coopertition aspect of the game where both alliances of teams can pool their totes and stack them on a step dividing the field to each gain twenty points. Along with these robot actions, human players can attempt to throw the pool noodles across the field to gain four points for each noodle left in the opposing alliance's work zone."},
    
        2014: {"name": "Aerial Assist", 
               "video": "https://www.youtube.com/watch?v=oxp4dkMQ1Vo", 
               "logo": "/assets/logos/2014.png", 
               "manual": "https://www.firstinspires.org/sites/default/files/uploads/resource_library/frc/game-and-season-info/archive/2014/2014-game-manual.pdf",
               "summary": "In Aerial Assist, two alliances win via getting the scoring elements (2-foot diameter exercise balls) into the scoring areas located on the far end of the field. The game starts with each robots in either the White Zone (center field) or the goalie zones. They can be preloaded with 1 game ball prior to the start. The match begins with a 10-second autonomous period, where robots use the pre-programmed instructions to score points. Said points are worth 5 more during the Autonomous period, and one goal will be lit up during each half. That goal is worth 5 additional points, for a maximum total of a 10-point bonus. When Tele-op starts, a human player transfers a ball onto the playing field. The robots can then do either the basic goal score, or assist them in doing so. The recipient of the latter will earn bonus points. Throwing the ball over the truss when transferring will add 10 additional points. Having an alliance partner catch it will earn 10 more points."},
    
        2013: {"name": "Ultimate Ascent", 
               "video": "https://www.youtube.com/watch?v=itHNW2OFr4Y", 
               "logo": "/assets/logos/2013.png", 
               "manual": "https://www.firstinspires.org/sites/default/files/uploads/resource_library/frc/game-and-season-info/archive/2013/2013-game-manual.pdf",
               "summary": "Teams start with up to 2 or 3 discs on the robot at the beginning of the match. Robots which begin touching the carpet behind their colored Auto Line may have three discs; others may have only two. They can score these in autonomous or wait for the teleoperated period. Only the 6 discs of an alliance's color count when scored on top of its pyramid. White or opposing colored discs will not count if scored in the pyramid. Since the human players may not put any colored discs in play until teleoperated, scoring in the pyramid is not possible in autonomous. The match ends with robots attempting to climb pyramid game elements located on the field. Robots earn points by climbing the pyramid based on how high they climb. Levels are divided by the horizontal bars on the pyramid, with from the ground to the first bar being level 1."},
    
        2012: {"name": "Rebound Rumble", 
               "video": "https://www.youtube.com/watch?v=gYWscqruBRA", 
               "logo": "/assets/logos/2012.png", 
               "manual": "https://www.firstinspires.org/sites/default/files/uploads/resource_library/frc/game-and-season-info/archive/2012/2012-frc-competition-manual-game-sec1-5.pdf",
               "summary": "In the 2012 game, Rebound Rumble, two Alliances of three teams compete by trying to score as many basketballs in the hoops as possible during the two-minute and 15-second match. Balls scored in higher hoops score Alliances more points. Alliances are awarded bonus points if they are balanced on bridges at the end of the match. In matches where opponent Alliances work together to balance on the white Coopertition bridge, all participating teams earn additional valuable seeding points."},
    
        2011: {"name": "Logo Motion", 
               "video": "https://www.youtube.com/watch?v=aH_9QHZpsfs", 
               "logo": "/assets/logos/2011.png",
               "manual": "https://www.firstinspires.org/sites/default/files/uploads/resource_library/frc/game-and-season-info/archive/2011/2011-logomotion-game-manual.pdf",
               "summary": "In the 2011 game, LOGO MOTION™, two alliances of three teams compete on a 27-by-54-foot field with poles, attempting to earn points by hanging as many triangle, circle, and square logo pieces as possible. Bonus points are earned for each robot that can hang and assemble logo pieces to form the FIRST logo. Robots can also deploy Mini-Bots to climb vertical poles for a chance to earn additional points."},
    
        2010: {"name": "Breakaway", 
               "video": "https://www.youtube.com/watch?v=Bb1P43OSfOU", 
               "logo": "/assets/logos/2010.png", 
               "manual": "https://www.firstinspires.org/sites/default/files/uploads/resource_library/frc/game-and-season-info/archive/2010/2010-breakaway-complete-manual.pdf",
               "summary": "In the 2010 game, BREAKAWAY, two alliances of three teams compete on a 27-by-54-foot field with bumps, attempting to earn points by collecting soccer balls in goals. Additional bonus points are earned for each robot suspended in air and not touching the field at the end of the match."},
    
        2009: {"name": "Lunacy", 
               "video": "https://www.youtube.com/watch?v=nEh3Wzd1jDI", 
               "logo": "/assets/logos/2009.png", 
               "manual": "https://www.firstinspires.org/sites/default/files/uploads/resource_library/frc/game-and-season-info/archive/2009/2009-lunacy-complete-manual.pdf",
               "summary": "In the 2009 game, LUNACY, robots are designed to pick up 9-inch game balls and score them in trailers hitched to their opponents robots for points during a 2 minute and 15 second match. Additional points are awarded for scoring a special game ball, the Super Cell, in the opponents' trailers during the last 20 seconds of the match. LUNACY is played on a low-friction floor, which means teams must contend with the laws of physics."},
    
        2008: {"name": "FIRST Overdrive", 
               "video": "https://www.youtube.com/watch?v=D5oL7aLH0T4", 
               "logo": "/assets/logos/2008.png", 
               "manual": "https://www.firstinspires.org/sites/default/files/uploads/resource_library/frc/game-and-season-info/archive/2008/2008-overdrive-manual.pdf",
               "summary": "In the 2008 game, FIRST Overdrive, students' robots are designed to race around a track knocking down 40 inch inflated Trackballs and moving them around the track, passing them either over or under a 6.5 foot overpass. Extra points are scored by robots positioning the Trackballs back on the overpass before the end of the 2 minute and 15 second match."},
    
        2007: {"name": "Rack 'N' Roll", 
               "video": "https://www.youtube.com/watch?v=khTGSKvDyS4", 
               "logo": "/assets/logos/2007.png", 
               "manual": "https://www.firstinspires.org/sites/default/files/uploads/resource_library/frc/game-and-season-info/archive/2007/2007-racknroll-manual.pdf",
               "summary": "In the 2007 game, Rack N Roll, students robots are designed to hang inflated colored tubes on pegs configured in rows and columns on a 10-foot high center rack structure. Extra points are scored by robots being in their home zone and lifted more than 4 inches off the floor by another robot before the end of the 2 minute and 15 second match."},
    
        2006: {"name": "Aim High", 
               "video": "https://www.youtube.com/watch?v=1Vuwjse90AA", 
               "logo": "/assets/logos/2006.png", 
               "manual": "Not Available",
               "summary": "In the 2006 game, Aim High, students robots are designed to launch balls into goals while human players enter balls into play and score points by throwing/pushing balls into corner goals. Extra points are scored by robots racing back to their end zones and climbing the ramp to the platform before the end of the 2 minute and 10 second match."},
    
        2005: {"name": "Triply Play", 
               "video": "https://www.youtube.com/watch?v=6ePwDtrthWE", 
               "logo": "/assets/logos/2005.png", 
               "manual": "https://www.firstinspires.org/sites/default/files/uploads/resource_library/frc/game-and-season-info/archive/2005/2005-the-game.pdf",
               "summary": "Triply Play was played on a 27 foot wide by 52 foot long playing field with the 9 goals configured in 3 x 3 matrix, similar to tic-tac-toe. The robots will attempt to place the red and blue game tetras in or on one or more of the nine goals to score points and claim ownership of the goals."},
    
        2004: {"name": "FIRST Frenzy", 
               "video": "https://www.youtube.com/watch?v=JIGggWdMekk", 
               "logo": "/assets/logos/2004.png", 
               "manual": "https://www.firstinspires.org/sites/default/files/uploads/resource_library/frc/game-and-season-info/archive/2004/2004-the-game.pdf",
               "summary": "The game for the 2004 season requires robots to collect and pass 13 inch balls to the human player to then shoot them into fixed and moveable goals. There are three 30 inch balls on the playing field that can be placed on top of any goal by a robot, which will double the point value in the goal. Additionally, robots may attempt to hang from a 10 foot bar."},
    
        2003: {"name": "Stack Attack", 
               "video": "https://www.youtube.com/watch?v=lEefJljqyQU", 
               "logo": "/assets/logos/2003.png", 
               "manual": "https://www.firstinspires.org/sites/default/files/uploads/resource_library/frc/game-and-season-info/archive/2003/2003-the-game.pdf",
               "summary": "The game for the 2003 season requires robots to collect and stack plastic storage containers on their side of the playing field. The location of the robots and containers and the height of the stacks at the end of the match determine each team's score for the round."},
    
        2002: {"name": "Zone Zeal", 
               "video": "https://www.youtube.com/watch?v=GkgDoF0hnrI", 
               "logo": "/assets/logos/2002.png", 
               "manual": "https://www.firstinspires.org/sites/default/files/uploads/resource_library/frc/game-and-season-info/archive/2002/2002-game-manual.pdf",  
               "summary": "Each 2 minute match begins with the 24ft x 48ft field broken up into 5 zones. Four robots start on the playing field and are paired in alliances of 2. There are 2 robots at diagonally opposite corners, 10 soccer balls in each driver station area, 20 soccer balls centered along each side of the field, and 3 moveable goals weighing approximately 130 lbs each in the center zone. Robots race around the playing field trying to gather balls, place them into goals, place the goals in their scoring zone, and return their robot to their starting zone before the 2 minutes have elapsed."},
    
        2001: {"name": "Diabolical Dynamics", 
               "video": "https://www.youtube.com/watch?v=m1vkEKM7wKE", 
               "logo": "/assets/logos/2001.png", 
               "manual": "Not Available", 
               "summary": "A four-team alliances tries to achieve as high a score as possible in each match. Points are scored by placing balls in their goal, and by positioning their robots and goals in designated areas at the end of each match. At the start of each match, the alliance station contains twenty small balls. In addition there are twenty small balls and four large balls on the far side of the field which may be used to score points. At the end of the two minute match, the alliance will receive one point for each small ball in the goal and not in contact with a robot, and ten points for each large ball in the goal and not in contact with a robot. Each alliance will receive ten points for each robot that is in the End Zone. An additional ten points will be added if the stretcher is in the End Zone. The alliance doubles its score if the bridge is balanced. The alliance multiplies its score by a factor of up to three by ending the match before the two minute time limit. Each team receives the alliance score. A team multiplies its' score by 1.1 if its large ball is on top of a goal. Scores are rounded up to the nearest whole point after applying all applicable multipliers."},
    
        2000: {"name": "Co-opertition FIRST", 
               "video": "https://www.youtube.com/watch?v=_FJFbvHRyco", 
               "logo": "/assets/logos/2000.png", 
               "manual": "Not Available", 
               "summary": "Four teams, paired in two alliances, will compete in each match. An alliance scores points by placing balls in their goal, and by positioning their robots in designated areas at the end of each match. At the start of a match each alliance has seven yellow balls and one black ball in their station. In addition, there are fifteen yellow balls and two black balls on the far side of the field which may be scored by either alliance."},
    
        1999: {"name": "Double Trouble", 
               "video": "https://www.youtube.com/watch?v=Q0CDop_IwW8", 
               "logo": "/assets/logos/1999.png", 
               "manual": "Not Available", 
               "summary": "Points are scored by positioning floppies, robots, and the puck on the playing field. Floppies are light weight, pillow-like objects with Velcro-loop material located in the center and around the perimeter. Each alliance has ten color coded floppies located on the playing field and at the player stations. At the end of each two minute match, points are awarded as follows: Each two-team alliance will receive one point for each of its floppies that is at least 2 inches over and not touching the playing field surface, and less than eight feet above the surface of the playing field. Each alliance will receive three points for each of its floppies eight feet or higher over the surface of the playing field. Any robot that climbs onto the puck will multiply its alliance's score by three."},
    
        1998: {"name": "Ladder Logic", 
               "video": "https://www.youtube.com/watch?v=GKcxG8tIXSY", 
               "logo": "/assets/logos/1998.png", 
               "manual": "Not Available", 
               "summary": "In two minutes matches, the three robots and human players score points by placing the balls onto the side goals or into the central goal. The balls are color-coded to identify team ownership. A human player, located outside the perimeter of the field, is allowed to hand balls to the robot or throw balls directly at the goals."},
    
        1997: {"name": "Toroid Terror", 
               "video": "https://www.youtube.com/watch?v=nf0j0ztIsOE", 
               "logo": "/assets/logos/1997.png", 
               "manual": "Not Available", 
               "summary": "In two minute matches, the three robots and human players score points by placing the inner tubes onto pegs in the goal, or around the top of the goal. The tubes are color coded to identify team ownership. Human players are not allowed onto the field, but they may hand tubes to the robots or throw tubes directly onto the goal."},
    
        1996: {"name": "Hexagon Havoc", 
               "video": "https://www.youtube.com/watch?v=T8N6lnle1fc", 
               "logo": "/assets/logos/1996.png", 
               "manual": "Not Available", 
               "summary": "In two minute matches, the three robots, with their human partners, score points by placing the balls in the central goal. The balls may be carried, pushed or thrown into the goal by the robots. The human players are not allowed on the playing field as they are seat-belted down at their stations, but they may score points by throwing ball(s) into the central goal. Points are awarded for balls located in the central goal at the conclusion of each two minute match."},
    
        1995: {"name": "Ramp N' Roll", 
               "video": "https://www.youtube.com/watch?v=6yJ4suxGFFg", 
               "logo": "/assets/logos/1995.png", 
               "manual": "Not Available", 
               "summary": "In two minute matches, three robots race down a 30-foot raceway, over a speed bump just wide enough for two to pass through, to retrieve their 24 inch and 30 inch vinyl balls. To score, they must carry the ball(s) back up the raceway and push or shoot the ball over a nine-foot field goal from either the playing floor or a raised platform area, all the while trying to keep their opponents from scoring. Teams may score more than once with each ball – the smaller ball is worth two points and the larger ball is worth three points."},
    
        1994: {"name": "Tower Power", 
               "video": "https://www.youtube.com/watch?v=-AzPVqxFX4k", 
               "logo": "/assets/logos/1994.png", 
               "manual": "Not Available", 
               "summary": "Contestants attempt to place as many of their soccer balls possible inside one of two goals. In each match, three-team alliances compete to place 12 balls of their team color inside either the high goal, worth 3 points, or in the low goal, worth one point per ball. The winner is the team that has the highest total point value of soccer balls within the two goals at the end of the two minute match. In the case of a tie, the team with more balls in the upper goal wins."},
    
        1993: {"name": "Rug Rage", 
               "video": "https://www.youtube.com/watch?v=1rZyU9Xu8GE", 
               "logo": "/assets/logos/1993.png", 
               "manual": "Not Available", 
               "summary": "Contestants attempt to collect balls from either the playing field or their opponents' goals, place them in their own goals, and defend them. There are five large air-filled kick balls each worth five points, and twenty smaller water-filled balls worth one point each. The winner is the team with the highest total point value of balls within their foal at the conclusion of a two minute match. In the case of a tie, the team with the most large balls wins. If still a tie, the team which collected their balls first wins."},
    
        1992: {"name": "Maize Craze", 
               "video": "https://www.youtube.com/watch?v=0-m1QBOxsfg", 
               "logo": "/assets/logos/1992.png", 
               "manual": "Not Available", 
               "summary": "Four contestants vie in a round to see who can collect the highest point value total of tennis balls, return to home base, and defend their cache successfully. Each round is two minutes long. The game is played on a 16-foot X 16-foot square playing arena covered with 1.5 inch layer of whole corn kernels."}
    }

DISTRICT_STATES = {
    "ONT": ["Ontario"],
    "FMA": ["Delaware", "New Jersey", "Pennsylvania"],
    "ISR": ["Israel"],
    "CHS": ["Maryland", "Virginia", "District of Columbia"],
    "FIT": ["Texas", "New Mexico"],
    "PCH": ["Georgia"],
    "PNW": ["Washington", "Oregon"],
    "FIM": ["Michigan"],
    "FSC": ["South Carolina"],
    "FNC": ["North Carolina"],
    "FIN": ["Indiana"],
    "NE": ["Connecticut", "Massachusetts", "Maine", "New Hampshire", "Vermont"],
}