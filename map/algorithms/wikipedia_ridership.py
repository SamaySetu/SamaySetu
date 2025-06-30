import requests
import re
import time
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import json

def search_wikipedia_for_station(station_name: str, state: str) -> Optional[str]:
    """
    Search for a railway station on Wikipedia and return the page URL if found.
    """
    # Clean station name for search
    clean_name = station_name.replace("jn", "junction").replace("cantt", "cantonment")
    search_terms = [
        f"{clean_name} railway station",
        f"{clean_name} junction",
        f"{clean_name} station {state}",
        f"{clean_name} {state}",
        clean_name
    ]
    
    for search_term in search_terms:
        try:
            # Use Wikipedia's OpenSearch API
            search_url = "https://en.wikipedia.org/w/api.php"
            params = {
                'action': 'opensearch',
                'search': search_term,
                'limit': 5,
                'namespace': 0,
                'format': 'json'
            }
            
            response = requests.get(search_url, params=params, timeout=10)
            if response.status_code == 200:
                results = response.json()
                titles = results[1] if len(results) > 1 else []
                urls = results[3] if len(results) > 3 else []
                
                # Look for railway station pages
                for i, title in enumerate(titles):
                    if any(keyword in title.lower() for keyword in ['railway station', 'junction', 'terminal']):
                        if i < len(urls):
                            return urls[i]
            
            time.sleep(0.5)  # Be nice to Wikipedia
        except Exception as e:
            print(f"Search error for {station_name}: {e}")
            continue
    
    return None

def extract_ridership_from_wikipedia(url: str, station_name: str) -> Optional[Dict]:
    """
    Extract ridership data from a Wikipedia page.
    """
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for ridership information in various formats
        ridership_data = {}
        
        # Common patterns for ridership data
        ridership_patterns = [
            r'(\d{1,3}(?:,\d{3})*)\s*passengers?\s*(?:per\s*)?(?:day|daily)',
            r'daily\s*(?:passenger\s*)?footfall\s*(?:of\s*)?(\d{1,3}(?:,\d{3})*)',
            r'(\d{1,3}(?:,\d{3})*)\s*(?:daily\s*)?passengers?',
            r'footfall\s*(?:of\s*)?(\d{1,3}(?:,\d{3})*)',
            r'handles?\s*(?:about\s*)?(\d{1,3}(?:,\d{3})*)\s*passengers?',
            r'(\d{1,3}(?:,\d{3})*)\s*passengers?\s*(?:use|travel|board)',
        ]
        
        # Search in infobox first
        infobox = soup.find('table', class_='infobox')
        if infobox:
            for row in infobox.find_all('tr'):
                cell_text = row.get_text().lower()
                if any(keyword in cell_text for keyword in ['passengers', 'ridership', 'footfall']):
                    for pattern in ridership_patterns:
                        match = re.search(pattern, cell_text, re.IGNORECASE)
                        if match:
                            ridership_num = int(match.group(1).replace(',', ''))
                            ridership_data['daily_passengers'] = ridership_num
                            ridership_data['source'] = 'infobox'
                            break
                    if ridership_data:
                        break
        
        # If not found in infobox, search in main text
        if not ridership_data:
            text_content = soup.get_text()
            for pattern in ridership_patterns:
                matches = re.finditer(pattern, text_content, re.IGNORECASE)
                for match in matches:
                    ridership_num = int(match.group(1).replace(',', ''))
                    # Sanity check: reasonable daily passenger numbers (100 to 1,000,000)
                    if 100 <= ridership_num <= 1000000:
                        ridership_data['daily_passengers'] = ridership_num
                        ridership_data['source'] = 'main_text'
                        break
                if ridership_data:
                    break
        
        # Look for other useful information
        # Station class/category
        for class_pattern in [r'(\w+)\s*class\s*station', r'category\s*(\w+)\s*station']:
            match = re.search(class_pattern, text_content, re.IGNORECASE)
            if match:
                ridership_data['station_class'] = match.group(1).upper()
                break
        
        # Look for revenue information (additional indicator of importance)
        revenue_patterns = [
            r'revenue\s*(?:of\s*)?₹\s*(\d+(?:\.\d+)?)\s*(?:crore|lakh)',
            r'₹\s*(\d+(?:\.\d+)?)\s*(?:crore|lakh)\s*revenue'
        ]
        
        for pattern in revenue_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                revenue_amount = float(match.group(1))
                unit = 'crore' if 'crore' in match.group(0).lower() else 'lakh'
                ridership_data['annual_revenue'] = {
                    'amount': revenue_amount,
                    'unit': unit
                }
                break
        
        # Add metadata
        if ridership_data:
            ridership_data['wikipedia_url'] = url
            ridership_data['extracted_date'] = time.strftime('%Y-%m-%d')
            ridership_data['station_name'] = station_name
        
        return ridership_data if ridership_data else None
        
    except Exception as e:
        print(f"Error extracting ridership for {station_name}: {e}")
        return None

def get_ridership_for_stations(stations: List[Dict]) -> Dict[str, Dict]:
    """
    Get ridership data for a list of stations from Wikipedia.
    Returns a dictionary mapping station names to ridership data.
    """
    ridership_database = {}
    
    print(f"Searching Wikipedia for ridership data for {len(stations)} stations...")
    
    for i, station in enumerate(stations):
        station_name = station.get('name', 'Unknown')
        state = station.get('state', 'Unknown')
        
        if station_name == 'Unknown':
            continue
        
        print(f"  [{i+1}/{len(stations)}] Searching for {station_name}, {state}")
        
        # Search for Wikipedia page
        wiki_url = search_wikipedia_for_station(station_name, state)
        
        if wiki_url:
            print(f"    Found Wikipedia page: {wiki_url}")
            ridership_data = extract_ridership_from_wikipedia(wiki_url, station_name)
            
            if ridership_data:
                ridership_database[station_name] = ridership_data
                daily_passengers = ridership_data.get('daily_passengers', 0)
                print(f"    ✓ Found ridership: {daily_passengers:,} daily passengers")
            else:
                print(f"    ⚠ No ridership data found on page")
        else:
            print(f"    ✗ No Wikipedia page found")
        
        # Be respectful to Wikipedia's servers
        time.sleep(1)
        
        # Save intermediate results every 10 stations
        if (i + 1) % 10 == 0:
            save_ridership_database(ridership_database)
    
    print(f"\nRidership data collection complete!")
    print(f"Found ridership data for {len(ridership_database)} stations")
    
    return ridership_database

def save_ridership_database(ridership_data: Dict, filename: str = "ridership_database.json"):
    """Save ridership data to a JSON file"""
    import os
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, 'w') as f:
        json.dump(ridership_data, f, indent=2)
    print(f"Ridership database saved to {filename}")

def load_ridership_database(filename: str = "ridership_database.json") -> Dict:
    """Load ridership data from a JSON file"""
    import os
    filepath = os.path.join(os.path.dirname(__file__), filename)
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def calculate_ridership_score_with_wikipedia(station_name: str, ridership_database: Dict) -> int:
    """
    Calculate ridership score using actual Wikipedia data if available,
    otherwise fall back to estimation.
    """
    # Check if we have actual ridership data
    if station_name in ridership_database:
        ridership_data = ridership_database[station_name]
        daily_passengers = ridership_data.get('daily_passengers', 0)
        
        # Convert daily passengers to score (0-100)
        if daily_passengers >= 100000:  # 100k+ passengers (major terminals)
            return 95
        elif daily_passengers >= 50000:  # 50k+ passengers (important junctions)
            return 85
        elif daily_passengers >= 20000:  # 20k+ passengers (major stations)
            return 75
        elif daily_passengers >= 10000:  # 10k+ passengers (significant stations)
            return 65
        elif daily_passengers >= 5000:   # 5k+ passengers (moderate stations)
            return 55
        elif daily_passengers >= 2000:   # 2k+ passengers (regular stations)
            return 45
        elif daily_passengers >= 1000:   # 1k+ passengers (small stations)
            return 35
        elif daily_passengers >= 500:    # 500+ passengers (minor stations)
            return 25
        else:                            # <500 passengers (local stations)
            return 15
    
    # Fall back to estimation if no Wikipedia data
    name_lower = station_name.lower()
    
    if any(keyword in name_lower for keyword in ['central', 'terminal', 'main']):
        return 70  # Estimated high ridership
    elif any(keyword in name_lower for keyword in ['jn', 'junction']):
        return 60  # Estimated medium-high ridership
    elif any(keyword in name_lower for keyword in ['city', 'cantt']):
        return 50  # Estimated medium ridership
    else:
        return 30  # Estimated low ridership

# Pre-defined ridership data for major South Indian stations (from various sources)
KNOWN_RIDERSHIP_DATA = {
    "Chennai Central": {"daily_passengers": 550000, "source": "indian_railways"},
    "Bangalore City": {"daily_passengers": 465000, "source": "indian_railways"},
    "Bangalore Cantonment": {"daily_passengers": 180000, "source": "indian_railways"},
    "KSR Bengaluru": {"daily_passengers": 465000, "source": "indian_railways"},
    "Secunderabad Jn": {"daily_passengers": 300000, "source": "indian_railways"},
    "Hyderabad": {"daily_passengers": 200000, "source": "indian_railways"},
    "Vijayawada Jn": {"daily_passengers": 180000, "source": "indian_railways"},
    "Coimbatore Jn": {"daily_passengers": 120000, "source": "indian_railways"},
    "Ernakulam Jn": {"daily_passengers": 85000, "source": "indian_railways"},
    "Thiruvananthapuram Central": {"daily_passengers": 75000, "source": "indian_railways"},
    "Madurai Jn": {"daily_passengers": 65000, "source": "indian_railways"},
    "Salem Jn": {"daily_passengers": 55000, "source": "indian_railways"},
    "Tirunelveli": {"daily_passengers": 35000, "source": "indian_railways"},
    "Mysore Jn": {"daily_passengers": 45000, "source": "indian_railways"},
    "Tiruchirappalli": {"daily_passengers": 50000, "source": "indian_railways"},
}
