import math
import sys
import os
from typing import List, Dict, Tuple
from collections import defaultdict

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

def estimate_ridership_score(station: Dict, station_name: str, connectivity_score: int, urban_score: int) -> int:
    """
    Estimate ridership importance using heuristic estimation based on station characteristics.
    """
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

def calculate_station_importance(station: Dict, all_stations: List[Dict], tracks: List[Dict]) -> Dict:
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
    ridership_score = estimate_ridership_score(station, station_name, connectivity_score, urban_score)
    
    # Weighted total importance score
    weights = {
        'type': 0.20,
        'connectivity': 0.25,
        'urban': 0.25,
        'strategic': 0.15,
        'ridership': 0.15
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
        'weights_used': weights
    }
    
    return result

def rank_stations_by_importance(infrastructure: Dict) -> Dict:
    """
    Rank all stations by importance and add rankings to the infrastructure data.
    """
    all_stations = infrastructure.get('stations', []) + infrastructure.get('major_stations', [])
    tracks = infrastructure.get('tracks', [])
    
    print(f"Calculating importance rankings for {len(all_stations)} stations...")
    
    # Calculate importance for each station
    station_importance = []
    
    for i, station in enumerate(all_stations):
        if i % 50 == 0:
            print(f"  Processing station {i+1}/{len(all_stations)}")
        
        importance_data = calculate_station_importance(station, all_stations, tracks)
        
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
    
    for station in all_stations:
        category_counts[station.get('importance_category', 'unknown')] += 1
        type_counts[station.get('station_type', 'unknown')] += 1
        
        score = station.get('importance_score', 0)
        score_range = f"{(int(score) // 10) * 10}-{((int(score) // 10) + 1) * 10}"
        score_ranges[score_range] += 1
    
    # Add statistics to infrastructure
    infrastructure['station_rankings'] = {
        'total_stations': len(all_stations),
        'category_distribution': dict(category_counts),
        'type_distribution': dict(type_counts),
        'score_distribution': dict(score_ranges),
        'top_10_stations': [
            {
                'name': item['station']['name'],
                'score': item['score'],
                'category': item['station']['importance_category'],
                'type': item['station']['station_type'],
                'state': item['station'].get('state', 'Unknown')
            }
            for item in station_importance[:10]
        ],
        'average_score': sum(s.get('importance_score', 0) for s in all_stations) / max(len(all_stations), 1)
    }
    
    print(f"Station importance ranking complete!")
    print(f"  Average importance score: {infrastructure['station_rankings']['average_score']:.1f}")
    print(f"  Categories: {dict(category_counts)}")
    print(f"  Top 3 stations: {[s['name'] for s in infrastructure['station_rankings']['top_10_stations'][:3]]}")
    
    return infrastructure
