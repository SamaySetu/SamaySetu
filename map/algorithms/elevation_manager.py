import requests
import json
import time
import os
import math
from typing import List, Tuple, Dict, Set

class ElevationDataManager:
    """Manages bulk elevation data fetching and caching for railway network analysis"""
    
    def __init__(self, cache_file="elevation_cache.json"):
        self.cache_file = cache_file
        self.cache_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_path = os.path.join(self.cache_dir, cache_file)
        self.elevation_cache = self.load_cache()
        
    def load_cache(self) -> Dict[str, float]:
        """Load existing elevation cache from file"""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {}
    
    def save_cache(self):
        """Save elevation cache to file"""
        with open(self.cache_path, 'w') as f:
            json.dump(self.elevation_cache, f, indent=2)
        print(f"Saved elevation cache with {len(self.elevation_cache)} points to {self.cache_path}")
    
    def get_cache_key(self, lat: float, lon: float, precision: int = 4) -> str:
        """Generate cache key for a coordinate with specified precision"""
        return f"{lat:.{precision}f},{lon:.{precision}f}"
    
    def extract_all_coordinates(self, infrastructure: Dict) -> Set[Tuple[float, float]]:
        """Extract all unique coordinates from infrastructure data"""
        coordinates = set()
        
        # Extract from stations
        for station in infrastructure.get('stations', []):
            lat, lon = station.get('lat'), station.get('lon')
            if lat is not None and lon is not None:
                coordinates.add((round(lat, 4), round(lon, 4)))
        
        # Extract from tracks (sample points to reduce API calls)
        for track in infrastructure.get('tracks', []):
            coords = track.get('coords', [])
            # Sample every few points to reduce API calls while maintaining accuracy
            sample_interval = max(1, len(coords) // 20)  # At most 20 points per track
            for i in range(0, len(coords), sample_interval):
                lat, lon = coords[i][0], coords[i][1]
                coordinates.add((round(lat, 4), round(lon, 4)))
            
            # Always include start and end points
            if coords:
                lat, lon = coords[0][0], coords[0][1]
                coordinates.add((round(lat, 4), round(lon, 4)))
                lat, lon = coords[-1][0], coords[-1][1]
                coordinates.add((round(lat, 4), round(lon, 4)))
        
        # Extract from signals
        for signal in infrastructure.get('signals', []):
            lat, lon = signal.get('lat'), signal.get('lon')
            if lat is not None and lon is not None:
                coordinates.add((round(lat, 4), round(lon, 4)))
        
        # Extract from other infrastructure
        for item in infrastructure.get('other_infrastructure', []):
            lat, lon = item.get('lat'), item.get('lon')
            if lat is not None and lon is not None:
                coordinates.add((round(lat, 4), round(lon, 4)))
        
        return coordinates
    
    def fetch_elevations_in_batches(self, coordinates: List[Tuple[float, float]], 
                                   batch_size: int = 50, delay: float = 2.0):
        """Fetch elevations in batches with rate limiting"""
        total_coordinates = len(coordinates)
        fetched_count = 0
        
        print(f"Fetching elevations for {total_coordinates} unique coordinates...")
        
        for i in range(0, total_coordinates, batch_size):
            batch = coordinates[i:i + batch_size]
            
            # Check which coordinates are not in cache
            batch_to_fetch = []
            for lat, lon in batch:
                cache_key = self.get_cache_key(lat, lon)
                if cache_key not in self.elevation_cache:
                    batch_to_fetch.append((lat, lon))
            
            if not batch_to_fetch:
                print(f"  Batch {i//batch_size + 1}: All {len(batch)} points found in cache")
                continue
            
            # Prepare API request
            locations = [{"latitude": lat, "longitude": lon} for lat, lon in batch_to_fetch]
            payload = {"locations": locations}
            
            try:
                print(f"  Batch {i//batch_size + 1}: Fetching {len(batch_to_fetch)} new points...")
                response = requests.post(
                    "https://api.open-elevation.com/api/v1/lookup",
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Cache the results
                for j, result in enumerate(data.get('results', [])):
                    if j < len(batch_to_fetch):
                        lat, lon = batch_to_fetch[j]
                        cache_key = self.get_cache_key(lat, lon)
                        elevation = result.get('elevation', 0)
                        self.elevation_cache[cache_key] = elevation
                        fetched_count += 1
                
                print(f"    Successfully fetched {len(data.get('results', []))} elevations")
                
            except requests.exceptions.RequestException as e:
                print(f"    Error fetching batch {i//batch_size + 1}: {e}")
                # Continue with next batch
            
            # Rate limiting delay
            if i + batch_size < total_coordinates:
                time.sleep(delay)
        
        print(f"Elevation fetching complete: {fetched_count} new points fetched")
        self.save_cache()
    
    def get_elevation(self, lat: float, lon: float) -> float:
        """Get elevation for a coordinate from cache"""
        cache_key = self.get_cache_key(lat, lon)
        return self.elevation_cache.get(cache_key, 0.0)
    
    def interpolate_elevation(self, lat: float, lon: float) -> float:
        """Get elevation with interpolation from nearby cached points if exact match not found"""
        cache_key = self.get_cache_key(lat, lon)
        
        # Try exact match first
        if cache_key in self.elevation_cache:
            return self.elevation_cache[cache_key]
        
        # Find nearby points for interpolation
        nearby_points = []
        search_radius = 0.01  # ~1km
        
        for cached_key, elevation in self.elevation_cache.items():
            try:
                cached_lat, cached_lon = map(float, cached_key.split(','))
                distance = math.sqrt((lat - cached_lat)**2 + (lon - cached_lon)**2)
                if distance <= search_radius:
                    nearby_points.append((distance, elevation))
            except ValueError:
                continue
        
        if nearby_points:
            # Weighted average based on inverse distance
            weights = [1 / (d + 0.0001) for d, _ in nearby_points]  # Small offset to avoid division by zero
            weighted_elevation = sum(w * e for (_, e), w in zip(nearby_points, weights))
            total_weight = sum(weights)
            return weighted_elevation / total_weight if total_weight > 0 else 0.0
        
        return 0.0  # Default elevation if no nearby points found

def preload_elevation_data(infrastructure: Dict) -> ElevationDataManager:
    """Preload elevation data for all coordinates in the infrastructure"""
    print("\n=== Pre-loading Elevation Data ===")
    
    elevation_manager = ElevationDataManager()
    
    # Extract all unique coordinates
    coordinates = elevation_manager.extract_all_coordinates(infrastructure)
    coordinates_list = list(coordinates)
    
    print(f"Found {len(coordinates_list)} unique coordinates to process")
    
    # Check how many are already cached
    cached_count = sum(1 for lat, lon in coordinates_list 
                      if elevation_manager.get_cache_key(lat, lon) in elevation_manager.elevation_cache)
    
    print(f"Already cached: {cached_count}/{len(coordinates_list)} ({cached_count/len(coordinates_list)*100:.1f}%)")
    
    if cached_count < len(coordinates_list):
        print(f"Need to fetch: {len(coordinates_list) - cached_count} elevations")
        
        # Fetch missing elevations
        elevation_manager.fetch_elevations_in_batches(
            coordinates_list,
            batch_size=50,  # Open-Elevation API limit
            delay=2.0       # 2 second delay between batches
        )
    else:
        print("All elevations already cached!")
    
    print("=== Elevation Data Ready ===\n")
    return elevation_manager

if __name__ == "__main__":
    # Test the elevation manager
    print("Testing elevation data manager...")
    
    # Create test infrastructure
    test_infrastructure = {
        'stations': [
            {'name': 'Test Station 1', 'lat': 13.0827, 'lon': 80.2707},
            {'name': 'Test Station 2', 'lat': 28.6139, 'lon': 77.2090}
        ],
        'tracks': [
            {
                'coords': [
                    [13.0827, 80.2707],
                    [13.0837, 80.2717],
                    [13.0847, 80.2727]
                ]
            }
        ],
        'signals': [],
        'other_infrastructure': []
    }
    
    # Test preloading
    elevation_manager = preload_elevation_data(test_infrastructure)
    
    # Test getting elevations
    for station in test_infrastructure['stations']:
        elevation = elevation_manager.get_elevation(station['lat'], station['lon'])
        print(f"Station {station['name']}: {elevation}m elevation")
