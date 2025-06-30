import json

# Load the updated data
data = json.load(open('data/railway_data.json'))

signals = [e for e in data['elements'] if e.get('tags', {}).get('railway') == 'signal']
print(f'Total signals: {len(signals)}')

# Check signal types
signal_types = {}
synthetic_signals = 0
track_aligned = 0

for signal in signals:
    signal_type = signal.get('tags', {}).get('signal_type', 'unspecified')
    signal_types[signal_type] = signal_types.get(signal_type, 0) + 1
    
    if signal.get('tags', {}).get('synthetic') == 'true':
        synthetic_signals += 1
    
    if signal.get('tags', {}).get('track_aligned') == 'true':
        track_aligned += 1

print(f'\nSignal breakdown:')
print(f'  OSM signals: {len(signals) - synthetic_signals}')
print(f'  Synthetic signals: {synthetic_signals}')
print(f'  Track-aligned signals: {track_aligned}')

print(f'\nSignal type distribution:')
for sig_type, count in sorted(signal_types.items(), key=lambda x: x[1], reverse=True):
    print(f'  {sig_type}: {count}')

# Sample some track-aligned signals
track_aligned_signals = [s for s in signals if s.get('tags', {}).get('track_aligned') == 'true']
print(f'\nSample track-aligned signals:')
for signal in track_aligned_signals[:5]:
    name = signal.get('tags', {}).get('name', 'Unknown')
    sig_type = signal.get('tags', {}).get('signal_type', 'unknown')
    lat, lon = signal['lat'], signal['lon']
    print(f'  - {name} ({sig_type}) at {lat:.4f}, {lon:.4f}')
