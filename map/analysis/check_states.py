import json
import os

# Get the correct path to the data file
script_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(script_dir, 'railway_data.json')

# Load the data
try:
    with open(data_path, 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"Could not find railway_data.json at: {data_path}")
    print("Please make sure the file exists in the map/data/ directory")
    exit(1)

# Count all signals
signals = [e for e in data['elements'] if e.get('tags', {}).get('railway') == 'signal']
print(f'Total signals: {len(signals)}')

# Count by state
state_counts = {}
for signal in signals:
    state = signal.get('tags', {}).get('state', 'Unknown')
    state_counts[state] = state_counts.get(state, 0) + 1

print(f'\nSignals by state:')
for state, count in sorted(state_counts.items(), key=lambda x: x[1], reverse=True):
    print(f'  {state}: {count}')

# Check for signals with invalid coordinates
invalid_coords = 0
for signal in signals:
    if 'lat' not in signal or 'lon' not in signal:
        invalid_coords += 1

print(f'\nSignals with invalid coordinates: {invalid_coords}')

# Check Tamil Nadu specifically (since that's likely what the user is filtering)
tn_signals = [s for s in signals if s.get('tags', {}).get('state') == 'Tamil Nadu']
print(f'\nTamil Nadu signals: {len(tn_signals)}')

# Check coordinate ranges to see if there are any outliers
lats = [s['lat'] for s in signals if 'lat' in s]
lons = [s['lon'] for s in signals if 'lon' in s]

if lats and lons:
    print(f'\nCoordinate ranges:')
    print(f'  Latitude: {min(lats):.4f} to {max(lats):.4f}')
    print(f'  Longitude: {min(lons):.4f} to {max(lons):.4f}')

# Check signal types
signal_types = {}
synthetic_count = 0
osm_count = 0

for signal in signals:
    if signal.get('tags', {}).get('synthetic') == 'true':
        synthetic_count += 1
        signal_function = signal.get('tags', {}).get('signal_function', 'unknown')
        signal_types[signal_function] = signal_types.get(signal_function, 0) + 1
    else:
        osm_count += 1

print(f'\nSignal breakdown:')
print(f'  OSM signals: {osm_count}')
print(f'  Synthetic signals: {synthetic_count}')

if signal_types:
    print(f'\nSynthetic signal types:')
    for sig_type, count in sorted(signal_types.items(), key=lambda x: x[1], reverse=True):
        print(f'  {sig_type}: {count}')
