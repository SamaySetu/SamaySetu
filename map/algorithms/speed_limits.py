import math
import numpy as np
import requests
import time
import os
from typing import List, Tuple, Dict, Optional

# Import the elevation manager for bulk elevation handling
try:
    from .elevation_manager import ElevationDataManager, preload_elevation_data
except ImportError:
    from elevation_manager import ElevationDataManager, preload_elevation_data

# Configuration
ELEVATION_API_URL = "https://api.open-elevation.com/api/v1/lookup"
ELEVATION_API_MAX_POINTS = 50

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

def get_elevation_data(coordinates: List[List[float]], max_points: int = ELEVATION_API_MAX_POINTS) -> List[float]:
    """
    Get elevation data using Open-Elevation API.
    
    Args:
        coordinates: List of [lat, lon] pairs
        max_points: Maximum number of points to query (API limitation)
    
    Returns:
        List of elevations in meters
    """
    # Limit coordinates to avoid API rate limits
    if len(coordinates) > max_points:
        # Sample coordinates evenly
        step = len(coordinates) // max_points
        sampled_coords = coordinates[::step][:max_points]
    else:
        sampled_coords = coordinates
    
    elevations = []
    
    # Use Open-Elevation API
    try:
        print("Getting elevation data from Open-Elevation API...")
        
        # Batch request format
        locations = [{"latitude": lat, "longitude": lon} for lat, lon in sampled_coords]
        response = requests.post(ELEVATION_API_URL, json={"locations": locations}, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if 'results' in data:
                for result in data['results']:
                    elevations.append(float(result['elevation']))
                print(f"Retrieved {len(elevations)} elevations")
                success = True
            else:
                success = False
        else:
            print(f"API error: {response.status_code}")
            success = False
            
    except Exception as e:
        print(f"API error: {e}")
        success = False
    
    # Fallback to geographic estimation if API fails
    if not success:
        print("API failed, using geographic estimation fallback...")
        elevations = [estimate_elevation_fallback(lat, lon) for lat, lon in sampled_coords]
    
    # Interpolate elevations back to original coordinate count if we sampled
    if len(coordinates) > max_points and elevations:
        # Linear interpolation to fill in missing elevations
        x_original = np.linspace(0, 1, len(coordinates))
        x_sampled = np.linspace(0, 1, len(elevations))
        elevations = np.interp(x_original, x_sampled, elevations).tolist()
    
    return elevations

def estimate_elevation_fallback(lat: float, lon: float) -> float:
    """
    Fallback elevation estimation based on known geographic patterns.
    Used when elevation APIs are unavailable.
    """
    # Western Ghats: high elevation (500-2000m)
    western_ghats_regions = [
        (8.0, 77.0, 12.0, 76.0),  # Karnataka Western Ghats
        (11.0, 76.0, 12.5, 77.5),  # Tamil Nadu Western Ghats
        (8.5, 76.5, 10.5, 77.0),  # Kerala Western Ghats
    ]
    
    for min_lat, min_lon, max_lat, max_lon in western_ghats_regions:
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            # Higher elevation in Western Ghats
            return 800 + (lat - min_lat) * 200  # Gradient from 800m to 1200m
    
    # Coastal regions: low elevation (0-100m)
    if lon < 76.5 or lon > 80.5:
        return max(0, 50 - abs(lat - 10) * 10)  # Sea level to 50m
    
    # Eastern Ghats: moderate elevation (200-800m)
    if 78.5 <= lon <= 80.5:
        return 300 + abs(lat - 14) * 50  # 300-600m elevation
    
    # Deccan plateau: moderate elevation (400-800m)
    return 500 + (lat - 12) * 30  # Default plateau elevation

def calculate_gradient_from_elevation(coords: List[List[float]], elevations: List[float]) -> Tuple[float, float]:
    """
    Calculate track gradient and banking from elevation data.
    
    Returns:
        Tuple of (average_gradient_percent, max_gradient_percent)
    """
    if len(coords) < 2 or len(elevations) < 2:
        return 0.0, 0.0
    
    gradients = []
    
    for i in range(len(coords) - 1):
        if i >= len(elevations) - 1:
            break
            
        # Calculate horizontal distance
        horizontal_distance = calculate_distance(
            coords[i][0], coords[i][1],
            coords[i+1][0], coords[i+1][1]
        ) * 1000  # Convert to meters
        
        # Calculate elevation change
        elevation_change = elevations[i+1] - elevations[i]
        
        if horizontal_distance > 0:
            # Gradient as percentage (rise/run * 100)
            gradient = (elevation_change / horizontal_distance) * 100
            gradients.append(abs(gradient))
    
    if not gradients:
        return 0.0, 0.0
    
    avg_gradient = np.mean(gradients)
    max_gradient = max(gradients)
    
    return avg_gradient, max_gradient

def calculate_banking_requirement(coords: List[List[float]], elevations: List[float], speed_kmh: float) -> float:
    """
    Calculate required banking angle for curves based on speed and curvature.
    
    Returns:
        Banking angle in degrees
    """
    if len(coords) < 3:
        return 0.0
    
    curvature = calculate_curvature(coords)
    
    if curvature < 1.0:  # Very gentle curves don't need banking
        return 0.0
    
    # Convert speed to m/s
    speed_ms = speed_kmh / 3.6
    
    # Estimate curve radius from curvature (degrees per km)
    # Rough approximation: radius ≈ 57.3 / (curvature in degrees per km * km per 1000m)
    if curvature > 0:
        curve_radius = 57300 / curvature  # meters
    else:
        return 0.0
    
    # Standard banking calculation for railways
    # tan(θ) = v²/(g*r) where θ is banking angle, v is speed, g is gravity, r is radius
    g = 9.81  # gravity in m/s²
    
    if curve_radius > 0:
        banking_rad = math.atan(speed_ms**2 / (g * curve_radius))
        banking_deg = math.degrees(banking_rad)
        
        # Practical limits for railway banking (typically 0-10 degrees)
        return min(10.0, max(0.0, banking_deg))
    
    return 0.0

def is_urban_area(lat: float, lon: float, major_cities: List[Dict]) -> bool:
    """Check if coordinates are near urban areas"""
    for city in major_cities:
        distance = calculate_distance(lat, lon, city['lat'], city['lon'])
        if distance < city.get('radius', 25):  # Default 25km radius
            return True
    return False

def calculate_speed_limit(track_segment: Dict, all_stations: List[Dict]) -> Dict:
    """
    Calculate realistic speed limit for a track segment based on multiple factors including real elevation data.
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
    
    # Get real elevation data using free APIs with fallbacks
    print(f"Getting elevation data for track segment with {len(coords)} points...")
    elevations = get_elevation_data(coords)
    
    # Calculate factors
    curvature = calculate_curvature(coords)
    avg_gradient, max_gradient = calculate_gradient_from_elevation(coords, elevations)
    
    # Calculate preliminary speed for banking calculation
    preliminary_speed = base_speed
    banking_angle = calculate_banking_requirement(coords, elevations, preliminary_speed)
    
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
        speed_limit *= 0.5
    elif curvature > 30:  # Sharp curves
        speed_limit *= 0.65
    elif curvature > 20:  # Moderate curves
        speed_limit *= 0.75
    elif curvature > 10:  # Gentle curves
        speed_limit *= 0.85
    
    # Gradient factor (reduce speed for steep gradients) - now using real elevation data
    if max_gradient > 3.0:  # Very steep gradient (>3%)
        speed_limit *= 0.5
    elif max_gradient > 2.0:  # Steep gradient (>2%)
        speed_limit *= 0.65
    elif max_gradient > 1.5:  # Moderate steep gradient (>1.5%)
        speed_limit *= 0.75
    elif max_gradient > 1.0:  # Moderate gradient (>1%)
        speed_limit *= 0.85
    elif avg_gradient > 0.5:  # Gentle gradient (>0.5%)
        speed_limit *= 0.95
    
    # Banking consideration - well-banked curves can handle higher speeds
    if banking_angle > 5.0:  # Good banking allows higher speeds on curves
        if curvature > 10:  # Only helps on curved sections
            speed_limit *= 1.1
    elif banking_angle < 2.0 and curvature > 20:  # Insufficient banking on curves
        speed_limit *= 0.9
    
    # Gauge factor
    if gauge and gauge != '1676':  # Non-broad gauge
        if '1000' in gauge or '762' in gauge:  # Narrow gauge
            speed_limit *= 0.65
        elif '1435' in gauge:  # Standard gauge (rare in India)
            speed_limit *= 0.9
    
    # Urban area restrictions
    if urban:
        speed_limit *= 0.65
    
    # Station proximity restrictions
    if min_station_distance < 1:  # Within 1km of station
        speed_limit *= 0.6
    elif min_station_distance < 2:  # Within 2km of station
        speed_limit *= 0.75
    elif min_station_distance < 5:  # Within 5km of station
        speed_limit *= 0.9
    
    # Electrification bonus (electrified tracks often allow higher speeds)
    if electrified and track_type in ['main', 'branch']:
        speed_limit *= 1.15
    
    # Track type specific adjustments
    if track_type == 'main' and max_gradient < 1.0 and curvature < 10:
        # High-speed potential on good main lines
        speed_limit *= 1.1
    
    # Round to nearest 5 km/h and ensure reasonable bounds
    speed_limit = max(20, min(160, round(speed_limit / 5) * 5))
    
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
            'avg_gradient_percent': round(avg_gradient, 3),
            'max_gradient_percent': round(max_gradient, 3),
            'banking_angle_degrees': round(banking_angle, 2),
            'elevation_range_m': f"{min(elevations):.1f}-{max(elevations):.1f}" if elevations else "N/A",
            'urban': urban,
            'min_station_distance_km': round(min_station_distance, 2),
            'electrified': electrified,
            'track_type': track_type,
            'gauge': gauge
        }
    }

def calculate_speed_limit_with_elevation_cache(track_segment: Dict, all_stations: List[Dict], 
                                             elevation_manager: ElevationDataManager) -> Dict:
    """
    Calculate realistic speed limit for a track segment using pre-loaded elevation data.
    This version uses cached elevation data to avoid API rate limiting.
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
        {'name': 'Madurai', 'lat': 9.9252, 'lon': 78.1198, 'radius': 15},
        {'name': 'Trivandrum', 'lat': 8.5241, 'lon': 76.9366, 'radius': 15}
    ]
    
    # Calculate track characteristics using cached elevation data
    total_distance = 0
    total_elevation_change = 0
    max_gradient = 0
    urban_sections = 0
    station_proximity_sections = 0
    
    # Get elevations for all points using cache
    elevations = []
    for lat, lon in coords:
        elevation = elevation_manager.get_elevation(lat, lon)
        elevations.append(elevation)
    
    # Analyze track segment
    for i in range(len(coords) - 1):
        lat1, lon1 = coords[i]
        lat2, lon2 = coords[i + 1]
        
        # Distance calculation
        segment_distance = calculate_distance(lat1, lon1, lat2, lon2)
        total_distance += segment_distance
        
        # Elevation change and gradient using cached data
        elev1, elev2 = elevations[i], elevations[i + 1]
        elevation_change = abs(elev2 - elev1)
        total_elevation_change += elevation_change
        
        if segment_distance > 0:
            gradient = (elevation_change / 1000) / segment_distance  # Convert to rise/run
            max_gradient = max(max_gradient, gradient)
        
        # Urban area detection
        is_urban = any(
            calculate_distance(lat1, lon1, city['lat'], city['lon']) <= city['radius']
            for city in major_cities
        )
        if is_urban:
            urban_sections += 1
        
        # Station proximity
        near_station = any(
            calculate_distance(lat1, lon1, station['lat'], station['lon']) <= 2.0
            for station in all_stations
        )
        if near_station:
            station_proximity_sections += 1
    
    # Speed adjustments based on analysis
    speed_limit = base_speed
    adjustments = []
    
    # Gradient penalty (steep gradients reduce speed)
    if max_gradient > 0.03:  # 3% gradient
        gradient_penalty = min(40, max_gradient * 1000)  # Up to 40 km/h reduction
        speed_limit -= gradient_penalty
        adjustments.append(f"Gradient penalty: -{gradient_penalty:.1f} km/h")
    
    # Urban area penalty
    if urban_sections > len(coords) * 0.3:  # More than 30% in urban areas
        urban_penalty = 30
        speed_limit -= urban_penalty
        adjustments.append(f"Urban area penalty: -{urban_penalty} km/h")
    
    # Station proximity penalty
    if station_proximity_sections > len(coords) * 0.4:  # More than 40% near stations
        station_penalty = 20
        speed_limit -= station_penalty
        adjustments.append(f"Station proximity penalty: -{station_penalty} km/h")
    
    # Electrification bonus
    if electrified and track_type in ['main', 'branch']:
        electrification_bonus = 20
        speed_limit += electrification_bonus
        adjustments.append(f"Electrification bonus: +{electrification_bonus} km/h")
    
    # Gauge adjustments
    if gauge == '1000':  # Narrow gauge
        gauge_penalty = 30
        speed_limit -= gauge_penalty
        adjustments.append(f"Narrow gauge penalty: -{gauge_penalty} km/h")
    
    # Minimum speed limits
    min_speeds = {'service': 25, 'industrial': 20, 'other': 40}
    speed_limit = max(speed_limit, min_speeds.get(track_type, 40))
    
    # Maximum speed limits for safety
    max_speeds = {'main': 160, 'branch': 120, 'service': 60, 'industrial': 50, 'other': 100}
    speed_limit = min(speed_limit, max_speeds.get(track_type, 100))
    
    # Classification
    if speed_limit >= 100:
        classification = 'high_speed'
    elif speed_limit >= 80:
        classification = 'medium_speed'
    elif speed_limit >= 60:
        classification = 'standard_speed'
    else:
        classification = 'low_speed'
    
    return {
        'speed_limit_kmh': round(speed_limit),
        'classification': classification,
        'base_speed': base_speed,
        'max_gradient': round(max_gradient * 100, 2),  # Convert to percentage
        'total_elevation_change': round(total_elevation_change, 1),
        'distance_km': round(total_distance, 2),
        'urban_percentage': round((urban_sections / len(coords)) * 100, 1) if coords else 0,
        'adjustments': adjustments,
        'track_type': track_type,
        'electrified': electrified,
        'gauge': gauge
    }

def add_speed_limits_to_tracks(infrastructure: Dict) -> Dict:
    """
    Add speed limits to all track segments in the infrastructure using pre-loaded elevation data.
    
    Args:
        infrastructure: Railway infrastructure data
    """
    tracks = infrastructure.get('tracks', [])
    all_stations = infrastructure.get('stations', [])
    
    print(f"Calculating speed limits for {len(tracks)} track segments...")
    
    # Pre-load all elevation data to avoid rate limiting
    print("Pre-loading elevation data for all coordinates...")
    elevation_manager = preload_elevation_data(infrastructure)
    
    print(f"Processing tracks with cached elevation data...")
    for i, track in enumerate(tracks):
        if i % 100 == 0:  # More frequent updates since no API delays
            print(f"  Processing track {i+1}/{len(tracks)}")
        
        speed_data = calculate_speed_limit_with_elevation_cache(track, all_stations, elevation_manager)
        track.update(speed_data)
    
    # Generate summary statistics
    speed_stats = {}
    classifications = {}
    gradient_stats = {}
    banking_stats = {}
    
    for track in tracks:
        speed = track.get('speed_limit_kmh', 0)
        classification = track.get('classification', 'unknown')
        factors = track.get('factors', {})
        
        # Speed distribution
        speed_range = f"{(speed // 20) * 20}-{((speed // 20) + 1) * 20}"
        speed_stats[speed_range] = speed_stats.get(speed_range, 0) + 1
        
        # Classification distribution
        classifications[classification] = classifications.get(classification, 0) + 1
        
        # Gradient statistics
        max_gradient = factors.get('max_gradient_percent', 0)
        if max_gradient > 3.0:
            gradient_category = 'very_steep'
        elif max_gradient > 2.0:
            gradient_category = 'steep'
        elif max_gradient > 1.0:
            gradient_category = 'moderate'
        elif max_gradient > 0.5:
            gradient_category = 'gentle'
        else:
            gradient_category = 'flat'
        
        gradient_stats[gradient_category] = gradient_stats.get(gradient_category, 0) + 1
        
        # Banking statistics
        banking = factors.get('banking_angle_degrees', 0)
        if banking > 5.0:
            banking_category = 'high_banking'
        elif banking > 2.0:
            banking_category = 'moderate_banking'
        elif banking > 0.5:
            banking_category = 'low_banking'
        else:
            banking_category = 'no_banking'
        
        banking_stats[banking_category] = banking_stats.get(banking_category, 0) + 1
    
    infrastructure['speed_statistics'] = {
        'speed_distribution': speed_stats,
        'classification_distribution': classifications,
        'gradient_distribution': gradient_stats,
        'banking_distribution': banking_stats,
        'total_tracks': len(tracks),
        'average_speed': sum(t.get('speed_limit_kmh', 0) for t in tracks) / max(len(tracks), 1),
        'average_gradient': sum(t.get('factors', {}).get('max_gradient_percent', 0) for t in tracks) / max(len(tracks), 1),
        'average_banking': sum(t.get('factors', {}).get('banking_angle_degrees', 0) for t in tracks) / max(len(tracks), 1)
    }
    
    print(f"Speed limit calculation with elevation data complete!")
    print(f"  Average speed limit: {infrastructure['speed_statistics']['average_speed']:.1f} km/h")
    print(f"  Average gradient: {infrastructure['speed_statistics']['average_gradient']:.2f}%")
    print(f"  Average banking: {infrastructure['speed_statistics']['average_banking']:.1f}°")
    print(f"  Classifications: {classifications}")
    print(f"  Gradient distribution: {gradient_stats}")
    print(f"  Banking distribution: {banking_stats}")
    
    return infrastructure
