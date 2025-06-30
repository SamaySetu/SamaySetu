import sys
import os

# Add the parent directory to Python path to enable package imports
parent_dir = os.path.dirname(os.path.dirname(__file__))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from algorithms.station_importance import (
        extract_station_data_from_website,
        get_station_data_by_name,
        calculate_station_importance,
        rank_stations_by_importance
    )
except ImportError as e:
    print(f"Error importing station_importance: {e}")
    print(f"Make sure the algorithms directory exists at: {parent_dir}")
    sys.exit(1)

def test_website_data_extraction():
    """Test if the website data extraction works correctly."""
    print("Testing website data extraction...")
    
    data = extract_station_data_from_website()
    if data:
        print(f"✓ Successfully extracted {data['metadata']['total_stations']} stations from website")
        print(f"✓ Index sizes: by_name={len(data['by_name'])}, by_code={len(data['by_code'])}, by_normalized_name={len(data['by_normalized_name'])}")
        return True
    else:
        print("✗ Failed to extract station data from website")
        return False

def test_station_lookup():
    """Test station name lookup functionality."""
    print("\nTesting station lookup...")
    
    # Test some common station names
    test_stations = [
        "NEW DELHI",
        "Chennai Central", 
        "Mumbai CST",
        "Howrah",
        "Bangalore City",
        "Hyderabad",
        "Trivandrum Central"
    ]
    
    found_count = 0
    for station_name in test_stations:
        data = get_station_data_by_name(station_name)
        if data:
            print(f"✓ Found: {station_name} -> {data['station_name']} ({data['code']}) - "
                  f"Footfall: {data['footfall']:,}, Revenue: ₹{data['revenue']:,}, NSG: {data['nsg_class']}")
            found_count += 1
        else:
            print(f"✗ Not found: {station_name}")
    
    print(f"\nFound {found_count}/{len(test_stations)} test stations")
    return found_count > 0

def test_importance_calculation():
    """Test importance calculation for sample stations."""
    print("\nTesting importance calculation...")
    
    # Create mock station data for testing
    sample_stations = [
        {"name": "NEW DELHI", "lat": 28.6435, "lon": 77.2197},
        {"name": "Chennai Central", "lat": 13.0836, "lon": 80.2750},
        {"name": "Mumbai CST", "lat": 18.9398, "lon": 72.8355},
        {"name": "Test Station", "lat": 12.0000, "lon": 77.0000}  # This won't be found in data
    ]
    
    sample_tracks = []  # Empty tracks for testing
    
    for station in sample_stations:
        importance = calculate_station_importance(station, sample_stations, sample_tracks)
        ridership_data = importance.get('ridership_data', {})
        
        print(f"Station: {station['name']}")
        print(f"  Importance Score: {importance['importance_score']:.1f}")
        print(f"  Category: {importance['importance_category']}")
        print(f"  Data Source: {ridership_data.get('data_source', 'unknown')}")
        
        if ridership_data.get('data_source') == 'real_footfall':
            print(f"  Real Data: Footfall={ridership_data.get('footfall', 0):,}, "
                  f"Revenue=₹{ridership_data.get('revenue', 0):,}, NSG={ridership_data.get('nsg_class', 'N/A')}")
        
        print()

def test_full_ranking():
    """Test the full ranking system with a small sample."""
    print("\nTesting full ranking system...")
    
    # Create a small infrastructure dataset for testing
    test_infrastructure = {
        'stations': [
            {"name": "NEW DELHI", "lat": 28.6435, "lon": 77.2197},
            {"name": "Chennai Central", "lat": 13.0836, "lon": 80.2750},
            {"name": "Mumbai CST", "lat": 18.9398, "lon": 72.8355},
            {"name": "Howrah", "lat": 22.5822, "lon": 88.3420},
            {"name": "Test Junction", "lat": 12.0000, "lon": 77.0000}
        ],
        'tracks': []
    }
    
    ranked_infrastructure = rank_stations_by_importance(test_infrastructure)
    
    rankings = ranked_infrastructure.get('station_rankings', {})
    print(f"\nRanking Results:")
    print(f"Total stations processed: {rankings.get('total_stations', 0)}")
    print(f"Real data usage: {rankings.get('data_source_usage', {}).get('real_data_percentage', 0):.1f}%")
    print(f"Dataset size: {rankings.get('dataset_info', {}).get('total_stations_in_dataset', 0):,} total stations")
    
    top_stations = rankings.get('top_10_stations', [])
    print(f"\nTop {len(top_stations)} stations:")
    for i, station in enumerate(top_stations, 1):
        real_data_indicator = "📊" if station.get('has_real_data') else "🔢"
        print(f"  {i}. {station['name']} - Score: {station['score']:.1f} {real_data_indicator}")

def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Updated Station Importance System with Website Data")
    print("=" * 60)
    
    success_count = 0
    total_tests = 4
    
    # Test 1: Website data extraction
    if test_website_data_extraction():
        success_count += 1
    
    # Test 2: Station lookup
    if test_station_lookup():
        success_count += 1
    
    # Test 3: Importance calculation
    try:
        test_importance_calculation()
        success_count += 1
        print("✓ Importance calculation test completed")
    except Exception as e:
        print(f"✗ Importance calculation test failed: {e}")
    
    # Test 4: Full ranking
    try:
        test_full_ranking()
        success_count += 1
        print("✓ Full ranking test completed")
    except Exception as e:
        print(f"✗ Full ranking test failed: {e}")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("🎉 All tests passed! The station importance system is working correctly with website data.")
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
