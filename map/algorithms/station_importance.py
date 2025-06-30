import math
import sys
import os
from typing import List, Dict, Tuple
from collections import defaultdict

# Add current directory to path for wikipedia_ridership import
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from wikipedia_ridership import (
        load_ridership_database, 
        calculate_ridership_score_with_wikipedia,
        KNOWN_RIDERSHIP_DATA,
        get_ridership_for_stations,
        save_ridership_database
    )
except ImportError:
    # Fallback if wikipedia_ridership is not available
    print("Warning: Wikipedia ridership module not available, using basic estimation")
    def load_ridership_database():
        return {}
    def calculate_ridership_score_with_wikipedia(name, db):
        return 50  # Default score
    KNOWN_RIDERSHIP_DATA = {}
    def get_ridership_for_stations(stations):
        return {}
    def save_ridership_database(db):
        pass

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * 
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def get_station_type_score(station_name: str) -> Tuple[int, str]:
    """
    Determine station type and base importance score from name patterns.
    Returns (score, type)
    """
    name_lower = station_name.lower()
    
    # Major terminals and junctions (highest importance)
    if any(keyword in name_lower for keyword in ['central', 'terminal', 'terminus']):
        return (100, 'terminal')
    
    # Junctions (high connectivity)
    if any(keyword in name_lower for keyword in ['jn', 'junction']):
        return (80, 'junction')
    
    # Cantonment stations (often important)
    if any(keyword in name_lower for keyword in ['cantt', 'cantonment']):
        return (70, 'cantonment')
    
    # City stations (urban importance)
    if any(keyword in name_lower for keyword in ['city', 'town', 'nagar']):
        return (60, 'city')
    
    # Main stations
    if 'main' in name_lower:
        return (50, 'main')
    
    # Regular stations
    return (30, 'regular')

def calculate_connectivity_score(station: Dict, all_stations: List[Dict], tracks: List[Dict]) -> int:
    """
    Calculate connectivity score based on number of nearby stations and track connections.
    Higher score indicates better connectivity.
    """
    station_lat, station_lon = station['lat'], station['lon']
    connectivity_score = 0
    
    # Count nearby stations (within different distance ranges)
    nearby_counts = {'close': 0, 'medium': 0, 'far': 0}
    
    for other_station in all_stations:
        if other_station == station:
            continue
        
        distance = calculate_distance(station_lat, station_lon, 
                                    other_station['lat'], other_station['lon'])
        
        if distance <= 5:  # Within 5km
            nearby_counts['close'] += 1
        elif distance <= 15:  # Within 15km
            nearby_counts['medium'] += 1
        elif distance <= 50:  # Within 50km
            nearby_counts['far'] += 1
    
    # Weight the connectivity (closer stations matter more)
    connectivity_score = (nearby_counts['close'] * 10 + 
                         nearby_counts['medium'] * 5 + 
                         nearby_counts['far'] * 2)
    
    # Count track connections (tracks passing near the station)
    track_connections = 0
    for track in tracks:
        for coord in track['coords']:
            distance = calculate_distance(station_lat, station_lon, coord[0], coord[1])
            if distance <= 2:  # Within 2km of track
                track_connections += 1
                break  # Count each track only once
    
    connectivity_score += track_connections * 5
    
    return min(connectivity_score, 100)  # Cap at 100

def calculate_urban_importance(station: Dict) -> int:
    """
    Calculate importance based on proximity to major urban centers.
    """
    station_lat, station_lon = station['lat'], station['lon']
    
    # Major South Indian cities with population-based importance weights
    major_cities = [
        {'name': 'Chennai', 'lat': 13.0827, 'lon': 80.2707, 'weight': 100, 'radius': 50},
        {'name': 'Bangalore', 'lat': 12.9716, 'lon': 77.5946, 'weight': 95, 'radius': 50},
        {'name': 'Hyderabad', 'lat': 17.3850, 'lon': 78.4867, 'weight': 90, 'radius': 50},
        {'name': 'Kochi', 'lat': 9.9312, 'lon': 76.2673, 'weight': 70, 'radius': 30},
        {'name': 'Coimbatore', 'lat': 11.0168, 'lon': 76.9558, 'weight': 65, 'radius': 30},
        {'name': 'Vijayawada', 'lat': 16.5062, 'lon': 80.6480, 'weight': 60, 'radius': 30},
        {'name': 'Mysore', 'lat': 12.2958, 'lon': 76.6394, 'weight': 55, 'radius': 25},
        {'name': 'Madurai', 'lat': 9.9252, 'lon': 78.1198, 'weight': 55, 'radius': 25},
        {'name': 'Tiruchirappalli', 'lat': 10.7905, 'lon': 78.7047, 'weight': 50, 'radius': 25},
        {'name': 'Salem', 'lat': 11.6643, 'lon': 78.1460, 'weight': 45, 'radius': 20},
        {'name': 'Tirunelveli', 'lat': 8.7139, 'lon': 77.7567, 'weight': 40, 'radius': 20},
        {'name': 'Vellore', 'lat': 12.9165, 'lon': 79.1325, 'weight': 35, 'radius': 15},
    ]
    
    max_urban_score = 0
    
    for city in major_cities:
        distance = calculate_distance(station_lat, station_lon, city['lat'], city['lon'])
        
        if distance <= city['radius']:
            # Score decreases with distance from city center
            distance_factor = max(0, 1 - (distance / city['radius']))
            urban_score = city['weight'] * distance_factor
            max_urban_score = max(max_urban_score, urban_score)
    
    return int(max_urban_score)

def calculate_strategic_importance(station: Dict, station_name: str) -> int:
    """
    Calculate strategic importance based on known railway strategic factors.
    """
    name_lower = station_name.lower()
    strategic_score = 0
    
    # Port cities (important for freight)
    port_keywords = ['port', 'harbour', 'harbor', 'dock', 'marine']
    if any(keyword in name_lower for keyword in port_keywords):
        strategic_score += 30
    
    # Border/gateway stations
    border_keywords = ['border', 'frontier', 'gateway']
    if any(keyword in name_lower for keyword in border_keywords):
        strategic_score += 25
    
    # Tourist destinations
    tourist_keywords = ['hill', 'palace', 'temple', 'beach', 'resort', 'falls']
    if any(keyword in name_lower for keyword in tourist_keywords):
        strategic_score += 15
    
    # Industrial areas
    industrial_keywords = ['steel', 'iron', 'mill', 'factory', 'industrial', 'chemical']
    if any(keyword in name_lower for keyword in industrial_keywords):
        strategic_score += 20
    
    # Educational hubs
    education_keywords = ['university', 'college', 'institute', 'iit', 'iisc']
    if any(keyword in name_lower for keyword in education_keywords):
        strategic_score += 10
    
    return strategic_score

def estimate_ridership_score(station: Dict, station_name: str, connectivity_score: int, urban_score: int, ridership_database: Dict = None) -> int:
    """
    Estimate ridership importance using actual Wikipedia data if available,
    otherwise fall back to heuristic estimation.
    """
    # Use Wikipedia ridership data if available
    if ridership_database and station_name in ridership_database:
        return calculate_ridership_score_with_wikipedia(station_name, ridership_database)
    
    # Check known ridership data
    if station_name in KNOWN_RIDERSHIP_DATA:
        temp_db = {station_name: KNOWN_RIDERSHIP_DATA[station_name]}
        return calculate_ridership_score_with_wikipedia(station_name, temp_db)
    
    # Fall back to heuristic estimation
    name_lower = station_name.lower()
    
    # Base ridership estimation
    base_ridership = 0
    
    # Station type influences ridership
    if any(keyword in name_lower for keyword in ['central', 'terminal', 'main']):
        base_ridership = 80
    elif any(keyword in name_lower for keyword in ['jn', 'junction']):
        base_ridership = 70
    elif any(keyword in name_lower for keyword in ['city', 'cantt']):
        base_ridership = 60
    else:
        base_ridership = 30
    
    # Connectivity and urban proximity strongly correlate with ridership
    connectivity_factor = min(connectivity_score / 2, 20)  # Up to 20 points
    urban_factor = min(urban_score / 3, 30)  # Up to 30 points
    
    total_ridership_score = base_ridership + connectivity_factor + urban_factor
    
    return min(total_ridership_score, 100)

def calculate_station_importance(station: Dict, all_stations: List[Dict], tracks: List[Dict], ridership_database: Dict = None) -> Dict:
    """
    Calculate comprehensive importance score for a railway station.
    Returns detailed scoring breakdown.
    """
    station_name = station.get('name', 'Unknown')
    
    # Get base type score
    type_score, station_type = get_station_type_score(station_name)
    
    # Calculate individual component scores
    connectivity_score = calculate_connectivity_score(station, all_stations, tracks)
    urban_score = calculate_urban_importance(station)
    strategic_score = calculate_strategic_importance(station, station_name)
    ridership_score = estimate_ridership_score(station, station_name, connectivity_score, urban_score, ridership_database)
    
    # Weighted total importance score
    # Increase ridership weight since we now have real data for many stations
    weights = {
        'type': 0.15,
        'connectivity': 0.20,
        'urban': 0.20,
        'strategic': 0.15,
        'ridership': 0.30  # Increased weight for actual ridership data
    }
    
    total_score = (type_score * weights['type'] + 
                  connectivity_score * weights['connectivity'] + 
                  urban_score * weights['urban'] + 
                  strategic_score * weights['strategic'] + 
                  ridership_score * weights['ridership'])
    
    # Determine importance category
    if total_score >= 80:
        importance_category = 'critical'
    elif total_score >= 65:
        importance_category = 'major'
    elif total_score >= 50:
        importance_category = 'important'
    elif total_score >= 35:
        importance_category = 'moderate'
    elif total_score >= 20:
        importance_category = 'minor'
    else:
        importance_category = 'local'
    
    # Add ridership data source info if available
    ridership_source = 'estimated'
    actual_ridership = None
    
    if ridership_database and station_name in ridership_database:
        ridership_source = 'wikipedia'
        actual_ridership = ridership_database[station_name].get('daily_passengers')
    elif station_name in KNOWN_RIDERSHIP_DATA:
        ridership_source = 'known_data'
        actual_ridership = KNOWN_RIDERSHIP_DATA[station_name].get('daily_passengers')
    
    result = {
        'importance_score': round(total_score, 1),
        'importance_category': importance_category,
        'station_type': station_type,
        'component_scores': {
            'type_score': type_score,
            'connectivity_score': connectivity_score,
            'urban_score': urban_score,
            'strategic_score': strategic_score,
            'ridership_score': ridership_score
        },
        'weights_used': weights,
        'ridership_source': ridership_source
    }
    
    if actual_ridership:
        result['actual_daily_ridership'] = actual_ridership
    
    return result

def rank_stations_by_importance(infrastructure: Dict) -> Dict:
    """
    Rank all stations by importance and add rankings to the infrastructure data.
    Now includes Wikipedia ridership data collection.
    """
    all_stations = infrastructure.get('stations', []) + infrastructure.get('major_stations', [])
    tracks = infrastructure.get('tracks', [])
    
    print(f"Calculating importance rankings for {len(all_stations)} stations...")
    
    # Load existing ridership database
    ridership_database = load_ridership_database()
    print(f"Loaded existing ridership data for {len(ridership_database)} stations")
    
    # For major stations without ridership data, try to fetch from Wikipedia
    major_stations_without_data = []
    for station in all_stations:
        station_name = station.get('name', 'Unknown')
        if (station_name != 'Unknown' and 
            station_name not in ridership_database and 
            station_name not in KNOWN_RIDERSHIP_DATA):
            # Prioritize major stations for Wikipedia lookup
            if any(keyword in station_name.lower() for keyword in 
                   ['central', 'junction', 'jn', 'terminal', 'main', 'city', 'cantt']):
                major_stations_without_data.append(station)
    
    # Limit Wikipedia lookups to avoid overwhelming the service
    if major_stations_without_data:
        print(f"Found {len(major_stations_without_data)} major stations without ridership data")
        # Limit to top 50 major stations to be respectful to Wikipedia
        stations_to_lookup = major_stations_without_data[:50]
        print(f"Fetching Wikipedia data for {len(stations_to_lookup)} stations...")
        
        new_ridership_data = get_ridership_for_stations(stations_to_lookup)
        ridership_database.update(new_ridership_data)
        
        # Save updated database
        save_ridership_database(ridership_database)
    
    # Calculate importance for each station
    station_importance = []
    
    for i, station in enumerate(all_stations):
        if i % 50 == 0:
            print(f"  Processing station {i+1}/{len(all_stations)}")
        
        importance_data = calculate_station_importance(station, all_stations, tracks, ridership_database)
        
        # Add importance data to station
        station.update(importance_data)
        
        station_importance.append({
            'station': station,
            'score': importance_data['importance_score']
        })
    
    # Sort by importance score (descending)
    station_importance.sort(key=lambda x: x['score'], reverse=True)
    
    # Add rankings
    for rank, item in enumerate(station_importance, 1):
        item['station']['importance_rank'] = rank
        item['station']['importance_percentile'] = round((len(all_stations) - rank + 1) / len(all_stations) * 100, 1)
    
    # Generate statistics
    category_counts = defaultdict(int)
    type_counts = defaultdict(int)
    score_ranges = defaultdict(int)
    ridership_sources = defaultdict(int)
    
    for station in all_stations:
        category_counts[station.get('importance_category', 'unknown')] += 1
        type_counts[station.get('station_type', 'unknown')] += 1
        ridership_sources[station.get('ridership_source', 'unknown')] += 1
        
        score = station.get('importance_score', 0)
        score_range = f"{(int(score) // 10) * 10}-{((int(score) // 10) + 1) * 10}"
        score_ranges[score_range] += 1
    
    # Add statistics to infrastructure
    infrastructure['station_rankings'] = {
        'total_stations': len(all_stations),
        'category_distribution': dict(category_counts),
        'type_distribution': dict(type_counts),
        'score_distribution': dict(score_ranges),
        'ridership_data_sources': dict(ridership_sources),
        'wikipedia_stations': len([s for s in all_stations if s.get('ridership_source') == 'wikipedia']),
        'known_data_stations': len([s for s in all_stations if s.get('ridership_source') == 'known_data']),
        'top_10_stations': [
            {
                'name': item['station']['name'],
                'score': item['score'],
                'category': item['station']['importance_category'],
                'type': item['station']['station_type'],
                'state': item['station'].get('state', 'Unknown'),
                'ridership_source': item['station'].get('ridership_source', 'estimated'),
                'daily_ridership': item['station'].get('actual_daily_ridership', 'N/A')
            }
            for item in station_importance[:10]
        ],
        'average_score': sum(s.get('importance_score', 0) for s in all_stations) / max(len(all_stations), 1)
    }
    
    print(f"Station importance ranking complete!")
    print(f"  Average importance score: {infrastructure['station_rankings']['average_score']:.1f}")
    print(f"  Categories: {dict(category_counts)}")
    print(f"  Ridership data sources: {dict(ridership_sources)}")
    print(f"  Top 3 stations: {[s['name'] for s in infrastructure['station_rankings']['top_10_stations'][:3]]}")
    
    return infrastructure
