import streamlit as st
import pandas as pd
import json
import os
import folium
from streamlit_folium import st_folium

@st.cache_data
def load_data():
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'railway_data.json')
    with open(data_path, 'r') as f:
        return json.load(f)

def extract_infrastructure(elements):
    """Extract all railway infrastructure types from OSM data"""
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
            state = elem.get('tags', {}).get('state', 'Unknown')  # Use state from JSON, not coordinates
            
            base_data = {
                'name': name,
                'lat': elem['lat'],
                'lon': elem['lon'],
                'state': state
            }
            
            # Categorize by importance and type - combine major stations and junctions
            if railway_type == 'station' or railway_type == 'junction':
                # Check if it's a major station/central/junction by looking for keywords in name
                is_major = any(term in name.lower() for term in ['jn', 'junction', 'central', 'terminal', 'main'])
                
                if is_major:
                    infrastructure['major_stations'].append({**base_data, 'type': 'major'})
                else:
                    infrastructure['stations'].append({**base_data, 'type': 'regular'})
            elif railway_type == 'signal':
                infrastructure['signals'].append(base_data)
            elif railway_type == 'milestone' or 'milestone' in elem.get('tags', {}):
                infrastructure['milestones'].append(base_data)
        
        # Extract tracks - this is the key improvement for the spotty track issue
        elif elem['type'] == 'way' and elem.get('tags', {}).get('railway') == 'rail':
            if len(elem.get('nodes', [])) > 1:
                coords = []
                for node_id in elem['nodes']:
                    if node_id in nodes:
                        node = nodes[node_id]
                        coords.append([node['lat'], node['lon']])
                
                if len(coords) > 1:
                    state = elem.get('tags', {}).get('state', 'Unknown')  # Use state from JSON
                    # Improved track type classification
                    tags = elem.get('tags', {})
                    usage = tags.get('usage', '')
                    service = tags.get('service', '')
                    railway = tags.get('railway', 'rail')
                    electrified = tags.get('electrified', '')
                    frequency = tags.get('frequency', '')
                    
                    # Determine track importance with better logic
                    # Check service first (these are usually sidings, yards, etc.)
                    if service in ['siding', 'yard', 'spur', 'crossover']:
                        track_type = 'service'
                    elif usage in ['industrial', 'military']:
                        track_type = 'service'
                    elif usage in ['branch', 'secondary']:
                        track_type = 'branch'
                    elif usage in ['main', 'trunk']:
                        track_type = 'main'
                    elif electrified or frequency:  # Electrified tracks are usually main lines
                        track_type = 'main'
                    elif usage == '':  # No usage specified, classify based on other hints
                        # If no specific usage, default to branch to avoid everything being main
                        track_type = 'branch'
                    else:
                        track_type = 'other'
                    
                    infrastructure['tracks'].append({
                        'coords': coords,
                        'state': state,
                        'type': track_type,
                        'length': len(coords)  # Add length for sorting
                    })
    
    return infrastructure

def create_enhanced_map(infrastructure, selected_states):
    """Create map with improved track rendering to fix spotty/cutoff issues"""
    # Center on South India
    m = folium.Map(
        location=[13.0827, 80.2707], 
        zoom_start=6,
        tiles='CartoDB positron'
    )
    
    # Filter by selected states
    def filter_by_state(items):
        return [item for item in items if item.get('state') in selected_states]
    
    # IMPROVED TRACK RENDERING - Fix scattered lines issue
    filtered_tracks = filter_by_state(infrastructure['tracks'])
    
    # Performance optimization: Better track selection to maintain connectivity
    MAX_TRACKS = 2000  # Increased to show more complete network
    if len(filtered_tracks) > MAX_TRACKS:
        # Sort tracks by importance and length to get better coverage
        main_tracks = [t for t in filtered_tracks if t.get('type') == 'main']
        branch_tracks = [t for t in filtered_tracks if t.get('type') == 'branch']
        service_tracks = [t for t in filtered_tracks if t.get('type') == 'service']
        other_tracks = [t for t in filtered_tracks if t.get('type') == 'other']
        
        # Sort by track length (number of coordinate points) to prioritize longer segments
        main_tracks.sort(key=lambda x: len(x.get('coords', [])), reverse=True)
        branch_tracks.sort(key=lambda x: len(x.get('coords', [])), reverse=True)
        service_tracks.sort(key=lambda x: len(x.get('coords', [])), reverse=True)
        other_tracks.sort(key=lambda x: len(x.get('coords', [])), reverse=True)
        
        # Take more tracks but prioritize longer, more important ones
        sampled_tracks = main_tracks[:800]  # More main tracks
        sampled_tracks.extend(branch_tracks[:800])  # More branch tracks
        sampled_tracks.extend(service_tracks[:200])  # Some service tracks
        sampled_tracks.extend(other_tracks[:200])  # Some other tracks
        
        filtered_tracks = sampled_tracks[:MAX_TRACKS]
    
    # Add tracks with better rendering - group by type for layered display
    main_tracks = [t for t in filtered_tracks if t.get('type') == 'main']
    branch_tracks = [t for t in filtered_tracks if t.get('type') == 'branch']
    service_tracks = [t for t in filtered_tracks if t.get('type') == 'service']
    other_tracks = [t for t in filtered_tracks if t.get('type') == 'other']
    
    # Add main tracks first (bottom layer)
    for track in main_tracks:
        folium.PolyLine(
            locations=track['coords'],
            color='#2E8B57',
            weight=4,
            opacity=0.8
        ).add_to(m)
    
    # Add branch tracks
    for track in branch_tracks:
        folium.PolyLine(
            locations=track['coords'],
            color='#4A7C59',
            weight=3,
            opacity=0.7
        ).add_to(m)
    
    # Add service tracks (sidings, yards)
    for track in service_tracks:
        folium.PolyLine(
            locations=track['coords'],
            color='#8B4513',
            weight=2,
            opacity=0.6
        ).add_to(m)
    
    # Add other tracks
    for track in other_tracks:
        folium.PolyLine(
            locations=track['coords'],
            color='#6B8E23',
            weight=2,
            opacity=0.5
        ).add_to(m)
    
    # Add infrastructure points on top of tracks
    # Add milestones (smallest)
    filtered_milestones = filter_by_state(infrastructure['milestones'])
    for milestone in filtered_milestones:
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
    
    # Add signals
    filtered_signals = filter_by_state(infrastructure['signals'])
    for signal in filtered_signals:
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
    
    # Add regular stations (limit for performance)
    filtered_stations = filter_by_state(infrastructure['stations'])
    for station in filtered_stations[:300]:  # Limit for faster loading
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
    """Add a comprehensive legend showing all track types and infrastructure"""
    legend_html = '''
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 240px; height: auto; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; font-family: 'Segoe UI', Arial, sans-serif;
                padding: 10px; border-radius: 10px; box-shadow: 0 0 15px rgba(0,0,0,0.2);">
        <h4 style="margin: 0 0 10px 0; color: #2C3E50;">🗺️ Railway Infrastructure</h4>
        <div style="border-bottom: 1px solid #eee; padding-bottom: 8px; margin-bottom: 8px;">
            <b>Stations</b>
        </div>
        <p style="margin: 3px 0; color: #8E44AD;"><span style="color: #8E44AD; font-size: 18px;">●</span> Major Stations/Junctions</p>
        <p style="margin: 3px 0; color: #3498DB;"><span style="color: #3498DB; font-size: 14px;">●</span> Regular Stations</p>
        <div style="border-bottom: 1px solid #eee; padding-bottom: 8px; margin: 8px 0;">
            <b>Signals & Markers</b>
        </div>
        <p style="margin: 3px 0; color: #F39C12;"><span style="color: #F39C12; font-size: 12px;">●</span> Railway Signals</p>
        <p style="margin: 3px 0; color: #95A5A6;"><span style="color: #95A5A6; font-size: 10px;">●</span> Milestones</p>
        <div style="border-bottom: 1px solid #eee; padding-bottom: 8px; margin: 8px 0;">
            <b>Railway Tracks</b>
        </div>
        <p style="margin: 3px 0; color: #2E8B57;"><span style="font-weight: bold; color: #2E8B57;">━━━</span> Main Lines</p>
        <p style="margin: 3px 0; color: #4A7C59;"><span style="font-weight: bold; color: #4A7C59;">━━</span> Branch Lines</p>
        <p style="margin: 3px 0; color: #8B4513;"><span style="color: #8B4513;">━</span> Service Tracks</p>
        <p style="margin: 3px 0; color: #6B8E23;"><span style="color: #6B8E23;">━</span> Other Tracks</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    return m

def main():
    st.set_page_config(
        page_title="SamaySetu Railway Map",
        page_icon="🚂",
        layout="wide"
    )
    
    st.title("🚂 SamaySetu Railway Network")
    st.markdown("**Interactive visualization of railway infrastructure across South India**")
    
    # Load data
    try:
        data = load_data()
        elements = data.get('elements', [])
        
        # Extract all infrastructure
        infrastructure = extract_infrastructure(elements)
        
        # Sidebar controls
        st.sidebar.header("🎛️ Filters & Controls")
        
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
            
            # Show track breakdown if tracks are displayed
            if show_tracks and len(filtered_infrastructure['tracks']) > 0:
                track_types = {}
                for track in filtered_infrastructure['tracks']:
                    track_type = track.get('type', 'unknown')
                    track_types[track_type] = track_types.get(track_type, 0) + 1
                
                st.sidebar.markdown("### 🛤️ Track Breakdown")
                for track_type, count in sorted(track_types.items()):
                    st.sidebar.text(f"{track_type.title()}: {count}")
                
                if len(filtered_infrastructure['tracks']) > 2000:
                    st.sidebar.warning(f"⚠️ Showing sampled tracks for performance")
                    st.sidebar.text(f"Total tracks: {len(filtered_infrastructure['tracks'])}")
            
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
                
                # Display the map with reduced height for faster loading
                map_data = st_folium(m, width=1200, height=600)
                
                # Map usage guide
                st.caption("💡 Click markers for details • Different colors represent different infrastructure types • Use sidebar filters to toggle visibility")
                # Infrastructure search - minimal spacing
                st.markdown("**🔍 Infrastructure Search**")
                all_infrastructure_items = []
                for infra_type, items in filtered_infrastructure.items():
                    for item in items:
                        if item.get('name', 'Unknown') != 'Unknown':
                            item_copy = item.copy()
                            item_copy['type'] = infra_type
                            all_infrastructure_items.append(item_copy)
                
                if all_infrastructure_items:
                    search_options = [f"{item['name']} ({item['type']}) - {item['state']}" 
                                    for item in all_infrastructure_items]
                    
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
                            for station in major_stations[:15]:  # Show first 15
                                st.write(f"• {station['name']} ({station['state']})")
                            if len(major_stations) > 15:
                                st.write(f"... and {len(major_stations) - 15} more")
                    
                    with col2:
                        st.metric("Regular Stations", len(regular_stations))
                        if regular_stations:
                            st.write("**Regular Stations (sample):**")
                            for station in regular_stations[:15]:  # Show first 15
                                st.write(f"• {station['name']} ({station['state']})")
                            if len(regular_stations) > 15:
                                st.write(f"... and {len(regular_stations) - 15} more")
                
                # Data export option
                if st.checkbox("🗂️ Show Infrastructure Data Tables"):
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
                st.info("No infrastructure found for selected states and filters.")
        else:
            st.warning("Please select at least one state to view the map.")
            
    except FileNotFoundError:
        st.error("Railway data not found. Please run the data fetch script first.")
        st.info("Run: `python data/fetch.py` to download the railway data.")
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.exception(e)  # Show full traceback for debugging

if __name__ == "__main__":
    main()
