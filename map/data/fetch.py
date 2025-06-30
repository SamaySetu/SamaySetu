import requests
import json
import time
from datetime import datetime

def extract_infrastructure(elements):
    """Extract infrastructure from OSM elements for signal synthesis"""
    infrastructure = {
        'stations': [],
        'major_stations': [],
        'signals': [],
        'milestones': [],
        'tracks': []
    }
    
    seen = set()
    nodes = {elem['id']: elem for elem in elements if elem['type'] == 'node'}
    
    for elem in elements:
        if elem['type'] == 'node' and 'lat' in elem and 'lon' in elem:
            key = (elem['lat'], elem['lon'])
            if key in seen:
                continue
            seen.add(key)
            
            railway_type = elem.get('tags', {}).get('railway', '')
            name = elem.get('tags', {}).get('name', 'Unknown')
            state = elem.get('tags', {}).get('state', 'Unknown')
            
            base_data = {
                'name': name,
                'lat': elem['lat'],
                'lon': elem['lon'],
                'state': state
            }
            
            # Categorize stations and junctions
            if railway_type == 'station' or railway_type == 'junction':
                major_keywords = ['jn', 'junction', 'central', 'terminal', 'main', 'city', 'cantt', 'cantonment']
                is_major = any(keyword in name.lower() for keyword in major_keywords)
                
                if is_major:
                    infrastructure['major_stations'].append({**base_data, 'type': 'major'})
                else:
                    infrastructure['stations'].append({**base_data, 'type': 'regular'})
            elif railway_type == 'signal':
                infrastructure['signals'].append(base_data)
            elif railway_type == 'milestone' or 'milestone' in elem.get('tags', {}):
                infrastructure['milestones'].append(base_data)
        
        # Extract tracks
        elif elem['type'] == 'way' and elem.get('tags', {}).get('railway') == 'rail':
            if len(elem.get('nodes', [])) > 1:
                coords = []
                for node_id in elem['nodes']:
                    if node_id in nodes:
                        node = nodes[node_id]
                        coords.append([node['lat'], node['lon']])
                
                if len(coords) > 1:
                    state = elem.get('tags', {}).get('state', 'Unknown')
                    tags = elem.get('tags', {})
                    usage = tags.get('usage', '')
                    service = tags.get('service', '')
                    electrified = tags.get('electrified', '')
                    frequency = tags.get('frequency', '')
                    gauge = tags.get('gauge', '')
                    
                    # Determine track type
                    if service in ['siding', 'yard', 'spur', 'crossover']:
                        track_type = 'service'
                    elif usage in ['industrial', 'military', 'tourism']:
                        track_type = 'industrial'
                    elif usage in ['branch', 'secondary']:
                        track_type = 'branch'
                    elif usage in ['main', 'trunk']:
                        track_type = 'main'
                    elif electrified in ['yes', 'contact_line', '25000'] or frequency:
                        track_type = 'main'
                    elif gauge and gauge != '1676':
                        track_type = 'narrow_gauge'
                    elif usage == '':
                        track_type = 'branch'
                    else:
                        track_type = 'other'
                    
                    infrastructure['tracks'].append({
                        'coords': coords,
                        'state': state,
                        'type': track_type,
                        'length': len(coords),
                        'electrified': bool(electrified),
                        'gauge': gauge,
                        'osm_id': elem['id']
                    })
    
    return infrastructure

def generate_realistic_signals(infrastructure):
    """Generate realistic railway signals that would exist in real life"""
    synthetic_signals = []
    signal_id = 10000  # Start with high ID to avoid conflicts
    
    print("Generating realistic railway signals...")
    
    # 1. Home and Distant signals for major stations (standard railway practice)
    print(f"Generating home/distant signals for {len(infrastructure['major_stations'])} major stations...")
    for station in infrastructure['major_stations']:
        # In real railways, signals are placed based on braking distance and visibility
        # Distant signal ~1km out, Home signal ~200m from platform
        signal_configs = [
            (0.009, 'distant', '🟡', 'Distant signal - advance warning'),  # ~1km
            (0.002, 'home', '🔴', 'Home signal - station entry control')    # ~200m
        ]
        
        # Typically 2 approach directions for major stations (up/down line)
        directions = [
            ('Up', 0, 1),      # Northbound/Eastbound
            ('Down', 0, -1)    # Southbound/Westbound
        ]
        
        for direction_name, lon_mult, lat_mult in directions:
            for distance, signal_type, emoji, description in signal_configs:
                synthetic_signals.append({
                    'id': signal_id,
                    'type': 'node',
                    'lat': station['lat'] + (distance * lat_mult),
                    'lon': station['lon'] + (distance * lon_mult * 0.5),  # Adjust for geography
                    'tags': {
                        'railway': 'signal',
                        'name': f"{station['name']} {direction_name} {signal_type.title()}",
                        'state': station['state'],
                        'signal_type': signal_type,
                        'station_ref': station['name'],
                        'direction': direction_name.lower(),
                        'description': description,
                        'signal_function': 'block',
                        'emoji': emoji,
                        'synthetic': 'true',
                        'realistic': 'true',
                        'generated_by': 'fetch.py',
                        'generated_date': datetime.now().isoformat()
                    }
                })
                signal_id += 1
    
    # 2. Starter signals at station platforms (departure control)
    print(f"Generating starter signals for {len(infrastructure['major_stations'])} major stations...")
    for station in infrastructure['major_stations']:
        # Starter signals control train departures from platforms
        starter_configs = [
            (0.001, 'starter_up', '🟢', 'Up line departure'),
            (-0.001, 'starter_down', '🟢', 'Down line departure')
        ]
        
        for offset, signal_type, emoji, description in starter_configs:
            synthetic_signals.append({
                'id': signal_id,
                'type': 'node',
                'lat': station['lat'] + offset,
                'lon': station['lon'],
                'tags': {
                    'railway': 'signal',
                    'name': f"{station['name']} {signal_type.replace('_', ' ').title()}",
                    'state': station['state'],
                    'signal_type': 'starter',
                    'station_ref': station['name'],
                    'description': description,
                    'signal_function': 'departure',
                    'emoji': emoji,
                    'synthetic': 'true',
                    'realistic': 'true',
                    'generated_by': 'fetch.py',
                    'generated_date': datetime.now().isoformat()
                }
            })
            signal_id += 1
    
    # 3. Junction signals at actual track junctions (interlocking points)
    print("Generating junction signals at track intersections...")
    track_endpoints = {}
    track_refs = {}
    
    # Analyze track intersections
    for i, track in enumerate(infrastructure['tracks']):
        coords = track['coords']
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
        if track_count >= 3:  # Actual junction point
            # Get state from connected tracks
            states = [track.get('state') for track in track_refs[(lat, lon)] if track.get('state') != 'Unknown']
            junction_state = states[0] if states else 'Unknown'
            
            # Determine if it's a major junction (main lines involved)
            track_types = [track.get('type', 'branch') for track in track_refs[(lat, lon)]]
            has_main_line = any(t == 'main' for t in track_types)
            
            # Real junction signals are placed to control conflicting movements
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
                    'emoji': '🟡' if has_main_line else '🟠',
                    'synthetic': 'true',
                    'realistic': 'true',
                    'generated_by': 'fetch.py',
                    'generated_date': datetime.now().isoformat()
                }
            })
            signal_id += 1
            junction_count += 1
    
    # 4. Block signals on long sections (automatic block signaling)
    print("Generating block signals on long track sections...")
    block_signal_count = 0
    for track in infrastructure['tracks']:
        # Only main and branch lines typically have block signals
        if track.get('type') in ['main', 'branch'] and len(track['coords']) > 15:
            coords = track['coords']
            track_length_km = len(coords) * 0.1  # Rough estimate
            
            # Block signals typically every 2-3km on main lines, 4-5km on branch lines
            if track.get('type') == 'main':
                signal_spacing = 20  # coordinates (roughly 2km)
            else:
                signal_spacing = 35  # coordinates (roughly 3.5km)
            
            # Don't place too many signals - realistic spacing
            max_signals_per_track = min(3, track_length_km // 2)
            signals_placed = 0
            
            for i in range(signal_spacing, len(coords), signal_spacing):
                if i < len(coords) and signals_placed < max_signals_per_track:
                    block_number = signals_placed + 1
                    
                    synthetic_signals.append({
                        'id': signal_id,
                        'type': 'node',
                        'lat': coords[i][0],
                        'lon': coords[i][1],
                        'tags': {
                            'railway': 'signal',
                            'name': f"Block Signal {block_number}",
                            'state': track.get('state', 'Unknown'),
                            'signal_type': 'block',
                            'track_type': track.get('type'),
                            'block_number': str(block_number),
                            'description': f'Automatic block signal on {track.get("type")} line',
                            'signal_function': 'block',
                            'emoji': '🔵',
                            'synthetic': 'true',
                            'realistic': 'true',
                            'generated_by': 'fetch.py',
                            'generated_date': datetime.now().isoformat()
                        }
                    })
                    signal_id += 1
                    block_signal_count += 1
                    signals_placed += 1
    
    # 5. Outer signals for regular stations (where trains actually stop)
    print(f"Generating outer signals for {min(50, len(infrastructure['stations']))} regular stations...")
    station_signal_count = 0
    for station in infrastructure['stations'][:50]:  # Limit to major regular stations
        # Regular stations typically have one outer signal per direction
        signal_configs = [
            (0.004, 'outer_up', '🟡', 'Up line approach'),
            (-0.004, 'outer_down', '🟡', 'Down line approach')
        ]
        
        for offset, signal_type, emoji, description in signal_configs:
            synthetic_signals.append({
                'id': signal_id,
                'type': 'node',
                'lat': station['lat'] + offset,
                'lon': station['lon'],
                'tags': {
                    'railway': 'signal',
                    'name': f"{station['name']} {signal_type.replace('_', ' ').title()}",
                    'state': station['state'],
                    'signal_type': 'outer',
                    'station_ref': station['name'],
                    'description': description,
                    'signal_function': 'approach',
                    'emoji': emoji,
                    'synthetic': 'true',
                    'realistic': 'true',
                    'generated_by': 'fetch.py',
                    'generated_date': datetime.now().isoformat()
                }
            })
            signal_id += 1
            station_signal_count += 1
    
    print(f"Generated {len(synthetic_signals)} realistic railway signals:")
    print(f"  - Station approach/departure signals: {(len(infrastructure['major_stations']) * 4) + station_signal_count}")
    print(f"  - Junction signals: {junction_count}")
    print(f"  - Block signals: {block_signal_count}")
    
    return synthetic_signals

def get_railway_data_by_state():
    states = {
        "Tamil Nadu": "tn",
        "Kerala": "kl", 
        "Karnataka": "ka",
        "Andhra Pradesh": "ap",
        "Telangana": "tg",
        "Puducherry": "py"
    }
    
    all_elements = []
    
    for state_name, state_code in states.items():
        print(f"Fetching data for {state_name}...")
        
        query = f"""
        [out:json][timeout:60];
        
        area["name"="{state_name}"]->.{state_code};
        
        (
          way["railway"="rail"](area.{state_code});
          node["railway"="station"](area.{state_code});
          way["railway"="station"](area.{state_code});
          node["railway"="signal"](area.{state_code});
          way["railway"="signal"](area.{state_code});
          node["railway"="milestone"](area.{state_code});
          way["railway"="milestone"](area.{state_code});
          node["milestone"](area.{state_code});
          node["railway:signal"](area.{state_code});
          node["railway"="junction"](area.{state_code});
          way["railway"="junction"](area.{state_code});
          node["railway"~"yard|depot|halt|platform"](area.{state_code});
        );
        
        out body;
        >;
        out skel qt;
        """
        
        url = "https://overpass-api.de/api/interpreter"
        
        try:
            response = requests.post(url, data=query, timeout=120)
            response.raise_for_status()
            data = response.json()
            
            # Add state info to each element
            for elem in data.get('elements', []):
                if 'tags' not in elem:
                    elem['tags'] = {}
                elem['tags']['state'] = state_name
            
            all_elements.extend(data.get('elements', []))
            print(f"  Added {len(data.get('elements', []))} elements from {state_name}")
            
        except requests.exceptions.Timeout:
            print(f"  Query timed out for {state_name}")
        except requests.exceptions.RequestException as e:
            print(f"  Request failed for {state_name}: {e}")
        
        # Small delay between requests
        time.sleep(1)
    
    return {"elements": all_elements}

def save_data(data, filename="railway_data.json"):
    import os
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    print("Fetching railway data by state...")
    data = get_railway_data_by_state()
    
    if data and data.get('elements'):
        print(f"Fetched {len(data['elements'])} OSM elements")
        
        # Generate realistic railway signals
        print("\nGenerating realistic railway signals...")
        infrastructure = extract_infrastructure(data['elements'])
        
        print(f"Extracted infrastructure:")
        print(f"  - Regular stations: {len(infrastructure['stations'])}")
        print(f"  - Major stations: {len(infrastructure['major_stations'])}")
        print(f"  - Existing signals: {len(infrastructure['signals'])}")
        print(f"  - Track segments: {len(infrastructure['tracks'])}")
        
        synthetic_signals = generate_realistic_signals(infrastructure)
        
        # Integrate synthetic signals into main data
        data['elements'].extend(synthetic_signals)
        
        # Add metadata
        data['metadata'] = {
            'osm_elements': len(data['elements']) - len(synthetic_signals),
            'synthetic_signals': len(synthetic_signals),
            'total_elements': len(data['elements']),
            'generated_date': datetime.now().isoformat(),
            'realistic_signals': True,
            'fetch_version': '2.0'
        }
        
        save_data(data)
        print(f"\nData saved with {len(data['elements'])} total elements")
        print(f"  - OSM elements: {data['metadata']['osm_elements']}")
        print(f"  - Realistic synthetic signals: {data['metadata']['synthetic_signals']}")
        print("Realistic railway network with proper signaling ready!")
    else:
        print("Failed to fetch data")

if __name__ == "__main__":
    main()
