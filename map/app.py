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
                infrastructure['signals'].append(base_data)
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
    
    # Render tracks by category with performance-optimized limits
    limits = {'main': 300, 'branch': 200, 'service': 100, 'industrial': 50, 'narrow_gauge': 50, 'other': 50}
    
    for category, data in track_categories.items():
        tracks = data['tracks']
        
        # Simple length-based selection for performance
        # Take the first N tracks (they're already in a reasonable order from OSM)
        selected_tracks = tracks[:limits[category]]
        
        for track in selected_tracks:
            # Add a subtle glow effect by drawing a thicker, more transparent line underneath
            folium.PolyLine(
                locations=track['coords'],
                color=data['color'],
                weight=data['weight'] + 3,
                opacity=data['opacity'] * 0.2,
                interactive=False  # This line won't be interactive to avoid selection box
            ).add_to(m)
            
            # Add the main track line on top
            folium.PolyLine(
                locations=track['coords'],
                color=data['color'],
                weight=data['weight'],
                opacity=data['opacity'],
                tooltip=f"{category.title()} Track" + (f" (Electrified)" if track.get('electrified') else ""),
                # Add custom options to reduce selection artifacts
                options={'bubblingMouseEvents': False}
            ).add_to(m)
    
    # Add milestones (smallest) - reduced for performance
    filtered_milestones = filter_by_state(infrastructure['milestones'])
    for milestone in filtered_milestones[:50]:  # Reduced from 100
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
    
    # Add signals - reduced for performance
    filtered_signals = filter_by_state(infrastructure['signals'])
    for signal in filtered_signals[:150]:  # Reduced from 300
        folium.CircleMarker(
            location=[signal['lat'], signal['lon']],
            radius=3,
            popup=f"🚦 Signal: {signal['name']}",
            tooltip=f"Signal: {signal['name']}",
            color='#F39C12',
            fillColor='#F39C12',
            fillOpacity=0.8,
            weight=1
        ).add_to(m)
    
    # Add regular stations - reduced for performance
    filtered_stations = filter_by_state(infrastructure['stations'])
    for station in filtered_stations[:200]:  # Reduced from 400
        folium.CircleMarker(
            location=[station['lat'], station['lon']],
            radius=4,
            popup=folium.Popup(
                f"""
                <div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px;">
                    <b style="color: #2E86AB;">🚉 {station['name']}</b><br>
                    <span style="color: #666;">📍 {station['state']}</span><br>
                    <span style="color: #888; font-size: 12px;">{station['lat']:.4f}, {station['lon']:.4f}</span>
                </div>
                """, 
                max_width=280
            ),
            tooltip=f"Station: {station['name']}",
            color='#3498DB',
            fillColor='#3498DB',
            fillOpacity=0.9,
            weight=1
        ).add_to(m)
    
    # Add major stations/junctions (combined category - most prominent)
    filtered_major_stations = filter_by_state(infrastructure['major_stations'])
    for station in filtered_major_stations:
        folium.CircleMarker(
            location=[station['lat'], station['lon']],
            radius=10,
            popup=folium.Popup(
                f"""
                <div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 16px;">
                    <b style="color: #8E44AD;">🏛️ {station['name']}</b><br>
                    <span style="color: #666;">📍 {station['state']}</span><br>
                    <span style="color: #8E44AD; font-weight: bold;">Major Station/Junction</span><br>
                    <span style="color: #888; font-size: 12px;">{station['lat']:.4f}, {station['lon']:.4f}</span>
                </div>
                """, 
                max_width=300
            ),
            tooltip=f"Major Station: {station['name']}",
            color='#8E44AD',
            fillColor='#8E44AD',
            fillOpacity=1.0,
            weight=3
        ).add_to(m)
    
    return m

def add_legend(m):
    # Add a custom legend to the map
    legend_html = '''
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 240px; height: auto; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:13px; font-family: 'Segoe UI', Arial, sans-serif;
                padding: 10px; border-radius: 10px; box-shadow: 0 0 15px rgba(0,0,0,0.2);">
        <h4 style="margin: 0 0 8px 0; color: #2C3E50;">🗺️ Railway Infrastructure</h4>
        <div style="border-bottom: 1px solid #eee; padding-bottom: 6px; margin-bottom: 6px;">
            <b>Stations & Infrastructure</b>
        </div>
        <p style="margin: 3px 0; color: #8E44AD;"><span style="color: #8E44AD; font-size: 16px;">●</span> Major Stations/Junctions</p>
        <p style="margin: 3px 0; color: #3498DB;"><span style="color: #3498DB; font-size: 12px;">●</span> Regular Stations</p>
        <p style="margin: 3px 0; color: #F39C12;"><span style="color: #F39C12; font-size: 10px;">●</span> Signals</p>
        <p style="margin: 3px 0; color: #95A5A6;"><span style="color: #95A5A6; font-size: 8px;">●</span> Milestones</p>
        <div style="border-bottom: 1px solid #eee; padding-bottom: 6px; margin: 6px 0;">
            <b>Railway Tracks</b>
        </div>
        <p style="margin: 2px 0; color: #2E8B57;"><span style="font-weight: bold; color: #2E8B57;">━━━</span> Main Lines</p>
        <p style="margin: 2px 0; color: #4A7C59;"><span style="font-weight: bold; color: #4A7C59;">━━</span> Branch Lines</p>
        <p style="margin: 2px 0; color: #8B4513;"><span style="color: #8B4513;">━━</span> Service Tracks</p>
        <p style="margin: 2px 0; color: #FF6347;"><span style="color: #FF6347;">━━</span> Industrial</p>
        <p style="margin: 2px 0; color: #9932CC;"><span style="color: #9932CC;">━━</span> Narrow Gauge</p>
        <p style="margin: 2px 0; color: #6B8E23;"><span style="color: #6B8E23;">━</span> Other Tracks</p>
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
        show_signals = st.sidebar.checkbox("Signals", value=False)  # Default off for performance
        show_milestones = st.sidebar.checkbox("Milestones", value=False)  # Default off for performance
        
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
                
                # Connectivity analysis (lightweight version)
                if st.sidebar.checkbox("Show Basic Track Info", value=False):
                    connectivity = analyze_track_connectivity(filtered_infrastructure['tracks'][:100])  # Analyze only first 100 tracks
                    st.sidebar.markdown("#### Basic Track Info (Sample)")
                    st.sidebar.text(f"Sample size: 100 tracks")
                    st.sidebar.text(f"Connection points: {connectivity['connection_points']}")
                    st.sidebar.text(f"Isolated endpoints: {connectivity['isolated_endpoints']}")
            
            # Create and display map
            if any(len(filtered_infrastructure[key]) > 0 for key in filtered_infrastructure.keys()):
                st.subheader("🗺️ Railway Infrastructure Map")
                st.info("💡 **Performance Note**: Map shows a subset of tracks for faster loading. Enable signals/milestones in sidebar for more detail.")
                
                # Apply infrastructure type filters
                display_infrastructure = {
                    'stations': filtered_infrastructure['stations'] if show_stations else [],
                    'major_stations': filtered_infrastructure['major_stations'] if show_major_stations else [],
                    'signals': filtered_infrastructure['signals'] if show_signals else [],
                    'milestones': filtered_infrastructure['milestones'] if show_milestones else [],
                    'tracks': filtered_infrastructure['tracks'] if show_tracks else []
                }
                
                # Show loading message
                with st.spinner('Loading map... This may take a moment.'):
                    # Create enhanced map with all infrastructure
                    m = create_enhanced_map(display_infrastructure, selected_states)
                    
                    # Add legend
                    m = add_legend(m)
                
                # Display the map with optimized size for faster loading
                map_data = st_folium(m, width=1200, height=500)
                
                # Map usage guide
                st.caption("💡 Click markers for details • Different colors represent different infrastructure types • Use sidebar filters to toggle visibility")
                
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
                tab1, tab2, tab3, tab4, tab5 = st.tabs(["Regular Stations", "Major Stations/Junctions", "Signals", "Milestones", "Tracks"])
                
                with tab1:
                    if filtered_infrastructure['stations']:
                        df = pd.DataFrame(filtered_infrastructure['stations'])
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No regular stations found")
                
                with tab2:
                    if filtered_infrastructure['major_stations']:
                        df = pd.DataFrame(filtered_infrastructure['major_stations'])
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
                        # For tracks, show simplified info (coordinates are too complex for dataframe)
                        track_info = [{'state': t['state'], 'type': t.get('type', 'main'), 'points': len(t['coords'])} 
                                    for t in filtered_infrastructure['tracks']]
                        df = pd.DataFrame(track_info)
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
