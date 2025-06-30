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
        'signals': [],
        'milestones': [],
        'tracks': [],
        'other_infrastructure': []  # yards, depots, halts, platforms
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
                'state': state,
                'railway_type': railway_type
            }
            
            # Categorize all stations equally (no artificial major/regular split)
            if railway_type == 'station' or railway_type == 'junction':
                infrastructure['stations'].append({**base_data, 'type': 'station'})
            elif railway_type == 'signal':
                infrastructure['signals'].append(base_data)
            elif railway_type == 'milestone' or 'milestone' in elem.get('tags', {}):
                infrastructure['milestones'].append(base_data)
            elif railway_type in ['yard', 'depot', 'halt', 'platform']:
                # Other railway infrastructure
                infrastructure['other_infrastructure'].append({**base_data, 'type': railway_type})
        
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

def save_split_data(infrastructure, synthetic_signals, metadata):
    """Save data split into separate files by infrastructure type"""
    import os
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Save stations (all stations together)
    all_stations = infrastructure.get('stations', [])
    stations_data = {
        'stations': all_stations,
        'metadata': {
            **metadata,
            'file_type': 'stations',
            'total_stations': len(all_stations)
        }
    }
    
    # Save tracks with speed limit data
    tracks_data = {
        'tracks': infrastructure.get('tracks', []),
        'metadata': {
            **metadata,
            'file_type': 'tracks',
            'total_tracks': len(infrastructure.get('tracks', [])),
            'speed_statistics': infrastructure.get('speed_statistics', {})
        }
    }
    
    # Save signals (existing + synthetic)
    all_signals = infrastructure.get('signals', []) + synthetic_signals
    signals_data = {
        'signals': all_signals,
        'metadata': {
            **metadata,
            'file_type': 'signals',
            'total_signals': len(all_signals),
            'osm_signals': len(infrastructure.get('signals', [])),
            'synthetic_signals': len(synthetic_signals)
        }
    }
    
    # Save other infrastructure (milestones, yards, depots, halts, platforms)
    other_data = {
        'milestones': infrastructure.get('milestones', []),
        'other_infrastructure': infrastructure.get('other_infrastructure', []),
        'metadata': {
            **metadata,
            'file_type': 'other_infrastructure',
            'total_milestones': len(infrastructure.get('milestones', [])),
            'total_other': len(infrastructure.get('other_infrastructure', []))
        }
    }
    
    # Save analysis data
    analysis_data = {
        'station_rankings': infrastructure.get('station_rankings', {}),
        'speed_statistics': infrastructure.get('speed_statistics', {}),
        'metadata': {
            **metadata,
            'file_type': 'analysis',
            'analysis_complete': True
        }
    }
    
    # Save each file
    files_to_save = [
        ('stations.json', stations_data),
        ('tracks.json', tracks_data),
        ('signals.json', signals_data),
        ('other_infrastructure.json', other_data),
        ('analysis.json', analysis_data)
    ]
    
    for filename, data in files_to_save:
        filepath = os.path.join(data_dir, filename)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"  Saved {filename} ({len(data.get(data['metadata']['file_type'].split('_')[0], data.get('stations', data.get('tracks', data.get('signals', data.get('milestones', []))))))} items)")
    
    # Also save the combined file for backward compatibility
    combined_data = {
        'elements': (infrastructure.get('signals', []) + 
                    infrastructure.get('stations', []) + 
                    infrastructure.get('milestones', []) + 
                    synthetic_signals),
        'metadata': metadata,
        'infrastructure_analysis': {
            'speed_statistics': infrastructure.get('speed_statistics', {}),
            'station_rankings': infrastructure.get('station_rankings', {}),
            'analysis_complete': True
        }
    }        # Add tracks as simplified elements for backward compatibility
    for track in infrastructure.get('tracks', []):
        # Convert track to elements format (simplified)
        track_element = {
            'type': 'way',
            'tags': {
                'railway': 'rail',
                'state': track.get('state', 'Unknown'),
                'track_type': track.get('type', 'other')
            },
            'coords': track.get('coords', [])
        }
        if 'speed_limit_kmh' in track:
            track_element['tags']['speed_limit'] = str(track['speed_limit_kmh'])
        combined_data['elements'].append(track_element)
    
    filepath = os.path.join(data_dir, 'railway_data.json')
    with open(filepath, 'w') as f:
        json.dump(combined_data, f, indent=2)
    print(f"  Saved railway_data.json (combined file with {len(combined_data['elements'])} elements)")

def main():
    print("Fetching railway data by state...")
    data = get_railway_data_by_state()
    
    if data and data.get('elements'):
        print(f"Fetched {len(data['elements'])} OSM elements")
        
        # Generate realistic railway signals
        print("\nGenerating realistic railway signals...")
        infrastructure = extract_infrastructure(data['elements'])
        
        print(f"Extracted infrastructure:")
        print(f"  - Stations: {len(infrastructure['stations'])}")
        print(f"  - Existing signals: {len(infrastructure['signals'])}")
        print(f"  - Track segments: {len(infrastructure['tracks'])}")
        print(f"  - Milestones: {len(infrastructure['milestones'])}")
        print(f"  - Other infrastructure (yards, depots, halts): {len(infrastructure['other_infrastructure'])}")
        
        synthetic_signals = generate_realistic_signals(infrastructure)
        
        # Calculate speed limits for track segments
        print("\nCalculating speed limits for track segments...")
        # Import speed limits module
        algorithms_path = os.path.join(os.path.dirname(__file__), '..', 'algorithms')
        if algorithms_path not in sys.path:
            sys.path.insert(0, algorithms_path)
        from speed_limits import add_speed_limits_to_tracks
        
        print("Using Open-Elevation API (free, reliable)")
        print("   Elevation functionality integrated in speed_limits module")
        
        infrastructure = add_speed_limits_to_tracks(infrastructure)
        
        # Calculate station importance rankings
        print("\nCalculating station importance rankings...")
        from station_importance import rank_stations_by_importance
        infrastructure = rank_stations_by_importance(infrastructure)
        
        # Integrate synthetic signals into main data
        data['elements'].extend(synthetic_signals)
        
        # Add enhanced metadata
        metadata = {
            'osm_elements': len(data['elements']) - len(synthetic_signals),
            'synthetic_signals': len(synthetic_signals),
            'total_elements': len(data['elements']),
            'generated_date': datetime.now().isoformat(),
            'realistic_signals': True,
            'speed_limits_calculated': True,
            'station_rankings_calculated': True,
            'fetch_version': '4.0'
        }
        
        # Save data split into separate files
        print(f"\nSaving data split by infrastructure type...")
        save_split_data(infrastructure, synthetic_signals, metadata)
        
        print(f"\nData processing complete!")
        print(f"  - OSM elements: {metadata['osm_elements']}")
        print(f"  - Realistic synthetic signals: {metadata['synthetic_signals']}")
        print(f"  - Track segments with speed limits: {len(infrastructure['tracks'])}")
        print(f"  - Stations with importance rankings: {infrastructure['station_rankings']['total_stations']}")
        print("Complete railway network analysis ready!")
        print("\nGenerated files:")
        print("  - stations.json (station data with importance rankings)")
        print("  - tracks.json (track data with speed limits)")
        print("  - signals.json (OSM + synthetic signals)")
        print("  - other_infrastructure.json (milestones, etc.)")
        print("  - analysis.json (rankings and statistics)")
        print("  - railway_data.json (combined file for backward compatibility)")
    else:
        print("Failed to fetch data")

if __name__ == "__main__":
    main()
