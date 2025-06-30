import sys
import os
# Add parent directory to path to import algorithms
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from algorithms.speed_limits import get_elevation_data, calculate_gradient_from_elevation, calculate_banking_requirement, ELEVATION_API_URL

def test_elevation_api():
    """Test the Open-Elevation API integration"""
    print("Testing Open-Elevation API...")
    print("=" * 50)
    
    # Test coordinates in South India (Chennai to Bangalore route sample)
    test_coords = [
        [13.0827, 80.2707],  # Chennai
        [12.9716, 77.5946],  # Bangalore
        [12.3, 78.9],        # Intermediate point
    ]
    
    print(f"Testing with coordinates: {test_coords}")
    print(f"\nUsing: {ELEVATION_API_URL}")
    print("Free, reliable, no API key required")
    print("-" * 50)
    
    try:
        # Test with Open-Elevation API
        print("\nFetching elevation data...")
        elevations = get_elevation_data(test_coords, max_points=3)
        print(f"Elevations: {elevations}")
        
        # Test gradient calculation
        avg_gradient, max_gradient = calculate_gradient_from_elevation(test_coords, elevations)
        print(f"Gradients - Avg: {avg_gradient:.3f}%, Max: {max_gradient:.3f}%")
        
        # Test banking calculation
        banking = calculate_banking_requirement(test_coords, elevations, 100)  # 100 km/h
        print(f"Banking: {banking:.2f} degrees")
        
        print("\nTest successful! System ready for data fetching.")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        print("Check internet connection")
        return False

if __name__ == "__main__":
    success = test_elevation_api()
    
    print("\n" + "=" * 50)
    print("SYSTEM STATUS: Simplified & Ready")
    print("Single reliable API (Open-Elevation)")
    print("No configuration needed")
    print("Data cached to JSON for fast app performance")
    
    exit(0 if success else 1)
