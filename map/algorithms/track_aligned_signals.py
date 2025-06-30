import json
import math
import os
import sys
from datetime import datetime

def find_tracks_near_station(station, tracks, max_distance=0.01):
    """Find all tracks within a certain distance of a station"""
    station_lat, station_lon = station['lat'], station['lon']
    nearby_tracks = []
    
    for track in tracks:
        coords = track.get('coords', [])
        for i, coord in enumerate(coords):
            lat, lon = coord[0], coord[1]
            distance = math.sqrt((station_lat - lat)**2 + (station_lon - lon)**2)
            if distance <= max_distance:
                nearby_tracks.append({
                    'track': track,
                    'coord_index': i,
                    'distance': distance,
                    'coordinate': coord
                })
    
    # Sort by distance to station
    nearby_tracks.sort(key=lambda x: x['distance'])
    return nearby_tracks

def get_track_direction(coords, coord_index):
    """Get the direction vector of a track at a specific coordinate"""
    if coord_index == 0 and len(coords) > 1:
        # First point - use direction to next point
        return calculate_bearing(coords[0], coords[1])
    elif coord_index == len(coords) - 1 and len(coords) > 1:
        # Last point - use direction from previous point
        return calculate_bearing(coords[-2], coords[-1])
    elif 0 < coord_index < len(coords) - 1:
        # Middle point - use average direction
        bearing1 = calculate_bearing(coords[coord_index-1], coords[coord_index])
        bearing2 = calculate_bearing(coords[coord_index], coords[coord_index+1])
        return (bearing1 + bearing2) / 2
    else:
        return 0  # Default bearing

def calculate_bearing(coord1, coord2):
    """Calculate bearing between two coordinates in degrees"""
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
    
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    
    bearing = math.atan2(y, x)
    return math.degrees(bearing)

def place_signal_on_track(station_coord, track_coord, bearing, distance_km, signal_type):
    """Place a signal on a track at a specific distance from station"""
    # Convert distance to approximate coordinate offset
    # 1 degree ≈ 111 km, so distance_km/111 gives degree offset
    coord_distance = distance_km / 111.0
    
    # Calculate offset based on track bearing
    bearing_rad = math.radians(bearing)
    lat_offset = coord_distance * math.cos(bearing_rad)
    lon_offset = coord_distance * math.sin(bearing_rad)
    
    # Position signal at the calculated offset from track coordinate
    signal_lat = track_coord[0] + lat_offset
    signal_lon = track_coord[1] + lon_offset
    
    return signal_lat, signal_lon

def generate_track_aligned_signals(infrastructure):
    """Generate realistic signals aligned with actual track geometry"""
    synthetic_signals = []
    signal_id = 10000
    
    print("Generating track-aligned realistic railway signals...")
    
    # Get all tracks for reference
    all_tracks = infrastructure['tracks']
    all_stations = infrastructure['stations']
    
    # 1. Generate signals for high-importance stations (top 200)
    print(f"Processing top 200 stations from {len(all_stations)} total stations...")
    for station in all_stations[:200]:
        nearby_tracks = find_tracks_near_station(station, all_tracks, max_distance=0.008)
        
        if not nearby_tracks:
            continue
            
        # For each nearby track, place appropriate signals
        track_count = 0
        for track_info in nearby_tracks[:4]:  # Limit to 4 nearest tracks
            track = track_info['track']
            coord_index = track_info['coord_index']
            track_coord = track_info['coordinate']
            
            # Get track direction
            bearing = get_track_direction(track['coords'], coord_index)
            
            # Determine track type for signal spacing
            track_type = track.get('type', 'branch')
            
            # Place home and distant signals based on track direction
            signal_configs = [
                (1.0, 'distant', 'Distant signal - advance warning'),  # 1km out
                (0.2, 'home', 'Home signal - station entry control'),    # 200m out
                (-0.1, 'starter', 'Starter signal - departure control')   # 100m past station
            ]
            
            for distance_km, signal_type, description in signal_configs:
                # Place signal in approach direction (opposite to track bearing for approach signals)
                signal_bearing = bearing + 180 if distance_km > 0 else bearing
                signal_lat, signal_lon = place_signal_on_track(
                    [station['lat'], station['lon']], 
                    track_coord, 
                    signal_bearing, 
                    abs(distance_km), 
                    signal_type
                )
                
                synthetic_signals.append({
                    'id': signal_id,
                    'type': 'node',
                    'lat': signal_lat,
                    'lon': signal_lon,
                    'tags': {
                        'railway': 'signal',
                        'name': f"{station['name']} {signal_type.title()} T{track_count+1}",
                        'state': station['state'],
                        'signal_type': signal_type,
                        'station_ref': station['name'],
                        'track_ref': track.get('osm_id', f'track_{track_count}'),
                        'description': description,
                        'signal_function': 'block' if signal_type in ['home', 'distant'] else 'departure',
                        'track_aligned': 'true',
                        'synthetic': 'true',
                        'realistic': 'true',
                        'generated_by': 'track_aligned_fetch.py',
                        'generated_date': datetime.now().isoformat()
                    }
                })
                signal_id += 1
            
            track_count += 1
    
    # 2. Generate signals for remaining stations (next 300)
    print(f"Processing next 300 stations from remaining {len(all_stations[200:])} stations...")
    for station in all_stations[200:500]:  # Process stations 201-500
        nearby_tracks = find_tracks_near_station(station, all_tracks, max_distance=0.005)
        
        if not nearby_tracks:
            continue
            
        # Place outer signals on up to 2 tracks
        for track_info in nearby_tracks[:2]:
            track = track_info['track']
            coord_index = track_info['coord_index']
            track_coord = track_info['coordinate']
            
            # Get track direction
            bearing = get_track_direction(track['coords'], coord_index)
            
            # Place outer signals at 500m approach distance
            signal_configs = [
                (0.5, 'outer', 'Outer signal - station approach'),
                (-0.1, 'outer', 'Outer signal - station departure')
            ]
            
            for distance_km, signal_type, description in signal_configs:
                signal_bearing = bearing + 180 if distance_km > 0 else bearing
                signal_lat, signal_lon = place_signal_on_track(
                    [station['lat'], station['lon']], 
                    track_coord, 
                    signal_bearing, 
                    abs(distance_km), 
                    signal_type
                )
                
                direction = 'Approach' if distance_km > 0 else 'Departure'
                synthetic_signals.append({
                    'id': signal_id,
                    'type': 'node',
                    'lat': signal_lat,
                    'lon': signal_lon,
                    'tags': {
                        'railway': 'signal',
                        'name': f"{station['name']} {direction} Outer",
                        'state': station['state'],
                        'signal_type': signal_type,
                        'station_ref': station['name'],
                        'description': description,
                        'signal_function': 'approach',
                        'track_aligned': 'true',
                        'synthetic': 'true',
                        'realistic': 'true',
                        'generated_by': 'track_aligned_fetch.py',
                        'generated_date': datetime.now().isoformat()
                    }
                })
                signal_id += 1
    
    # 3. Generate block signals along long track sections
    print("Generating block signals on track sections...")
    block_signal_count = 0
    
    for track in all_tracks:
        if track.get('type') in ['main', 'branch'] and len(track.get('coords', [])) > 15:
            coords = track['coords']
            
            # More dense signal placement for higher count
            signal_spacing = 15 if track.get('type') == 'main' else 20
            max_signals = min(5, len(coords) // signal_spacing)  # Increased from 3 to 5
            
            for i in range(signal_spacing, len(coords), signal_spacing):
                if i < len(coords) and block_signal_count < 3000:  # Increased from 1000 to 3000
                    coord = coords[i]
                    
                    # Get track direction at this point
                    bearing = get_track_direction(coords, i)
                    
                    # Place signal slightly offset from track center
                    offset_distance = 0.001  # ~100m offset
                    offset_bearing = bearing + 90  # Perpendicular to track
                    signal_lat, signal_lon = place_signal_on_track(
                        coord, coord, offset_bearing, offset_distance, 'block'
                    )
                    
                    synthetic_signals.append({
                        'id': signal_id,
                        'type': 'node',
                        'lat': signal_lat,
                        'lon': signal_lon,
                        'tags': {
                            'railway': 'signal',
                            'name': f"Block Signal {block_signal_count + 1}",
                            'state': track.get('state', 'Unknown'),
                            'signal_type': 'block',
                            'track_type': track.get('type'),
                            'description': f'Automatic block signal on {track.get("type")} line',
                            'signal_function': 'block',
                            'track_aligned': 'true',
                            'synthetic': 'true',
                            'realistic': 'true',
                            'generated_by': 'track_aligned_fetch.py',
                            'generated_date': datetime.now().isoformat()
                        }
                    })
                    signal_id += 1
                    block_signal_count += 1
                    
                    if block_signal_count >= max_signals:
                        break
    
    # 4. Generate additional junction/intermediate signals for track intersections
    print("Generating junction and intermediate signals...")
    
    # Find track intersections (approximate)
    track_endpoints = {}
    track_refs = {}
    
    for i, track in enumerate(all_tracks):
        coords = track.get('coords', [])
        if len(coords) >= 2:
            start = (round(coords[0][0], 4), round(coords[0][1], 4))
            end = (round(coords[-1][0], 4), round(coords[-1][1], 4))
            
            track_endpoints[start] = track_endpoints.get(start, 0) + 1
            track_endpoints[end] = track_endpoints.get(end, 0) + 1
            
            if start not in track_refs:
                track_refs[start] = []
            if end not in track_refs:
                track_refs[end] = []
                
            track_refs[start].append(track)
            track_refs[end].append(track)
    
    junction_count = 0
    for (lat, lon), track_count in track_endpoints.items():
        if track_count >= 3 and junction_count < 500:  # Junction points
            states = [track.get('state') for track in track_refs[(lat, lon)] if track.get('state') != 'Unknown']
            junction_state = states[0] if states else 'Unknown'
            
            track_types = [track.get('type', 'branch') for track in track_refs[(lat, lon)]]
            has_main_line = any(t == 'main' for t in track_types)
            
            signal_name = f"Junction {junction_count + 1}"
            if has_main_line:
                signal_name += " (Main Line)"
            
            synthetic_signals.append({
                'id': signal_id,
                'type': 'node',
                'lat': lat,
                'lon': lon,
                'tags': {
                    'railway': 'signal',
                    'name': signal_name,
                    'state': junction_state,
                    'signal_type': 'junction',
                    'track_count': str(track_count),
                    'has_main_line': str(has_main_line),
                    'description': f'Controls {track_count} converging tracks',
                    'signal_function': 'interlocking',
                    'track_aligned': 'true',
                    'synthetic': 'true',
                    'realistic': 'true',
                    'generated_by': 'track_aligned_fetch.py',
                    'generated_date': datetime.now().isoformat()
                }
            })
            signal_id += 1
            junction_count += 1
    
    # 5. Generate intermediate signals on very long tracks
    print("Generating intermediate signals on long tracks...")
    intermediate_count = 0
    
    for track in all_tracks:
        if len(track.get('coords', [])) > 40 and intermediate_count < 1500:  # Very long tracks
            coords = track['coords']
            
            # Place intermediate signals every 30 coordinate points
            for i in range(30, len(coords), 30):
                if i < len(coords) and intermediate_count < 1500:
                    coord = coords[i]
                    bearing = get_track_direction(coords, i)
                    
                    # Place signal slightly offset
                    offset_distance = 0.0008
                    signal_lat, signal_lon = place_signal_on_track(
                        coord, coord, bearing + 90, offset_distance, 'intermediate'
                    )
                    
                    synthetic_signals.append({
                        'id': signal_id,
                        'type': 'node',
                        'lat': signal_lat,
                        'lon': signal_lon,
                        'tags': {
                            'railway': 'signal',
                            'name': f"Intermediate Signal {intermediate_count + 1}",
                            'state': track.get('state', 'Unknown'),
                            'signal_type': 'intermediate',
                            'track_type': track.get('type'),
                            'description': f'Intermediate signal on {track.get("type")} line',
                            'signal_function': 'block',
                            'track_aligned': 'true',
                            'synthetic': 'true',
                            'realistic': 'true',
                            'generated_by': 'track_aligned_fetch.py',
                            'generated_date': datetime.now().isoformat()
                        }
                    })
                    signal_id += 1
                    intermediate_count += 1
    
    print(f"Generated {len(synthetic_signals)} track-aligned realistic signals:")
    station_signals = len([s for s in synthetic_signals if s['tags']['signal_type'] in ['home', 'distant', 'starter', 'outer']])
    block_signals = len([s for s in synthetic_signals if s['tags']['signal_type'] == 'block'])
    junction_signals = len([s for s in synthetic_signals if s['tags']['signal_type'] == 'junction'])
    intermediate_signals = len([s for s in synthetic_signals if s['tags']['signal_type'] == 'intermediate'])
    print(f"  - Station signals: {station_signals}")
    print(f"  - Block signals: {block_signals}")
    print(f"  - Junction signals: {junction_signals}")
    print(f"  - Intermediate signals: {intermediate_signals}")
    
    return synthetic_signals

if __name__ == "__main__":
    # Test the new signal generation
    print("Testing track-aligned signal generation...")
    
    # Load existing data
    with open('railway_data.json', 'r') as f:
        data = json.load(f)
    
    # Extract infrastructure
    try:
        parent_dir = os.path.dirname(os.path.dirname(__file__))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        from scripts.fetch import extract_infrastructure
        infrastructure = extract_infrastructure(data['elements'])
    except ImportError as e:
        print(f"Error importing fetch module: {e}")
        exit(1)
    
    # Generate new track-aligned signals
    new_signals = generate_track_aligned_signals(infrastructure)
    
    print(f"Generated {len(new_signals)} new track-aligned signals")
    print("Sample signals:")
    for signal in new_signals[:5]:
        print(f"  - {signal['tags']['name']} ({signal['tags']['signal_type']}) at {signal['lat']:.4f}, {signal['lon']:.4f}")
