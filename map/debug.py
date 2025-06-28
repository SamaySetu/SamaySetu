import streamlit as st
import pandas as pd
import json
import os

def main():
    st.title("🚂 SamaySetu Railway Network - Debug")
    
    # Load data
    try:
        data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'railway_data.json')
        with open(data_path, 'r') as f:
            data = json.load(f)
        
        elements = data.get('elements', [])
        st.write(f"Total elements loaded: {len(elements)}")
        
        # Extract stations
        stations = []
        for elem in elements:
            if elem['type'] == 'node' and elem.get('tags', {}).get('railway') == 'station':
                stations.append({
                    'name': elem.get('tags', {}).get('name', 'Unknown'),
                    'latitude': elem['lat'],
                    'longitude': elem['lon']
                })
        
        st.write(f"Stations found: {len(stations)}")
        
        if stations:
            # Create a simple map with first 100 stations
            df = pd.DataFrame(stations[:100])
            st.subheader("Railway Stations (First 100)")
            st.map(df)
            
            # Show sample data
            st.subheader("Sample Station Data")
            st.dataframe(df.head(10))
        else:
            st.error("No stations found in the data")
            
    except Exception as e:
        st.error(f"Error: {e}")
        st.write("Full error details:")
        st.exception(e)

if __name__ == "__main__":
    main()
