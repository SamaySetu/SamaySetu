import requests
import json
import time

def fetch_osm(query):
    # Get data from OSM
    url = "http://overpass-api.de/api/interpreter"
    
    try:
        response = requests.post(url, data=query, timeout=300)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None

def get_stations():
    # Get railway stations
    query = """
    [out:json][timeout:300];
    (
      node["railway"="station"]["place"!="city"]["place"!="town"]["place"!="village"]["station"!="subway"]["station"!="metro"]["transport"!="metro"]["public_transport"!="station"]["railway:metro"!="yes"]["metro"!="yes"]["subway"!="yes"](area:3600304716);
      way["railway"="station"]["place"!="city"]["place"!="town"]["place"!="village"]["station"!="subway"]["station"!="metro"]["transport"!="metro"]["public_transport"!="station"]["railway:metro"!="yes"]["metro"!="yes"]["subway"!="yes"](area:3600304716);
    );
    out geom;
    """
    
    print("Getting stations...")
    return fetch_osm(query)

def get_tracks():
    # Get railway tracks
    query = """
    [out:json][timeout:300];
    (
      way["railway"="rail"]["electrified"]["usage"!="industrial"]["usage"!="military"]["service"!="siding"]["service"!="yard"]["service"!="spur"]["highspeed"!="yes"](area:3600304716);
      way["railway"="rail"]["gauge"]["usage"!="industrial"]["usage"!="military"]["service"!="siding"]["service"!="yard"]["service"!="spur"]["highspeed"!="yes"](area:3600304716);
    );
    out geom;
    """
    
    print("Getting tracks...")
    return fetch_osm(query)

def parse_stations(data):
    # Parse station data
    stations = []
    
    if not data or 'elements' not in data:
        return stations
    
    for item in data['elements']:
        if item['type'] == 'node':
            station = {
                'id': item['id'],
                'type': 'station',
                'name': item.get('tags', {}).get('name', 'Unknown'),
                'lat': item['lat'],
                'lon': item['lon'],
                'tags': item.get('tags', {})
            }
            stations.append(station)
        elif item['type'] == 'way' and 'geometry' in item:
            coords = item['geometry']
            if coords:
                lat = sum(c['lat'] for c in coords) / len(coords)
                lon = sum(c['lon'] for c in coords) / len(coords)
                
                station = {
                    'id': item['id'],
                    'type': 'station',
                    'name': item.get('tags', {}).get('name', 'Unknown'),
                    'lat': lat,
                    'lon': lon,
                    'tags': item.get('tags', {})
                }
                stations.append(station)
    
    return stations

def parse_tracks(data):
    # Parse track data
    tracks = []
    
    if not data or 'elements' not in data:
        return tracks
    
    for item in data['elements']:
        if item['type'] == 'way' and 'geometry' in item:
            track = {
                'id': item['id'],
                'type': 'track',
                'name': item.get('tags', {}).get('name', ''),
                'coords': [(c['lon'], c['lat']) for c in item['geometry']],
                'tags': item.get('tags', {})
            }
            tracks.append(track)
    
    return tracks

def make_index(stations, tracks):
    # Build spatial index
    index = {
        'stations': {},
        'tracks': {},
        'bounds': {
            'min_lat': float('inf'),
            'max_lat': float('-inf'),
            'min_lon': float('inf'),
            'max_lon': float('-inf')
        }
    }
    
    for station in stations:
        lat_key = int(station['lat'] * 10)
        lon_key = int(station['lon'] * 10)
        grid = f"{lat_key},{lon_key}"
        
        if grid not in index['stations']:
            index['stations'][grid] = []
        index['stations'][grid].append(station)
        
        index['bounds']['min_lat'] = min(index['bounds']['min_lat'], station['lat'])
        index['bounds']['max_lat'] = max(index['bounds']['max_lat'], station['lat'])
        index['bounds']['min_lon'] = min(index['bounds']['min_lon'], station['lon'])
        index['bounds']['max_lon'] = max(index['bounds']['max_lon'], station['lon'])
    
    for track in tracks:
        for lon, lat in track['coords']:
            lat_key = int(lat * 10)
            lon_key = int(lon * 10)
            grid = f"{lat_key},{lon_key}"
            
            if grid not in index['tracks']:
                index['tracks'][grid] = []
            
            if track['id'] not in [t['id'] for t in index['tracks'][grid]]:
                index['tracks'][grid].append(track)
            
            index['bounds']['min_lat'] = min(index['bounds']['min_lat'], lat)
            index['bounds']['max_lat'] = max(index['bounds']['max_lat'], lat)
            index['bounds']['min_lon'] = min(index['bounds']['min_lon'], lon)
            index['bounds']['max_lon'] = max(index['bounds']['max_lon'], lon)
    
    return index

def main():
    # Main function
    print("Getting Indian Railways data...")
    
    stations_data = get_stations()
    time.sleep(2)
    tracks_data = get_tracks()
    
    if not stations_data and not tracks_data:
        print("Failed to get data")
        return
    
    print("Parsing stations...")
    stations = parse_stations(stations_data)
    print(f"Found {len(stations)} stations")
    
    print("Parsing tracks...")
    tracks = parse_tracks(tracks_data)
    print(f"Found {len(tracks)} tracks")
    
    print("Building index...")
    index = make_index(stations, tracks)
    
    data = {
        'meta': {
            'source': 'OpenStreetMap',
            'date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'stations': len(stations),
            'tracks': len(tracks),
            'bounds': index['bounds']
        },
        'index': index,
        'stations': stations,
        'tracks': tracks
    }
    
    file = 'rail_data.json'
    print(f"Saving to {file}...")
    
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Done! {len(stations)} stations, {len(tracks)} tracks")

if __name__ == "__main__":
    main()
