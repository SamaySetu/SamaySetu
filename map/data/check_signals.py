import json

# Load the data
data = json.load(open('railway_data.json'))

print(f'Total elements: {len(data["elements"])}')

# Count all signals
signals = [e for e in data['elements'] if e.get('tags', {}).get('railway') == 'signal']
print(f'Total signals: {len(signals)}')

# Count synthetic vs OSM signals
synthetic = [s for s in signals if s.get('tags', {}).get('synthetic') == 'true']
print(f'Synthetic signals: {len(synthetic)}')

osm_signals = [s for s in signals if s.get('tags', {}).get('synthetic') != 'true']
print(f'OSM signals: {len(osm_signals)}')

# Check metadata
if 'metadata' in data:
    print(f'\nMetadata:')
    for key, value in data['metadata'].items():
        print(f'  {key}: {value}')

# Sample a few synthetic signals
if synthetic:
    print(f'\nSample synthetic signals:')
    for i, signal in enumerate(synthetic[:3]):
        print(f'  {i+1}. {signal.get("tags", {}).get("name", "Unknown")} - {signal.get("tags", {}).get("signal_type", "Unknown")}')

# Count by signal type
signal_types = {}
for signal in signals:
    signal_type = signal.get('tags', {}).get('signal_type', 'unspecified')
    signal_types[signal_type] = signal_types.get(signal_type, 0) + 1

print(f'\nSignal types:')
for signal_type, count in sorted(signal_types.items(), key=lambda x: x[1], reverse=True):
    print(f'  {signal_type}: {count}')
