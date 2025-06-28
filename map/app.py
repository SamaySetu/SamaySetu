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

def extract_stations(elements):
    stations = []
    seen = set()
    
    for elem in elements:
        if elem['type'] == 'node' and elem.get('tags', {}).get('railway') == 'station':
            key = (elem['lat'], elem['lon'])
            if key not in seen:
                seen.add(key)
                name = elem.get('tags', {}).get('name', 'Unknown')
                stations.append({
                    'name': name,
                    'lat': elem['lat'],
                    'lon': elem['lon'],
                    'state': get_state_from_coords(elem['lat'], elem['lon'])
                })
    return stations

def extract_tracks(elements):
        tracks = []
        
        # Simple track extraction - convert ways to line segments
        for elem in elements:
            if elem['type'] == 'way' and elem.get('tags', {}).get('railway') == 'rail':
                if len(elem.get('nodes', [])) > 1:
                    tracks.append({
                        'nodes': len(elem['nodes']),
                        'state': 'Unknown'  # Simplified for now
                    })
        
        return tracks

def get_state_from_coords(lat, lon):
    # Simple approximation based on coordinates
    if 8.0 <= lat <= 13.0 and 76.0 <= lon <= 78.0:
        return "Kerala"
    elif 8.0 <= lat <= 17.0 and 77.0 <= lon <= 84.0:
        return "Tamil Nadu"
    elif 11.5 <= lat <= 19.0 and 74.0 <= lon <= 78.5:
        return "Karnataka"
    elif 13.0 <= lat <= 19.5 and 77.0 <= lon <= 84.5:
        return "Andhra Pradesh"
    elif 15.8 <= lat <= 19.9 and 77.3 <= lon <= 81.8:
        return "Telangana"
    elif 11.7 <= lat <= 12.1 and 79.6 <= lon <= 80.0:
        return "Puducherry"
    return "Unknown"

def get_track_count(elements):
    # Count railway tracks
    count = 0
    for elem in elements:
        if elem['type'] == 'way' and elem.get('tags', {}).get('railway') == 'rail':
            count += 1
    return count

def main():
    st.set_page_config(
        page_title="SamaySetu Railway Map",
        page_icon="🚂",
        layout="wide"
    )
    
    st.title("🚂 SamaySetu Railway Network")
    st.markdown("Interactive map of railway stations and tracks across South India")
    
    # Load data
    try:
        data = load_data()
        elements = data.get('elements', [])
        
        stations = extract_stations(elements)
        track_count = get_track_count(elements)
        
        # Sidebar controls
        st.sidebar.header("🎛️ Filters")
        
        available_states = list(set([s['state'] for s in stations if s['state'] != 'Unknown']))
        available_states.sort()
        
        selected_states = st.sidebar.multiselect(
            "Select States",
            available_states,
            default=available_states
        )
        
        # Stats
        if selected_states:
            filtered_stations = [s for s in stations if s['state'] in selected_states]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Stations", len(filtered_stations))
            with col2:
                st.metric("Track Segments", track_count)
            with col3:
                st.metric("States", len(selected_states))
            
            # Map
            if filtered_stations:
                # Limit stations for performance
                max_stations = 500
                display_stations = filtered_stations[:max_stations]
                
                # Create interactive Folium map with modern styling
                m = folium.Map(
                    location=[13.0827, 80.2707], 
                    zoom_start=6,
                    tiles='CartoDB positron'  # Clean, modern basemap
                )
                
                # Add stations as small, clean markers
                for station in display_stations:
                    folium.CircleMarker(
                        location=[station['lat'], station['lon']],
                        radius=4,  # Smaller dots
                        popup=folium.Popup(
                            f"""
                            <div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px;">
                                <b style="color: #2E86AB;">{station['name']}</b><br>
                                <span style="color: #666;">📍 {station['state']}</span><br>
                                <span style="color: #888; font-size: 12px;">{station['lat']:.4f}, {station['lon']:.4f}</span>
                            </div>
                            """, 
                            max_width=280
                        ),
                        tooltip=folium.Tooltip(
                            station['name'], 
                            style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; background-color: rgba(0,0,0,0.8); color: white; border-radius: 6px;"
                        ),
                        color='#E74C3C',
                        fillColor='#E74C3C',
                        fillOpacity=0.9,
                        weight=1
                    ).add_to(m)
                
                st.subheader("🗺️ Railway Network Map")
                if len(filtered_stations) > max_stations:
                    st.info(f"Showing first {max_stations} of {len(filtered_stations)} stations for performance")
                
                # Display the map
                map_data = st_folium(m, width=1200, height=600)
                
                st.caption("💡 Click markers for details • Hover for station names")
                
                # Search dropdown as backup
                st.subheader("🔍 Station Search")
                station_names = [s['name'] for s in filtered_stations]
                selected_station = st.selectbox("Search for a station:", station_names, index=0)
                
                if selected_station:
                    station_info = next(s for s in filtered_stations if s['name'] == selected_station)
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**Name:** {station_info['name']}")
                    with col2:
                        st.write(f"**State:** {station_info['state']}")
                    with col3:
                        st.write(f"**Coordinates:** {station_info['lat']:.4f}, {station_info['lon']:.4f}")
            else:
                st.info("No stations found for selected states.")
            
            # Station list
            if st.checkbox("Show Station List"):
                df = pd.DataFrame(filtered_stations)
                st.dataframe(df, use_container_width=True)
        else:
            st.warning("Please select at least one state to view the map.")
            
    except FileNotFoundError:
        st.error("Railway data not found. Please run the data fetch script first.")
    except Exception as e:
        st.error(f"Error loading data: {e}")

if __name__ == "__main__":
    main()
