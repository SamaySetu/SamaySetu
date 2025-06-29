import requests
import json
import time

def get_railway_data_by_state():
    states = {
        "Tamil Nadu": "tn",
        "Kerala": "kl", 
        "Karnataka": "ka",
        "Andhra Pradesh": "ap",
        "Telangana": "tg",
        "Puducherry": "py"
    }
    
    all_elements = []
    
    for state_name, state_code in states.items():
        print(f"Fetching data for {state_name}...")
        
        query = f"""
        [out:json][timeout:60];
        
        area["name"="{state_name}"]->.{state_code};
        
        (
          way["railway"="rail"](area.{state_code});
          node["railway"="station"](area.{state_code});
          way["railway"="station"](area.{state_code});
          node["railway"="signal"](area.{state_code});
          way["railway"="signal"](area.{state_code});
          node["railway"="milestone"](area.{state_code});
          way["railway"="milestone"](area.{state_code});
          node["milestone"](area.{state_code});
          node["railway:signal"](area.{state_code});
          node["railway"="junction"](area.{state_code});
          way["railway"="junction"](area.{state_code});
          node["railway"~"yard|depot|halt|platform"](area.{state_code});
        );
        
        out body;
        >;
        out skel qt;
        """
        
        url = "https://overpass-api.de/api/interpreter"
        
        try:
            response = requests.post(url, data=query, timeout=120)
            response.raise_for_status()
            data = response.json()
            
            # Add state info to each element
            for elem in data.get('elements', []):
                if 'tags' not in elem:
                    elem['tags'] = {}
                elem['tags']['state'] = state_name
            
            all_elements.extend(data.get('elements', []))
            print(f"  Added {len(data.get('elements', []))} elements from {state_name}")
            
        except requests.exceptions.Timeout:
            print(f"  Query timed out for {state_name}")
        except requests.exceptions.RequestException as e:
            print(f"  Request failed for {state_name}: {e}")
        
        # Small delay between requests
        time.sleep(1)
    
    return {"elements": all_elements}

def save_data(data, filename="railway_data.json"):
    import os
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    print("Fetching railway data by state...")
    data = get_railway_data_by_state()
    
    if data:
        save_data(data)
        print(f"Data saved with {len(data.get('elements', []))} total elements")
    else:
        print("Failed to fetch data")

if __name__ == "__main__":
    main()
