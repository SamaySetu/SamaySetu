import math
import numpy as np
from typing import List, Tuple, Dict

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

def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate bearing between two points in degrees"""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    
    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = (math.cos(lat1_rad) * math.sin(lat2_rad) - 
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))
    
    bearing = math.atan2(y, x)
    return (math.degrees(bearing) + 360) % 360

def calculate_curvature(coords: List[List[float]], segment_length: float = 1.0) -> float:
    """
    Calculate track curvature using bearing changes over distance.
    Returns curvature in degrees per kilometer.
    """
    if len(coords) < 3:
        return 0.0
    
    total_bearing_change = 0.0
    total_distance = 0.0
    
    for i in range(len(coords) - 2):
        # Calculate bearings for consecutive segments
        bearing1 = calculate_bearing(coords[i][0], coords[i][1], 
                                   coords[i+1][0], coords[i+1][1])
        bearing2 = calculate_bearing(coords[i+1][0], coords[i+1][1], 
                                   coords[i+2][0], coords[i+2][1])
        
        # Calculate bearing change (accounting for 360° wrap-around)
        bearing_change = abs(bearing2 - bearing1)
        if bearing_change > 180:
            bearing_change = 360 - bearing_change
        
        # Calculate distance for this segment
        distance = calculate_distance(coords[i][0], coords[i][1], 
                                    coords[i+1][0], coords[i+1][1])
        
        total_bearing_change += bearing_change
        total_distance += distance
    
    # Return curvature in degrees per kilometer
    return total_bearing_change / max(total_distance, 0.001)

def estimate_gradient(coords: List[List[float]]) -> float:
    """
    Estimate track gradient. Since OSM doesn't have elevation data,
    we use geographic heuristics and terrain patterns.
    """
    if len(coords) < 2:
        return 0.0
    
    # Basic gradient estimation based on geographic patterns
    start_lat, start_lon = coords[0]
    end_lat, end_lon = coords[-1]
    
    # Estimate elevation changes based on known geographic patterns
    # Western Ghats: steep gradients
    # Coastal plains: minimal gradients
    # Deccan plateau: moderate gradients
    
    # Western Ghats regions (approximate boundaries)
    western_ghats_regions = [
        (8.0, 77.0, 12.0, 76.0),  # Karnataka Western Ghats
        (11.0, 76.0, 12.5, 77.5),  # Tamil Nadu Western Ghats
        (8.5, 76.5, 10.5, 77.0),  # Kerala Western Ghats
    ]
    
    gradient_factor = 0.0
    
    # Check if track passes through Western Ghats
    for lat, lon in coords:
        for min_lat, min_lon, max_lat, max_lon in western_ghats_regions:
            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                gradient_factor = max(gradient_factor, 2.0)  # Steep gradient
                break
    
    # Coastal regions (flatter)
    if any(lon < 76.0 or lon > 80.0 for _, lon in coords):
        gradient_factor = min(gradient_factor, 0.5)  # Minimal gradient
    
    # Default moderate gradient for Deccan plateau
    if gradient_factor == 0.0:
        gradient_factor = 1.0
    
    return gradient_factor

def is_urban_area(lat: float, lon: float, major_cities: List[Dict]) -> bool:
    """Check if coordinates are near urban areas"""
    for city in major_cities:
        distance = calculate_distance(lat, lon, city['lat'], city['lon'])
        if distance < city.get('radius', 25):  # Default 25km radius
            return True
    return False

def calculate_speed_limit(track_segment: Dict, all_stations: List[Dict]) -> Dict:
    """
    Calculate realistic speed limit for a track segment based on multiple factors.
    Returns speed limit in km/h and classification.
    """
    coords = track_segment['coords']
    track_type = track_segment.get('type', 'other')
    electrified = track_segment.get('electrified', False)
    gauge = track_segment.get('gauge', '1676')  # Default broad gauge
    
    # Base speed limits by track type
    base_speeds = {
        'main': 130,      # Main lines (high-speed potential)
        'branch': 100,    # Branch lines
        'service': 50,    # Service/yard tracks
        'industrial': 40, # Industrial tracks
        'narrow_gauge': 80, # Narrow gauge limitations
        'other': 80       # Default
    }
    
    base_speed = base_speeds.get(track_type, 80)
    
    # Major South Indian cities for urban detection
    major_cities = [
        {'name': 'Chennai', 'lat': 13.0827, 'lon': 80.2707, 'radius': 30},
        {'name': 'Bangalore', 'lat': 12.9716, 'lon': 77.5946, 'radius': 35},
        {'name': 'Hyderabad', 'lat': 17.3850, 'lon': 78.4867, 'radius': 30},
        {'name': 'Kochi', 'lat': 9.9312, 'lon': 76.2673, 'radius': 20},
        {'name': 'Coimbatore', 'lat': 11.0168, 'lon': 76.9558, 'radius': 20},
        {'name': 'Mysore', 'lat': 12.2958, 'lon': 76.6394, 'radius': 15},
        {'name': 'Vijayawada', 'lat': 16.5062, 'lon': 80.6480, 'radius': 20},
        {'name': 'Tirunelveli', 'lat': 8.7139, 'lon': 77.7567, 'radius': 15},
    ]
    
    # Calculate factors
    curvature = calculate_curvature(coords)
    gradient = estimate_gradient(coords)
    
    # Check proximity to stations
    min_station_distance = float('inf')
    for coord in coords:
        for station in all_stations:
            distance = calculate_distance(coord[0], coord[1], 
                                        station['lat'], station['lon'])
            min_station_distance = min(min_station_distance, distance)
    
    # Check if in urban area
    urban = any(is_urban_area(coord[0], coord[1], major_cities) for coord in coords)
    
    # Apply speed reductions based on factors
    speed_limit = base_speed
    
    # Curvature factor (reduce speed for sharp curves)
    if curvature > 50:  # Very sharp curves
        speed_limit *= 0.6
    elif curvature > 20:  # Moderate curves
        speed_limit *= 0.8
    elif curvature > 10:  # Gentle curves
        speed_limit *= 0.9
    
    # Gradient factor (reduce speed for steep gradients)
    if gradient > 1.5:  # Steep gradient
        speed_limit *= 0.7
    elif gradient > 1.0:  # Moderate gradient
        speed_limit *= 0.85
    
    # Gauge factor
    if gauge and gauge != '1676':  # Non-broad gauge
        if '1000' in gauge or '762' in gauge:  # Narrow gauge
            speed_limit *= 0.7
        elif '1435' in gauge:  # Standard gauge (rare in India)
            speed_limit *= 0.9
    
    # Urban area restrictions
    if urban:
        speed_limit *= 0.7
    
    # Station proximity restrictions
    if min_station_distance < 2:  # Within 2km of station
        speed_limit *= 0.8
    elif min_station_distance < 5:  # Within 5km of station
        speed_limit *= 0.9
    
    # Electrification bonus (electrified tracks often allow higher speeds)
    if electrified and track_type in ['main', 'branch']:
        speed_limit *= 1.1
    
    # Round to nearest 5 km/h and ensure reasonable bounds
    speed_limit = max(25, min(160, round(speed_limit / 5) * 5))
    
    # Classify the speed limit
    if speed_limit >= 130:
        classification = 'high_speed'
    elif speed_limit >= 100:
        classification = 'express'
    elif speed_limit >= 80:
        classification = 'fast'
    elif speed_limit >= 60:
        classification = 'medium'
    elif speed_limit >= 40:
        classification = 'slow'
    else:
        classification = 'restricted'
    
    return {
        'speed_limit_kmh': int(speed_limit),
        'classification': classification,
        'factors': {
            'base_speed': base_speed,
            'curvature': round(curvature, 2),
            'gradient_factor': round(gradient, 2),
            'urban': urban,
            'min_station_distance_km': round(min_station_distance, 2),
            'electrified': electrified,
            'track_type': track_type,
            'gauge': gauge
        }
    }

def add_speed_limits_to_tracks(infrastructure: Dict) -> Dict:
    """Add speed limits to all track segments in the infrastructure"""
    tracks = infrastructure.get('tracks', [])
    all_stations = infrastructure.get('stations', []) + infrastructure.get('major_stations', [])
    
    print(f"Calculating speed limits for {len(tracks)} track segments...")
    
    for i, track in enumerate(tracks):
        if i % 100 == 0:
            print(f"  Processing track {i+1}/{len(tracks)}")
        
        speed_data = calculate_speed_limit(track, all_stations)
        track.update(speed_data)
    
    # Generate summary statistics
    speed_stats = {}
    classifications = {}
    
    for track in tracks:
        speed = track.get('speed_limit_kmh', 0)
        classification = track.get('classification', 'unknown')
        
        # Speed distribution
        speed_range = f"{(speed // 20) * 20}-{((speed // 20) + 1) * 20}"
        speed_stats[speed_range] = speed_stats.get(speed_range, 0) + 1
        
        # Classification distribution
        classifications[classification] = classifications.get(classification, 0) + 1
    
    infrastructure['speed_statistics'] = {
        'speed_distribution': speed_stats,
        'classification_distribution': classifications,
        'total_tracks': len(tracks),
        'average_speed': sum(t.get('speed_limit_kmh', 0) for t in tracks) / max(len(tracks), 1)
    }
    
    print(f"Speed limit calculation complete!")
    print(f"  Average speed limit: {infrastructure['speed_statistics']['average_speed']:.1f} km/h")
    print(f"  Classifications: {classifications}")
    
    return infrastructure
