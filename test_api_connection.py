#!/usr/bin/env python3
"""
Test script for Radio Browser API - to be run on Windows with internet access
This will verify that the API integration works correctly
"""

import sys

print("="*60)
print("Radio Browser API Connection Test")
print("="*60)

try:
    from radio_api import RadioBrowserAPI
    print("✓ RadioBrowserAPI module imported")
except ImportError as e:
    print(f"✗ Failed to import: {e}")
    print("\nPlease install requirements:")
    print("  pip install requests")
    sys.exit(1)

# Create API instance
try:
    api = RadioBrowserAPI()
    print(f"✓ API client created (using {api.current_url})")
except Exception as e:
    print(f"✗ Failed to create API client: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("Testing API Endpoints")
print("="*60)

# Test 1: Get top voted stations
print("\n1. Getting top 5 voted stations worldwide...")
try:
    stations = api.get_top_stations(limit=5)
    if stations:
        print(f"✓ SUCCESS: Found {len(stations)} top stations")
        for i, station in enumerate(stations[:3], 1):
            name = station.get('name', 'Unknown')
            country = station.get('country', 'Unknown')
            votes = station.get('votes', 0)
            print(f"   {i}. {name} ({country}) - {votes} votes")
    else:
        print("✗ FAILED: No stations returned")
        print("  Possible causes:")
        print("  - No internet connection")
        print("  - Firewall blocking access to api.radio-browser.info")
        print("  - API temporarily unavailable")
except Exception as e:
    print(f"✗ ERROR: {e}")

# Test 2: Search by country (Czech Republic)
print("\n2. Searching for Czech stations (CZ)...")
try:
    stations = api.get_stations_by_country('CZ', limit=5)
    if stations:
        print(f"✓ SUCCESS: Found {len(stations)} Czech stations")
        for i, station in enumerate(stations[:3], 1):
            name = station.get('name', 'Unknown')
            print(f"   {i}. {name}")
    else:
        print("✗ FAILED: No Czech stations returned")
except Exception as e:
    print(f"✗ ERROR: {e}")

# Test 3: Search by name
print("\n3. Searching for BBC stations...")
try:
    stations = api.search_stations(name='BBC', limit=5)
    if stations:
        print(f"✓ SUCCESS: Found {len(stations)} BBC stations")
        for i, station in enumerate(stations[:3], 1):
            name = station.get('name', 'Unknown')
            country = station.get('country', 'Unknown')
            print(f"   {i}. {name} ({country})")
    else:
        print("⚠ No BBC stations found")
except Exception as e:
    print(f"✗ ERROR: {e}")

# Test 4: Search by language
print("\n4. Searching for Czech language stations...")
try:
    stations = api.get_stations_by_language('czech', limit=5)
    if stations:
        print(f"✓ SUCCESS: Found {len(stations)} Czech language stations")
        for i, station in enumerate(stations[:3], 1):
            name = station.get('name', 'Unknown')
            print(f"   {i}. {name}")
    else:
        print("⚠ No Czech language stations found")
except Exception as e:
    print(f"✗ ERROR: {e}")

# Test 5: Get a station's details
print("\n5. Testing station information display...")
try:
    stations = api.get_top_stations(limit=1)
    if stations and len(stations) > 0:
        station = stations[0]
        info = api.get_station_info(station)
        print("✓ SUCCESS: Station info retrieved")
        print("\nSample station details:")
        print(info)
    else:
        print("⚠ No stations available to show info")
except Exception as e:
    print(f"✗ ERROR: {e}")

print("\n" + "="*60)
print("Test Summary")
print("="*60)

print("\nIf you see stations listed above, the API is working correctly!")
print("If not, please check:")
print("  1. Internet connection is active")
print("  2. Firewall allows access to *.api.radio-browser.info")
print("  3. Try running the radio_player.py application")
print("\nPress Enter to exit...")
input()
