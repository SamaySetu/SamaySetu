import requests
import json
import time
import sys
import os
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
    # Import the track-aligned signal generation
    algorithms_path = os.path.join(os.path.dirname(__file__), '..', 'algorithms')
    if algorithms_path not in sys.path:
        sys.path.insert(0, algorithms_path)
    from track_aligned_signals import generate_track_aligned_signals
    
    print("Generating track-aligned realistic railway signals...")
    synthetic_signals = generate_track_aligned_signals(infrastructure)
    
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
    # Save to data directory (parent directory)
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(data_dir, exist_ok=True)
    filepath = os.path.join(data_dir, filename)
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
        
        # Calculate speed limits for track segments
        print("\nCalculating speed limits for track segments...")
        # Import speed limits module
        algorithms_path = os.path.join(os.path.dirname(__file__), '..', 'algorithms')
        if algorithms_path not in sys.path:
            sys.path.insert(0, algorithms_path)
        from speed_limits import add_speed_limits_to_tracks
        infrastructure = add_speed_limits_to_tracks(infrastructure)
        
        # Calculate station importance rankings
        print("\nCalculating station importance rankings...")
        from station_importance import rank_stations_by_importance
        infrastructure = rank_stations_by_importance(infrastructure)
        
        # Integrate synthetic signals into main data
        data['elements'].extend(synthetic_signals)
        
        # Add enhanced metadata
        data['metadata'] = {
            'osm_elements': len(data['elements']) - len(synthetic_signals),
            'synthetic_signals': len(synthetic_signals),
            'total_elements': len(data['elements']),
            'generated_date': datetime.now().isoformat(),
            'realistic_signals': True,
            'speed_limits_calculated': True,
            'station_rankings_calculated': True,
            'fetch_version': '3.0'
        }
        
        # Add infrastructure analysis to data
        data['infrastructure_analysis'] = {
            'speed_statistics': infrastructure.get('speed_statistics', {}),
            'station_rankings': infrastructure.get('station_rankings', {}),
            'analysis_complete': True
        }
        
        save_data(data)
        print(f"\nData saved with {len(data['elements'])} total elements")
        print(f"  - OSM elements: {data['metadata']['osm_elements']}")
        print(f"  - Realistic synthetic signals: {data['metadata']['synthetic_signals']}")
        print(f"  - Track segments with speed limits: {len(infrastructure['tracks'])}")
        print(f"  - Stations with importance rankings: {infrastructure['station_rankings']['total_stations']}")
        print("Complete railway network analysis ready!")
    else:
        print("Failed to fetch data")

if __name__ == "__main__":
    main()
