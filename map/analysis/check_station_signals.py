import json
import math

# Load the data
data = json.load(open('railway_data.json'))

signals = [e for e in data['elements'] if e.get('tags', {}).get('railway') == 'signal']
stations = [e for e in data['elements'] if e.get('tags', {}).get('railway') == 'station']

print(f'Total signals: {len(signals)}')
print(f'Total stations: {len(stations)}')

def distance(lat1, lon1, lat2, lon2):
    return math.sqrt((lat1-lat2)**2 + (lon1-lon2)**2)

# Check signals near stations
station_signals = {}
for station in stations[:20]:  # Check first 20 stations
    nearby_signals = []
    for signal in signals:
        if 'lat' in signal and 'lon' in signal and 'lat' in station and 'lon' in station:
            dist = distance(station['lat'], station['lon'], signal['lat'], signal['lon'])
            if dist < 0.01:  # Within ~1km
                signal_name = signal.get('tags', {}).get('name', 'Unknown')
                signal_type = signal.get('tags', {}).get('signal_type', 'unknown')
                nearby_signals.append(f"{signal_name} ({signal_type})")
    
    station_name = station.get('tags', {}).get('name', 'Unknown')
    station_state = station.get('tags', {}).get('state', 'Unknown')
    print(f'\n{station_name} ({station_state}): {len(nearby_signals)} nearby signals')
    for sig in nearby_signals[:3]:  # Show first 3 signals
        print(f'  - {sig}')

# Check signal types distribution
signal_types = {}
synthetic_signals = 0
for signal in signals:
    signal_type = signal.get('tags', {}).get('signal_type', 'unspecified')
    signal_types[signal_type] = signal_types.get(signal_type, 0) + 1
    
    if signal.get('tags', {}).get('synthetic') == 'true':
        synthetic_signals += 1

print(f'\nSignal type distribution:')
for sig_type, count in sorted(signal_types.items(), key=lambda x: x[1], reverse=True):
    print(f'  {sig_type}: {count}')

print(f'\nSynthetic signals: {synthetic_signals}')
print(f'OSM signals: {len(signals) - synthetic_signals}')
