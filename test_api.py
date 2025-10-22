#!/usr/bin/env python3
"""
Test script for Radio Browser API integration
"""

import sys

print("Testing Radio Browser API client...")

try:
    from radio_api import RadioBrowserAPI
    print("✓ RadioBrowserAPI imported successfully")
except ImportError as e:
    print(f"✗ Failed to import RadioBrowserAPI: {e}")
    sys.exit(1)

# Test API initialization
try:
    api = RadioBrowserAPI()
    print("✓ RadioBrowserAPI instance created")
    print(f"  Using base URL: {api.current_url}")
except Exception as e:
    print(f"✗ Failed to create API instance: {e}")
    sys.exit(1)

# Test API methods exist
methods_to_check = [
    'search_stations',
    'get_stations_by_country',
    'get_stations_by_language',
    'get_top_stations',
    'get_countries',
    'get_languages',
    'get_tags',
    'click_station',
    'format_station_for_display',
    'get_station_url',
    'get_station_info'
]

print("\nChecking API methods...")
for method in methods_to_check:
    if hasattr(api, method):
        print(f"✓ Method {method} exists")
    else:
        print(f"✗ Method {method} not found")
        sys.exit(1)

# Test actual API call (optional - requires internet)
print("\nTesting live API call (requires internet)...")
try:
    # Try to get a few top stations
    stations = api.get_top_stations(limit=5)
    if stations:
        print(f"✓ Successfully fetched {len(stations)} stations from API")
        if len(stations) > 0:
            first_station = stations[0]
            print(f"  First station: {first_station.get('name', 'Unknown')}")
            display_name = api.format_station_for_display(first_station)
            print(f"  Formatted: {display_name}")
    else:
        print("⚠ API returned empty list (may be temporary issue)")
except Exception as e:
    print(f"⚠ Live API test failed (may be expected without internet): {e}")

print("\n" + "="*50)
print("API tests completed! ✓")
print("="*50)
