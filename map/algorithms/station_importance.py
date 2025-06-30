import math
import re
import json
import requests
import time
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

# Global cache for station data from website
_station_data_cache = None

def extract_station_data_from_website(url: str = "https://railway-stations-classification.pages.dev/") -> Optional[Dict]:
    """
    Extract the station data JavaScript array from the live website.
    Returns processed data with lookup indexes for fast station matching.
    """
    global _station_data_cache
    
    # Return cached data if available
    if _station_data_cache is not None:
        return _station_data_cache
    
    try:
        print(f"Fetching station data from: {url}")
        
        # Set headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Fetch the webpage
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        content = response.text
        print("Successfully fetched webpage content")
        
        # Find the JavaScript data array
        # Look for "const data =[" and extract until the closing bracket
        match = re.search(r'const data\s*=\s*\[(.*?)\];', content, re.DOTALL)
        
        if not match:
            print("Could not find JavaScript data array in webpage")
            return None
        
        # Extract the JSON array content
        json_content = '[' + match.group(1) + ']'
        
        # Parse the JSON
        raw_station_data = json.loads(json_content)
        
        print(f"Successfully extracted {len(raw_station_data)} station records from website")
        
        # Process the data for efficient lookups
        processed_data = process_station_data(raw_station_data)
        
        # Cache the processed data
        _station_data_cache = processed_data
        
        return processed_data
        
    except requests.RequestException as e:
        print(f"Error fetching data from website: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON data: {e}")
        return None
    except Exception as e:
        print(f"Error extracting data from website: {e}")
        return None

def normalize_station_name(name: str) -> str:
    """Normalize station name for matching."""
    name = name.upper().strip()
    
    # Common replacements for better matching
    replacements = {
        ' JUNCTION': ' JN',
        ' TERMINAL': ' TERM',
        ' CANTONMENT': ' CANTT',
        ' RAILWAY STATION': '',
        ' STATION': '',
        'BENGALURU': 'BANGALORE',
        'THIRUVANANTHAPURAM': 'TRIVANDRUM',
        'PUDUCHERRY': 'PONDICHERRY',
        'MGR CHENNAI CENTRAL': 'CHENNAI CENTRAL',
        'KSR BENGALURU': 'BANGALORE',
        'SMVT BENGLURE': 'BANGALORE',
        'LOKMANYA TILAK TERMINUS': 'LTT',
        'MUMBAI CSMT': 'MUMBAI CST',
        'PT DEEN DAYAL UPADHYAYA JN': 'DEEN DAYAL UPADHYAYA JN',
        'V LAXMIBI JHANSI JN': 'JHANSI JN',
    }
    
    for old, new in replacements.items():
        name = name.replace(old, new)
    
    return name

def process_station_data(raw_data: list) -> dict:
    """
    Process the raw station data into a format optimized for lookups.
    Creates multiple indexes for efficient station matching.
    """
    processed_data = {
        'stations': [],
        'by_name': {},
        'by_code': {},
        'by_normalized_name': {},
        'metadata': {
            'total_stations': len(raw_data),
            'extraction_date': '2024',
            'source': 'railway-stations-classification.pages.dev'
        }
    }
    
    for station in raw_data:
        # Convert to our standard format
        processed_station = {
            'station_name': station['station'],
            'code': station['code'],
            'state': station['state'],
            'zone': station['zone'],
            'division': station['division'],
            'nsg_class': station['new'],  # Use 'new' classification
            'footfall': station['total_pax'],
            'revenue': station['total_rev'],
            'reserved_passengers': station['res_pax'],
            'unreserved_passengers': station['ur_pax'],
            'reserved_revenue': station['res_rev'],
            'unreserved_revenue': station['ur_rev'],
            'previous_classification': station.get('previous', ''),
        }
        
        processed_data['stations'].append(processed_station)
        
        # Create indexes for fast lookup
        original_name = station['station']
        normalized_name = normalize_station_name(original_name)
        code = station['code']
        
        # Index by original name
        processed_data['by_name'][original_name.upper()] = processed_station
        
        # Index by station code
        processed_data['by_code'][code.upper()] = processed_station
        
        # Index by normalized name
        processed_data['by_normalized_name'][normalized_name] = processed_station
        
        # Also index common variations
        variations = [
            original_name.replace(' JN', ' JUNCTION'),
            original_name.replace(' JUNCTION', ' JN'),
            original_name.replace(' CANTT', ' CANTONMENT'),
            original_name.replace(' CANTONMENT', ' CANTT'),
            original_name.replace(' TERM', ' TERMINAL'),
            original_name.replace(' TERMINAL', ' TERM'),
        ]
        
        for variation in variations:
            if variation != original_name:
                processed_data['by_name'][variation.upper()] = processed_station
                normalized_variation = normalize_station_name(variation)
                processed_data['by_normalized_name'][normalized_variation] = processed_station
    
    print(f"Created lookup indexes: by_name={len(processed_data['by_name'])}, by_code={len(processed_data['by_code'])}, by_normalized_name={len(processed_data['by_normalized_name'])}")
    
    return processed_data

def get_station_data_by_name(station_name: str) -> Optional[Dict]:
    """
    Get station data by name using the website dataset.
    Uses multiple lookup strategies for best matching.
    """
    # Load data if not already cached
    dataset = extract_station_data_from_website()
    if not dataset:
        return None
    
    # Try different lookup strategies
    lookup_strategies = [
        # 1. Direct name lookup (original and upper case)
        station_name.upper().strip(),
        station_name.strip(),
        
        # 2. Normalized name lookup
        normalize_station_name(station_name),
        
        # 3. Common variations
        station_name.upper().replace(' JN', ' JUNCTION'),
        station_name.upper().replace(' JUNCTION', ' JN'),
        station_name.upper().replace(' CANTT', ' CANTONMENT'),
        station_name.upper().replace(' CANTONMENT', ' CANTT'),
        station_name.upper().replace(' TERM', ' TERMINAL'),
        station_name.upper().replace(' TERMINAL', ' TERM'),
    ]
    
    # Try by_name index first
    for name_variant in lookup_strategies:
        if name_variant in dataset['by_name']:
            return dataset['by_name'][name_variant]
    
    # Try by_normalized_name index
    for name_variant in lookup_strategies:
        normalized = normalize_station_name(name_variant)
        if normalized in dataset['by_normalized_name']:
            return dataset['by_normalized_name'][normalized]
    
    # Try partial matching for stations that might have slight differences
    normalized_search = normalize_station_name(station_name)
    search_words = normalized_search.split()
    
    if search_words:
        primary_word = search_words[0]
        
        # Look for stations that start with the same primary word
        for indexed_name, station_data in dataset['by_normalized_name'].items():
            indexed_words = indexed_name.split()
            if indexed_words and len(primary_word) >= 4 and len(indexed_words[0]) >= 4:
                if primary_word == indexed_words[0]:
                    # Additional check: ensure reasonable similarity
                    if _is_station_name_similar(normalized_search, indexed_name):
                        return station_data
    
    return None

def _is_station_name_similar(name1: str, name2: str) -> bool:
    """
    Check if two station names are similar enough to be considered a match.
    """
    # Direct match
    if name1 == name2:
        return True
    
    # Check if one contains the other (with minimum length)
    if len(name1) >= 4 and len(name2) >= 4:
        if name1 in name2 or name2 in name1:
            return True
    
    # Check word overlap
    words1 = set(name1.split())
    words2 = set(name2.split())
    
    if words1 and words2:
        # At least 50% word overlap for longer names
        overlap = len(words1.intersection(words2))
        min_words = min(len(words1), len(words2))
        
        if min_words >= 2 and overlap / min_words >= 0.5:
            return True
        
        # For single-word stations, require exact match of significant words
        if min_words == 1 and overlap == 1:
            common_word = list(words1.intersection(words2))[0]
            if len(common_word) >= 4:
                return True
    
    return False

def calculate_ridership_score_from_footfall(footfall: int) -> int:
    """
    Calculate ridership score based on actual footfall numbers.
    Uses logarithmic scaling to handle the wide range of footfall values.
    """
    if footfall <= 0:
        return 0
    
    # Use logarithmic scaling for footfall (base 10)
    # Scale so that 1M footfall = ~50 points, 10M = ~70 points, 25M+ = ~90+ points
    log_footfall = math.log10(footfall)
    
    # Adjust scaling based on typical Indian Railways footfall ranges
    if log_footfall <= 3:  # Up to 1,000 passengers
        score = log_footfall * 10
    elif log_footfall <= 5:  # Up to 100,000 passengers
        score = 30 + (log_footfall - 3) * 15
    elif log_footfall <= 6:  # Up to 1,000,000 passengers
        score = 60 + (log_footfall - 5) * 20
    elif log_footfall <= 7:  # Up to 10,000,000 passengers
        score = 80 + (log_footfall - 6) * 15
    else:  # 10M+ passengers
        score = 95 + min((log_footfall - 7) * 5, 5)  # Cap at 100
    
    return min(int(score), 100)

def calculate_revenue_importance(revenue: int) -> int:
    """
    Calculate importance based on station revenue.
    Revenue often correlates with both passenger and freight importance.
    """
    if revenue <= 0:
        return 0
    
    log_revenue = math.log10(revenue)
    
    # Revenue scaling (in INR)
    if log_revenue <= 5:  # Up to 100,000 INR
        score = log_revenue * 8
    elif log_revenue <= 7:  # Up to 10,000,000 INR
        score = 40 + (log_revenue - 5) * 20
    elif log_revenue <= 8:  # Up to 100,000,000 INR
        score = 80 + (log_revenue - 7) * 15
    else:  # 100M+ INR
        score = 95 + min((log_revenue - 8) * 5, 5)
    
    return min(int(score), 100)

def get_nsg_class_score(nsg_class: str) -> int:
    """
    Get importance score based on Indian Railways NSG (Non-Suburban Group) classification.
    NSG 1 = Highest importance, NSG 6 = Lowest importance
    """
    nsg_scores = {
        'NSG 1': 100,
        'NSG 2': 85,
        'NSG 3': 70,
        'NSG 4': 55,
        'NSG 5': 40,
        'NSG 6': 25
    }
    
    return nsg_scores.get(nsg_class, 30)  # Default for unknown classification

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

def estimate_ridership_score(station: Dict, station_name: str, connectivity_score: int, urban_score: int) -> Tuple[int, Dict]:
    """
    Calculate ridership importance using real footfall data from website when available,
    falling back to heuristic estimation based on station characteristics.
    Returns (score, metadata) where metadata contains the data source and details.
    """
    # First, try to get real footfall data from website
    footfall_data = get_station_data_by_name(station_name)
    
    if footfall_data:
        # Use real footfall data
        footfall_score = calculate_ridership_score_from_footfall(footfall_data['footfall'])
        revenue_score = calculate_revenue_importance(footfall_data['revenue'])
        nsg_score = get_nsg_class_score(footfall_data['nsg_class'])
        
        # Weighted combination of real data metrics
        real_data_score = int(footfall_score * 0.6 + revenue_score * 0.3 + nsg_score * 0.1)
        
        metadata = {
            'data_source': 'real_footfall',
            'footfall': footfall_data['footfall'],
            'revenue': footfall_data['revenue'],
            'nsg_class': footfall_data['nsg_class'],
            'station_code': footfall_data.get('code'),
            'state': footfall_data.get('state'),
            'zone': footfall_data.get('zone'),
            'division': footfall_data.get('division'),
            'footfall_score': footfall_score,
            'revenue_score': revenue_score,
            'nsg_score': nsg_score,
            'lookup_attempted': True
        }
        
        return real_data_score, metadata
    
    else:
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
        heuristic_score = min(total_ridership_score, 100)
        
        metadata = {
            'data_source': 'heuristic_estimation',
            'base_ridership': base_ridership,
            'connectivity_factor': connectivity_factor,
            'urban_factor': urban_factor,
            'lookup_attempted': True
        }
        
        return heuristic_score, metadata

def calculate_station_importance(station: Dict, all_stations: List[Dict], tracks: List[Dict]) -> Dict:
    """
    Calculate comprehensive importance score for a railway station.
    Returns detailed scoring breakdown including real footfall data when available.
    """
    station_name = station.get('name', 'Unknown')
    
    # Get base type score
    type_score, station_type = get_station_type_score(station_name)
    
    # Calculate individual component scores
    connectivity_score = calculate_connectivity_score(station, all_stations, tracks)
    urban_score = calculate_urban_importance(station)
    strategic_score = calculate_strategic_importance(station, station_name)
    ridership_score, ridership_metadata = estimate_ridership_score(station, station_name, connectivity_score, urban_score)
    
    # Adjust weights based on data availability
    if ridership_metadata['data_source'] == 'real_footfall':
        # Give more weight to ridership when we have real data
        weights = {
            'type': 0.15,
            'connectivity': 0.20,
            'urban': 0.20,
            'strategic': 0.15,
            'ridership': 0.30  # Increased weight for real data
        }
    else:
        # Standard weights for heuristic estimation
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
        'weights_used': weights,
        'ridership_data': ridership_metadata
    }
    
    return result

def rank_stations_by_importance(infrastructure: Dict) -> Dict:
    """
    Rank all stations by importance and add rankings to the infrastructure data.
    Now uses comprehensive local dataset from Indian Railways website.
    """
    all_stations = infrastructure.get('stations', [])
    tracks = infrastructure.get('tracks', [])
    
    print(f"Calculating importance rankings for {len(all_stations)} stations...")
    print("Using comprehensive dataset from railway-stations-classification.pages.dev")
    
    # Calculate importance for each station
    station_importance = []
    real_data_count = 0
    heuristic_data_count = 0
    lookup_failures = 0
    
    for i, station in enumerate(all_stations):
        if i % 50 == 0:  # Less frequent updates since local lookup is fast
            print(f"  Processing station {i+1}/{len(all_stations)} (Found real data for {real_data_count} stations)")
        
        importance_data = calculate_station_importance(station, all_stations, tracks)
        
        # Track data source usage
        ridership_data = importance_data.get('ridership_data', {})
        if ridership_data.get('data_source') == 'real_footfall':
            real_data_count += 1
            if i % 25 == 0 and real_data_count > 0:  # Log some successful matches
                print(f"    ✓ Found real data for: {station.get('name', 'Unknown')} - "
                      f"Footfall: {ridership_data.get('footfall', 0):,}, "
                      f"NSG: {ridership_data.get('nsg_class', 'Unknown')}")
        else:
            heuristic_data_count += 1
            if ridership_data.get('lookup_attempted', False):
                lookup_failures += 1
        
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
    nsg_class_counts = defaultdict(int)
    
    for station in all_stations:
        category_counts[station.get('importance_category', 'unknown')] += 1
        type_counts[station.get('station_type', 'unknown')] += 1
        
        score = station.get('importance_score', 0)
        score_range = f"{(int(score) // 10) * 10}-{((int(score) // 10) + 1) * 10}"
        score_ranges[score_range] += 1
        
        # Track NSG class distribution
        ridership_data = station.get('ridership_data', {})
        if ridership_data.get('data_source') == 'real_footfall':
            nsg_class = ridership_data.get('nsg_class', 'Unknown')
            nsg_class_counts[nsg_class] += 1
    
    # Get top stations with real data
    real_data_stations = [
        {
            'name': item['station']['name'],
            'score': item['score'],
            'category': item['station']['importance_category'],
            'type': item['station']['station_type'],
            'state': item['station'].get('ridership_data', {}).get('state', 'Unknown'),
            'footfall': item['station'].get('ridership_data', {}).get('footfall'),
            'revenue': item['station'].get('ridership_data', {}).get('revenue'),
            'nsg_class': item['station'].get('ridership_data', {}).get('nsg_class'),
            'station_code': item['station'].get('ridership_data', {}).get('station_code')
        }
        for item in station_importance 
        if item['station'].get('ridership_data', {}).get('data_source') == 'real_footfall'
    ]
    
    # Load station dataset info for summary
    dataset_info = extract_station_data_from_website()
    dataset_size = dataset_info.get('metadata', {}).get('total_stations', 0) if dataset_info else 0
    
    # Add statistics to infrastructure
    infrastructure['station_rankings'] = {
        'total_stations': len(all_stations),
        'dataset_info': {
            'total_stations_in_dataset': dataset_size,
            'source': 'railway-stations-classification.pages.dev (live website)',
            'extraction_date': '2024'
        },
        'data_source_usage': {
            'real_footfall_data': real_data_count,
            'heuristic_estimation': heuristic_data_count,
            'lookup_failures': lookup_failures,
            'real_data_percentage': round(real_data_count / max(len(all_stations), 1) * 100, 1)
        },
        'category_distribution': dict(category_counts),
        'type_distribution': dict(type_counts),
        'score_distribution': dict(score_ranges),
        'nsg_class_distribution': dict(nsg_class_counts),
        'top_10_stations': [
            {
                'name': item['station']['name'],
                'score': item['score'],
                'category': item['station']['importance_category'],
                'type': item['station']['station_type'],
                'state': item['station'].get('ridership_data', {}).get('state', 'Unknown'),
                'has_real_data': item['station'].get('ridership_data', {}).get('data_source') == 'real_footfall'
            }
            for item in station_importance[:10]
        ],
        'stations_with_real_data': real_data_stations[:20],  # Top 20 with real data
        'average_score': sum(s.get('importance_score', 0) for s in all_stations) / max(len(all_stations), 1)
    }
    
    print(f"\nStation importance ranking complete!")
    print(f"  Average importance score: {infrastructure['station_rankings']['average_score']:.1f}")
    print(f"  Stations with real footfall data: {real_data_count} ({infrastructure['station_rankings']['data_source_usage']['real_data_percentage']:.1f}%)")
    print(f"  Dataset contains: {dataset_size:,} total Indian Railway stations")
    print(f"  Categories: {dict(category_counts)}")
    print(f"  NSG Classes: {dict(nsg_class_counts)}")
    print(f"  Top 3 stations: {[s['name'] for s in infrastructure['station_rankings']['top_10_stations'][:3]]}")
    
    # Show some examples of stations with real data
    if real_data_stations:
        print(f"\nExample stations with real data:")
        for station in real_data_stations[:5]:
            print(f"  • {station['name']} ({station['station_code']}): "
                  f"{station['footfall']:,} footfall, {station['nsg_class']}, "
                  f"Score: {station['score']:.1f}")
    
    return infrastructure
