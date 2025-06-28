import requests
import json
import time

def get_railway_data():
    query = """
    [out:json][timeout:180];

    area["name"="Tamil Nadu"]->.tn;
    area["name"="Kerala"]->.kl;
    area["name"="Karnataka"]->.ka;
    area["name"="Andhra Pradesh"]->.ap;
    area["name"="Telangana"]->.tg;
    area["name"="Puducherry"]->.py;

    (
      way["railway"="rail"](area.tn);
      way["railway"="rail"](area.kl);
      way["railway"="rail"](area.ka);
      way["railway"="rail"](area.ap);
      way["railway"="rail"](area.tg);
      way["railway"="rail"](area.py);

      node["railway"="station"](area.tn);
      node["railway"="station"](area.kl);
      node["railway"="station"](area.ka);
      node["railway"="station"](area.ap);
      node["railway"="station"](area.tg);
      node["railway"="station"](area.py);

      way["railway"="station"](area.tn);
      way["railway"="station"](area.kl);
      way["railway"="station"](area.ka);
      way["railway"="station"](area.ap);
      way["railway"="station"](area.tg);
      way["railway"="station"](area.py);
    );

    out body;
    >;
    out skel qt;
    """
    
    url = "https://overpass-api.de/api/interpreter"
    
    try:
        response = requests.post(url, data=query, timeout=200)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("Query timed out")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

def save_data(data, filename="railway_data.json"):
    import os
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    print("Fetching railway data...")
    data = get_railway_data()
    
    if data:
        save_data(data)
        print(f"Data saved with {len(data.get('elements', []))} elements")
    else:
        print("Failed to fetch data")

if __name__ == "__main__":
    main()
