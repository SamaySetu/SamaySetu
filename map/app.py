import streamlit as st
import pandas as pd
import json
import os
import folium
from streamlit_folium import st_folium

@st.cache_data
def load_data():
    data_path = os.path.join(os.path.dirname(__file__), 'data', 'railway_data.json')
    with open(data_path, 'r') as f:
        return json.load(f)

def extract_infrastructure(elements):
    # Extract all railway infrastructure
    infrastructure = {
        'stations': [],
        'major_stations': [],  # Combined major stations and junctions
        'signals': [],
        'milestones': [],
        'tracks': []
    }
    
    seen = set()
    nodes = {elem['id']: elem for elem in elements if elem['type'] == 'node'}
    
    for elem in elements:
        if elem['type'] == 'node' and 'lat' in elem and 'lon' in elem:
            # Use element ID instead of coordinates to avoid removing synthetic signals
            # that may be placed close to each other
            key = elem.get('id', f"{elem['lat']},{elem['lon']}")
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
            
            # Categorize by importance and type - combine major stations and junctions
            if railway_type == 'station' or railway_type == 'junction':
                # Check if it's a major station/central/junction by looking for keywords in name
                major_keywords = ['jn', 'junction', 'central', 'terminal', 'main', 'city', 'cantt', 'cantonment']
                is_major = any(keyword in name.lower() for keyword in major_keywords)
                
                if is_major:
                    infrastructure['major_stations'].append({**base_data, 'type': 'major'})
                else:
                    infrastructure['stations'].append({**base_data, 'type': 'regular'})
            elif railway_type == 'signal':
                # Include tags for signal type classification
                signal_data = {**base_data}
                if 'tags' in elem:
                    signal_data['tags'] = elem['tags']
                infrastructure['signals'].append(signal_data)
            elif railway_type == 'milestone' or 'milestone' in elem.get('tags', {}):
                infrastructure['milestones'].append(base_data)
        
        # Extract tracks with proper categorization
        elif elem['type'] == 'way' and elem.get('tags', {}).get('railway') == 'rail':
            if len(elem.get('nodes', [])) > 1:
                coords = []
                for node_id in elem['nodes']:
                    if node_id in nodes:
                        node = nodes[node_id]
                        coords.append([node['lat'], node['lon']])
                
                if len(coords) > 1:
                    state = elem.get('tags', {}).get('state', 'Unknown')
                    # Enhanced track type classification
                    tags = elem.get('tags', {})
                    usage = tags.get('usage', '')
                    service = tags.get('service', '')
                    electrified = tags.get('electrified', '')
                    frequency = tags.get('frequency', '')
                    gauge = tags.get('gauge', '')
                    
                    # Determine track type based on multiple factors
                    if service in ['siding', 'yard', 'spur', 'crossover']:
                        track_type = 'service'
                    elif usage in ['industrial', 'military', 'tourism']:
                        track_type = 'industrial'
                    elif usage in ['branch', 'secondary']:
                        track_type = 'branch'
                    elif usage in ['main', 'trunk']:
                        track_type = 'main'
                    elif electrified in ['yes', 'contact_line', '25000'] or frequency:
                        track_type = 'main'  # Electrified tracks are usually main lines
                    elif gauge and gauge != '1676':  # Non-standard gauge (Indian broad gauge is 1676mm)
                        track_type = 'narrow_gauge'
                    elif usage == '':
                        # No usage specified, make educated guess based on other properties
                        track_type = 'branch'  # Default to branch to avoid everything being main
                    else:
                        track_type = 'other'
                    
                    infrastructure['tracks'].append({
                        'coords': coords,
                        'state': state,
                        'type': track_type,
                        'length': len(coords),  # Track length for sorting
                        'electrified': bool(electrified),
                        'gauge': gauge
                    })
    
    return infrastructure

def create_enhanced_map(infrastructure, selected_states):
    # Center on South India
    m = folium.Map(
        location=[13.0827, 80.2707], 
        zoom_start=6,
        tiles='CartoDB positron'
    )
    
    # Filter by selected states
    def filter_by_state(items):
        return [item for item in items if item['state'] in selected_states]
    
    # Add tracks first (background layer) with different categories and colors
    filtered_tracks = filter_by_state(infrastructure['tracks'])
    
    # Separate tracks by type for better rendering and performance
    track_categories = {
        'main': {'tracks': [], 'color': '#2E8B57', 'weight': 4, 'opacity': 0.8},
        'branch': {'tracks': [], 'color': '#4A7C59', 'weight': 3, 'opacity': 0.7},
        'service': {'tracks': [], 'color': '#8B4513', 'weight': 2, 'opacity': 0.6},
        'industrial': {'tracks': [], 'color': '#FF6347', 'weight': 2, 'opacity': 0.6},
        'narrow_gauge': {'tracks': [], 'color': '#9932CC', 'weight': 2, 'opacity': 0.7},
        'other': {'tracks': [], 'color': '#6B8E23', 'weight': 2, 'opacity': 0.5}
    }
    
    # Categorize tracks
    for track in filtered_tracks:
        track_type = track.get('type', 'other')
        if track_type in track_categories:
            track_categories[track_type]['tracks'].append(track)
        else:
            track_categories['other']['tracks'].append(track)
    
    # Render tracks by category with improved limits and connectivity focus
    limits = {'main': 800, 'branch': 600, 'service': 200, 'industrial': 150, 'narrow_gauge': 150, 'other': 150}
    
    for category, data in track_categories.items():
        tracks = data['tracks']
        
        # Instead of just sorting by length, try to maintain better connectivity
        # Sort by a combination of length and coordinate density
        tracks.sort(key=lambda x: (len(x.get('coords', [])), x.get('length', 0)), reverse=True)
        
        # Show more tracks for better connectivity, especially for main and branch lines
        selected_tracks = tracks[:limits[category]]
        
        for track in selected_tracks:
            # Enhanced popup with speed limit information if available
            popup_text = f"🛤️ {category.title()} Track"
            tooltip_text = f"{category.title()} Track"
            
            if track.get('electrified'):
                popup_text += " (Electrified)"
            
            # Add speed limit information if available
            if 'speed_limit_kmh' in track:
                speed_limit = track['speed_limit_kmh']
                classification = track.get('classification', 'unknown')
                popup_text += f"<br>� Speed Limit: {speed_limit} km/h ({classification})"
                tooltip_text += f" | {speed_limit} km/h"
                
                # Color-code tracks by speed limit for better visualization
                if speed_limit >= 130:
                    track_color = '#E74C3C'  # Red for high speed
                elif speed_limit >= 100:
                    track_color = '#F39C12'  # Orange for express
                elif speed_limit >= 80:
                    track_color = '#F1C40F'  # Yellow for fast
                elif speed_limit >= 60:
                    track_color = '#2ECC71'  # Green for medium
                else:
                    track_color = '#3498DB'  # Blue for slow/restricted
            else:
                track_color = data['color']  # Use default color if no speed limit
            
            folium.PolyLine(
                locations=track['coords'],
                color=track_color,
                weight=data['weight'],
                opacity=data['opacity'],
                popup=popup_text,
                tooltip=tooltip_text
            ).add_to(m)
    
    # Add milestones (smallest)
    filtered_milestones = filter_by_state(infrastructure['milestones'])
    for milestone in filtered_milestones[:100]:
        folium.CircleMarker(
            location=[milestone['lat'], milestone['lon']],
            radius=2,
            popup=f"📏 {milestone['name']}",
            tooltip=f"Milestone: {milestone['name']}",
            color='#95A5A6',
            fillColor='#95A5A6',
            fillOpacity=0.7,
            weight=1
        ).add_to(m)
    
    # Add signals with intelligent prioritization
    filtered_signals = filter_by_state(infrastructure['signals'])
    
    # Prioritize signals for display: station signals first, then others
    station_signals = []
    junction_signals = []
    block_signals = []
    other_signals = []
    
    for signal in filtered_signals:
        signal_type = signal.get('tags', {}).get('signal_type', 'unspecified')
        signal_function = signal.get('tags', {}).get('signal_function', 'unknown')
        
        if signal_type in ['outer', 'home', 'distant', 'starter']:
            station_signals.append(signal)
        elif signal_type == 'junction' or signal_function == 'interlocking':
            junction_signals.append(signal)
        elif signal_type == 'block' or signal_function == 'block':
            block_signals.append(signal)
        else:
            other_signals.append(signal)
    
    # Display signals in priority order with appropriate limits
    signals_to_display = (
        station_signals[:500] +           # Show more station-related signals
        junction_signals[:300] +          # Show junction signals
        block_signals[:800] +             # Show many block signals for network coverage
        other_signals[:200]               # Show some other signals
    )
    
    # Add different colors for different signal types
    for signal in signals_to_display:
        signal_type = signal.get('tags', {}).get('signal_type', 'unspecified')
        signal_function = signal.get('tags', {}).get('signal_function', 'unknown')
        
        # Choose color based on signal type/function
        if signal_type in ['outer', 'home', 'distant', 'starter']:
            color = '#E74C3C'  # Red for station signals
            radius = 4
        elif signal_type == 'junction' or signal_function == 'interlocking':
            color = '#9B59B6'  # Purple for junction signals
            radius = 5
        elif signal_type == 'block' or signal_function == 'block':
            color = '#3498DB'  # Blue for block signals
            radius = 3
        else:
            color = '#F39C12'  # Orange for other signals
            radius = 3
        
        # Enhanced popup with signal details
        signal_name = signal.get('name', 'Unknown Signal')
        signal_details = f"🚦 {signal_name}"
        if signal_type != 'unspecified':
            signal_details += f"<br>Type: {signal_type.title()}"
        if signal_function != 'unknown':
            signal_details += f"<br>Function: {signal_function.title()}"
        if signal.get('tags', {}).get('synthetic') == 'true':
            signal_details += f"<br><small>Synthetic Signal</small>"
        
        folium.CircleMarker(
            location=[signal['lat'], signal['lon']],
            radius=radius,
            popup=folium.Popup(signal_details, max_width=250),
            tooltip=f"Signal: {signal_name}",
            color=color,
            fillColor=color,
            fillOpacity=0.8,
            weight=1
        ).add_to(m)
    
    # Add regular stations with importance-based sizing and coloring
    filtered_stations = filter_by_state(infrastructure['stations'])
    for station in filtered_stations[:400]:
        # Determine radius and color based on importance if available
        radius = 4
        color = '#3498DB'  # Default blue
        importance_info = ""
        
        if 'importance_score' in station:
            importance_score = station['importance_score']
            importance_category = station.get('importance_category', 'unknown')
            
            # Size based on importance
            if importance_score >= 80:
                radius = 7
                color = '#E74C3C'  # Red for critical
            elif importance_score >= 65:
                radius = 6
                color = '#E67E22'  # Orange for major
            elif importance_score >= 50:
                radius = 5
                color = '#F39C12'  # Dark orange for important
            elif importance_score >= 35:
                radius = 4
                color = '#F1C40F'  # Yellow for moderate
            else:
                radius = 3
                color = '#3498DB'  # Blue for minor/local
            
            importance_info = f"<br><span style='color: #8E44AD;'>📊 Importance: {importance_score:.1f} ({importance_category})</span>"
            if 'importance_rank' in station:
                importance_info += f"<br><span style='color: #8E44AD;'>🏆 Rank: #{station['importance_rank']}</span>"
        
        folium.CircleMarker(
            location=[station['lat'], station['lon']],
            radius=radius,
            popup=folium.Popup(
                f"""
                <div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px;">
                    <b style="color: #2E86AB;">🚉 {station['name']}</b><br>
                    <span style="color: #666;">📍 {station['state']}</span>{importance_info}<br>
                    <span style="color: #888; font-size: 12px;">{station['lat']:.4f}, {station['lon']:.4f}</span>
                </div>
                """, 
                max_width=280
            ),
            tooltip=f"Station: {station['name']}" + (f" (Score: {station.get('importance_score', 0):.1f})" if 'importance_score' in station else ""),
            color=color,
            fillColor=color,
            fillOpacity=0.9,
            weight=1
        ).add_to(m)
    
    # Add major stations/junctions with enhanced importance information
    filtered_major_stations = filter_by_state(infrastructure['major_stations'])
    for station in filtered_major_stations:
        # Enhanced sizing and coloring for major stations
        radius = 10
        color = '#8E44AD'  # Default purple
        importance_info = ""
        
        if 'importance_score' in station:
            importance_score = station['importance_score']
            importance_category = station.get('importance_category', 'unknown')
            
            # Enhanced size and color for major stations based on importance
            if importance_score >= 80:
                radius = 14
                color = '#C0392B'  # Dark red for critical major stations
            elif importance_score >= 65:
                radius = 12
                color = '#E74C3C'  # Red for major
            else:
                radius = 10
                color = '#8E44AD'  # Purple for regular major
            
            importance_info = f"<br><span style='color: #E74C3C;'>📊 Importance: {importance_score:.1f} ({importance_category})</span>"
            if 'importance_rank' in station:
                importance_info += f"<br><span style='color: #E74C3C;'>🏆 Rank: #{station['importance_rank']}</span>"
        
        folium.CircleMarker(
            location=[station['lat'], station['lon']],
            radius=radius,
            popup=folium.Popup(
                f"""
                <div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 16px;">
                    <b style="color: #8E44AD;">🏛️ {station['name']}</b><br>
                    <span style="color: #666;">📍 {station['state']}</span><br>
                    <span style="color: #8E44AD; font-weight: bold;">Major Station/Junction</span>{importance_info}<br>
                    <span style="color: #888; font-size: 12px;">{station['lat']:.4f}, {station['lon']:.4f}</span>
                </div>
                """, 
                max_width=300
            ),
            tooltip=f"Major Station: {station['name']}" + (f" (Score: {station.get('importance_score', 0):.1f})" if 'importance_score' in station else ""),
            color=color,
            fillColor=color,
            fillOpacity=1.0,
            weight=3
        ).add_to(m)
    
    return m

def add_legend(m):
    # Add a custom legend to the map with enhanced information
    legend_html = '''
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 280px; height: auto; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:12px; font-family: 'Segoe UI', Arial, sans-serif;
                padding: 10px; border-radius: 10px; box-shadow: 0 0 15px rgba(0,0,0,0.2);">
        <h4 style="margin: 0 0 8px 0; color: #2C3E50;">🗺️ Railway Infrastructure</h4>
        
        <div style="border-bottom: 1px solid #eee; padding-bottom: 6px; margin-bottom: 6px;">
            <b>Station Importance (Size & Color)</b>
        </div>
        <p style="margin: 3px 0; color: #C0392B;"><span style="color: #C0392B; font-size: 18px;">●</span> Critical (80+ score)</p>
        <p style="margin: 3px 0; color: #E74C3C;"><span style="color: #E74C3C; font-size: 16px;">●</span> Major (65+ score)</p>
        <p style="margin: 3px 0; color: #F39C12;"><span style="color: #F39C12; font-size: 14px;">●</span> Important (50+ score)</p>
        <p style="margin: 3px 0; color: #F1C40F;"><span style="color: #F1C40F; font-size: 12px;">●</span> Moderate (35+ score)</p>
        <p style="margin: 3px 0; color: #3498DB;"><span style="color: #3498DB; font-size: 10px;">●</span> Minor/Local (&lt;35 score)</p>
        
        <div style="border-bottom: 1px solid #eee; padding-bottom: 6px; margin: 6px 0;">
            <b>Railway Signals</b>
        </div>
        <p style="margin: 2px 0; color: #E74C3C;"><span style="color: #E74C3C; font-size: 10px;">●</span> Station Signals (Home/Distant/Outer)</p>
        <p style="margin: 2px 0; color: #9B59B6;"><span style="color: #9B59B6; font-size: 11px;">●</span> Junction/Interlocking Signals</p>
        <p style="margin: 2px 0; color: #3498DB;"><span style="color: #3498DB; font-size: 9px;">●</span> Block Signals</p>
        <p style="margin: 2px 0; color: #F39C12;"><span style="color: #F39C12; font-size: 9px;">●</span> Other Signals</p>
        <p style="margin: 3px 0; color: #95A5A6;"><span style="color: #95A5A6; font-size: 8px;">●</span> Milestones</p>
        
        <div style="border-bottom: 1px solid #eee; padding-bottom: 6px; margin: 6px 0;">
            <b>Track Speed Limits (Color Coded)</b>
        </div>
        <p style="margin: 2px 0; color: #E74C3C;"><span style="font-weight: bold; color: #E74C3C;">━━━</span> High Speed (130+ km/h)</p>
        <p style="margin: 2px 0; color: #F39C12;"><span style="font-weight: bold; color: #F39C12;">━━━</span> Express (100-129 km/h)</p>
        <p style="margin: 2px 0; color: #F1C40F;"><span style="font-weight: bold; color: #F1C40F;">━━━</span> Fast (80-99 km/h)</p>
        <p style="margin: 2px 0; color: #2ECC71;"><span style="font-weight: bold; color: #2ECC71;">━━━</span> Medium (60-79 km/h)</p>
        <p style="margin: 2px 0; color: #3498DB;"><span style="font-weight: bold; color: #3498DB;">━━━</span> Slow/Restricted (&lt;60 km/h)</p>
        
        <div style="border-bottom: 1px solid #eee; padding-bottom: 6px; margin: 6px 0;">
            <b>Track Types</b>
        </div>
        <p style="margin: 2px 0; color: #2E8B57;"><span style="font-weight: bold; color: #2E8B57;">━━━</span> Main Lines</p>
        <p style="margin: 2px 0; color: #4A7C59;"><span style="font-weight: bold; color: #4A7C59;">━━</span> Branch Lines</p>
        <p style="margin: 2px 0; color: #8B4513;"><span style="color: #8B4513;">━━</span> Service Tracks</p>
        <p style="margin: 2px 0; color: #FF6347;"><span style="color: #FF6347;">━━</span> Industrial</p>
        <p style="margin: 2px 0; color: #9932CC;"><span style="color: #9932CC;">━━</span> Narrow Gauge</p>
        <p style="margin: 2px 0; color: #6B8E23;"><span style="color: #6B8E23;">━</span> Other Tracks</p>
        
        <div style="margin-top: 8px; font-size: 10px; color: #7F8C8D;">
            💡 Hover/click elements for detailed info
        </div>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    return m

def analyze_track_connectivity(tracks):
    """Analyze track connectivity to help diagnose rendering issues"""
    if not tracks:
        return {}
    
    # Collect all endpoints
    endpoints = {}
    track_count_by_length = {}
    
    for i, track in enumerate(tracks):
        coords = track.get('coords', [])
        if len(coords) < 2:
            continue
            
        # Track length distribution
        length_bucket = len(coords) // 10 * 10  # Group by tens
        track_count_by_length[length_bucket] = track_count_by_length.get(length_bucket, 0) + 1
        
        # Check endpoints for potential connections
        start_point = tuple(coords[0])
        end_point = tuple(coords[-1])
        
        # Count endpoint occurrences (for connectivity analysis)
        endpoints[start_point] = endpoints.get(start_point, 0) + 1
        endpoints[end_point] = endpoints.get(end_point, 0) + 1
    
    # Find potential connection points (endpoints shared by multiple tracks)
    connection_points = {point: count for point, count in endpoints.items() if count > 1}
    
    return {
        'total_tracks': len(tracks),
        'length_distribution': track_count_by_length,
        'connection_points': len(connection_points),
        'isolated_endpoints': len([count for count in endpoints.values() if count == 1])
    }

def main():
    st.set_page_config(
        page_title="SamaySetu Railway Map",
        page_icon="🚂",
        layout="wide"
    )
    
    st.title("🚂 SamaySetu Railway Network")
    st.markdown("Interactive visualization of railway infrastructure across South India")
    
    # Load data
    try:
        data = load_data()
        elements = data.get('elements', [])
        
        # Extract all infrastructure
        infrastructure = extract_infrastructure(elements)
        
        # Sidebar controls
        st.sidebar.header("🎛️ Filters")
        
        # Get all available states from all infrastructure types
        all_states = set()
        for infra_type in infrastructure.values():
            for item in infra_type:
                if item.get('state') and item['state'] != 'Unknown':
                    all_states.add(item['state'])
        
        available_states = sorted(list(all_states))
        
        selected_states = st.sidebar.multiselect(
            "Select States",
            available_states,
            default=available_states
        )
        
        # Infrastructure type filters
        st.sidebar.subheader("🔧 Infrastructure Types")
        show_tracks = st.sidebar.checkbox("Railway Tracks", value=True)
        show_stations = st.sidebar.checkbox("Regular Stations", value=True)
        show_major_stations = st.sidebar.checkbox("Major Stations/Junctions", value=True)
        show_signals = st.sidebar.checkbox("Signals", value=True)
        show_milestones = st.sidebar.checkbox("Milestones", value=True)
        
        # Stats
        if selected_states:
            # Filter by selected states
            def filter_by_state(items):
                return [item for item in items if item.get('state') in selected_states]
            
            filtered_infrastructure = {
                'stations': filter_by_state(infrastructure['stations']),
                'major_stations': filter_by_state(infrastructure['major_stations']),
                'signals': filter_by_state(infrastructure['signals']),
                'milestones': filter_by_state(infrastructure['milestones']),
                'tracks': filter_by_state(infrastructure['tracks'])
            }
            
            # Display metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("🚉 Regular Stations", len(filtered_infrastructure['stations']))
            with col2:
                st.metric("🏛️ Major Stations/Junctions", len(filtered_infrastructure['major_stations']))
            with col3:
                st.metric("🚦 Signals", len(filtered_infrastructure['signals']))
            with col4:
                st.metric("📏 Milestones", len(filtered_infrastructure['milestones']))
            with col5:
                st.metric("🛤️ Track Segments", len(filtered_infrastructure['tracks']))
            
            # Track breakdown by category
            if show_tracks and len(filtered_infrastructure['tracks']) > 0:
                st.sidebar.markdown("### 🛤️ Track Categories")
                track_categories = {}
                total_coords = 0
                
                for track in filtered_infrastructure['tracks']:
                    track_type = track.get('type', 'other')
                    track_categories[track_type] = track_categories.get(track_type, 0) + 1
                    total_coords += len(track.get('coords', []))
                
                # Sort by count and display
                for track_type, count in sorted(track_categories.items(), key=lambda x: x[1], reverse=True):
                    st.sidebar.text(f"{track_type.title()}: {count}")
                
                # Show additional track statistics for debugging
                st.sidebar.markdown("#### Track Analysis")
                st.sidebar.text(f"Total coordinate points: {total_coords}")
                st.sidebar.text(f"Avg points per track: {total_coords/len(filtered_infrastructure['tracks']):.1f}")
                
                # Show electrification info
                electrified_count = sum(1 for track in filtered_infrastructure['tracks'] if track.get('electrified'))
                if electrified_count > 0:
                    st.sidebar.text(f"⚡ Electrified: {electrified_count}")
                
                # Show track length distribution
                track_lengths = [len(track.get('coords', [])) for track in filtered_infrastructure['tracks']]
                if track_lengths:
                    st.sidebar.text(f"Longest track: {max(track_lengths)} points")
                    st.sidebar.text(f"Shortest track: {min(track_lengths)} points")
                
                # Connectivity analysis
                if st.sidebar.checkbox("Show Connectivity Analysis", value=False):
                    connectivity = analyze_track_connectivity(filtered_infrastructure['tracks'])
                    st.sidebar.markdown("#### Connectivity Analysis")
                    st.sidebar.text(f"Connection points: {connectivity['connection_points']}")
                    st.sidebar.text(f"Isolated endpoints: {connectivity['isolated_endpoints']}")
                    st.sidebar.text("Length distribution:")
                    for length, count in sorted(connectivity['length_distribution'].items()):
                        st.sidebar.text(f"  {length}-{length+9} points: {count} tracks")
            
            # Create and display map
            if any(len(filtered_infrastructure[key]) > 0 for key in filtered_infrastructure.keys()):
                st.subheader("🗺️ Railway Infrastructure Map")
                
                # Apply infrastructure type filters
                display_infrastructure = {
                    'stations': filtered_infrastructure['stations'] if show_stations else [],
                    'major_stations': filtered_infrastructure['major_stations'] if show_major_stations else [],
                    'signals': filtered_infrastructure['signals'] if show_signals else [],
                    'milestones': filtered_infrastructure['milestones'] if show_milestones else [],
                    'tracks': filtered_infrastructure['tracks'] if show_tracks else []
                }
                
                # Create enhanced map with all infrastructure
                m = create_enhanced_map(display_infrastructure, selected_states)
                
                # Add legend
                m = add_legend(m)
                
                # Display the map
                map_data = st_folium(m, width=1200, height=700)
                
                # Map usage guide
                st.caption("💡 Click markers for details • Different colors represent different infrastructure types • Use sidebar filters to toggle visibility")
                
                # Show enhanced analytics if available
                if 'infrastructure_analysis' in data:
                    analysis = data['infrastructure_analysis']
                    
                    if st.expander("🚄 Speed Limits & Station Rankings"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("🚅 Speed Limit Analysis")
                            if 'speed_statistics' in analysis:
                                speed_stats = analysis['speed_statistics']
                                st.metric("Tracks with Speed Limits", speed_stats.get('total_tracks', 0))
                                st.metric("Average Speed Limit", f"{speed_stats.get('average_speed', 0):.1f} km/h")
                                
                                if 'classification_distribution' in speed_stats:
                                    st.write("**Speed Classifications:**")
                                    for classification, count in speed_stats['classification_distribution'].items():
                                        st.write(f"• {classification.title()}: {count} tracks")
                                
                                if 'speed_distribution' in speed_stats:
                                    st.write("**Speed Distribution:**")
                                    for speed_range, count in speed_stats['speed_distribution'].items():
                                        st.write(f"• {speed_range} km/h: {count} tracks")
                        
                        with col2:
                            st.subheader("🏛️ Station Importance Rankings")
                            if 'station_rankings' in analysis:
                                rankings = analysis['station_rankings']
                                st.metric("Ranked Stations", rankings.get('total_stations', 0))
                                st.metric("Average Importance Score", f"{rankings.get('average_score', 0):.1f}")
                                
                                # Show ridership data sources
                                if 'ridership_data_sources' in rankings:
                                    st.write("**Ridership Data Sources:**")
                                    sources = rankings['ridership_data_sources']
                                    if 'wikipedia' in sources:
                                        st.write(f"• Wikipedia: {sources['wikipedia']} stations")
                                    if 'known_data' in sources:
                                        st.write(f"• Known data: {sources['known_data']} stations")
                                    if 'estimated' in sources:
                                        st.write(f"• Estimated: {sources['estimated']} stations")
                                
                                if 'category_distribution' in rankings:
                                    st.write("**Importance Categories:**")
                                    for category, count in rankings['category_distribution'].items():
                                        st.write(f"• {category.title()}: {count} stations")
                                
                                if 'top_10_stations' in rankings:
                                    st.write("**Top 5 Most Important Stations:**")
                                    for i, station in enumerate(rankings['top_10_stations'][:5], 1):
                                        ridership_text = ""
                                        if station.get('daily_ridership') != 'N/A':
                                            ridership_text = f" ({station['daily_ridership']:,} daily)"
                                        st.write(f"{i}. {station['name']} ({station['score']:.1f}) - {station['category'].title()}{ridership_text}")
                
                # Detailed breakdown
                if st.expander("📊 Infrastructure Breakdown"):
                    st.subheader("Station Details")
                    
                    all_stations = filtered_infrastructure['stations'] + filtered_infrastructure['major_stations']
                    major_stations = filtered_infrastructure['major_stations']
                    regular_stations = filtered_infrastructure['stations']
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Major Stations/Junctions", len(major_stations))
                        if major_stations:
                            st.write("**Major Stations/Junctions:**")
                            for station in major_stations[:10]:  # Show first 10
                                st.write(f"• {station['name']} ({station['state']})")
                    
                    with col2:
                        st.metric("Regular Stations", len(regular_stations))
                        if regular_stations:
                            st.write("**Regular Stations (sample):**")
                            for station in regular_stations[:10]:  # Show first 10
                                st.write(f"• {station['name']} ({station['state']})")
                
                # Station search
                st.subheader("🔍 Infrastructure Search")
                all_infrastructure_items = []
                for infra_type, items in filtered_infrastructure.items():
                    for item in items:
                        item_copy = item.copy()
                        item_copy['type'] = infra_type
                        all_infrastructure_items.append(item_copy)
                
                if all_infrastructure_items:
                    search_options = [f"{item['name']} ({item['type']}) - {item['state']}" 
                                    for item in all_infrastructure_items if item.get('name', 'Unknown') != 'Unknown']
                    
                    if search_options:
                        selected_item = st.selectbox("Search for infrastructure:", [""] + search_options)
                        
                        if selected_item:
                            # Find the selected item
                            selected_name = selected_item.split(' (')[0]
                            selected_type = selected_item.split('(')[1].split(')')[0]
                            
                            for item in all_infrastructure_items:
                                if item['name'] == selected_name and item['type'] == selected_type:
                                    col1, col2, col3, col4 = st.columns(4)
                                    with col1:
                                        st.write(f"**Name:** {item['name']}")
                                    with col2:
                                        st.write(f"**Type:** {item['type'].title()}")
                                    with col3:
                                        st.write(f"**State:** {item['state']}")
                                    with col4:
                                        if 'lat' in item and 'lon' in item:
                                            st.write(f"**Coordinates:** {item['lat']:.4f}, {item['lon']:.4f}")
                                    break
            else:
                st.info("No infrastructure found for selected states and filters.")
            
            # Data export option
            if st.checkbox("🗂️ Show Infrastructure Data"):
                tab1, tab2, tab3, tab4, tab5 = st.tabs(["Regular Stations", "Major Stations/Junctions", "Signals", "Milestones", "Track Segments"])
                
                with tab1:
                    if filtered_infrastructure['stations']:
                        df = pd.DataFrame(filtered_infrastructure['stations'])
                        # Show importance rankings if available
                        if 'importance_score' in df.columns:
                            df = df.sort_values('importance_score', ascending=False)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No regular stations found")
                
                with tab2:
                    if filtered_infrastructure['major_stations']:
                        df = pd.DataFrame(filtered_infrastructure['major_stations'])
                        # Show importance rankings if available
                        if 'importance_score' in df.columns:
                            df = df.sort_values('importance_score', ascending=False)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No major stations/junctions found")
                
                with tab3:
                    if filtered_infrastructure['signals']:
                        df = pd.DataFrame(filtered_infrastructure['signals'])
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No signals found")
                
                with tab4:
                    if filtered_infrastructure['milestones']:
                        df = pd.DataFrame(filtered_infrastructure['milestones'])
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No milestones found")
                
                with tab5:
                    if filtered_infrastructure['tracks']:
                        # For tracks, show enhanced info including speed limits
                        track_info = []
                        for t in filtered_infrastructure['tracks']:
                            info = {
                                'state': t['state'], 
                                'type': t.get('type', 'main'), 
                                'points': len(t['coords']),
                                'electrified': t.get('electrified', False)
                            }
                            # Add speed limit info if available
                            if 'speed_limit_kmh' in t:
                                info['speed_limit_kmh'] = t['speed_limit_kmh']
                                info['classification'] = t.get('classification', 'unknown')
                                if 'factors' in t:
                                    info['curvature'] = t['factors'].get('curvature', 0)
                                    info['urban'] = t['factors'].get('urban', False)
                            track_info.append(info)
                        
                        df = pd.DataFrame(track_info)
                        if 'speed_limit_kmh' in df.columns:
                            df = df.sort_values('speed_limit_kmh', ascending=False)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No tracks found")
        else:
            st.warning("Please select at least one state to view the map.")
            
    except FileNotFoundError:
        st.error("Railway data not found. Please run the data fetch script first.")
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.exception(e)  # Show full traceback for debugging

if __name__ == "__main__":
    main()
