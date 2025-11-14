#!/usr/bin/env python3
"""Quick test to verify curl_cffi bypasses PerimeterX"""

import time

from curl_cffi import requests

print("Testing curl_cffi bypass...")
print("=" * 60)

# Create session
session = requests.Session()

# Test 1: Visit homepage
print("\n1. Testing homepage access...")
try:
    response = session.get(
        "https://www.flyfrontier.com/", impersonate="chrome120", timeout=15
    )
    print(f"   Status: {response.status_code}")
    print(f"   Response length: {len(response.text)} bytes")
    if response.status_code == 200:
        print("   ✅ Homepage SUCCESS")
    else:
        print(f"   ❌ Failed with status {response.status_code}")
except Exception as e:
    print(f"   ❌ Error: {e}")

time.sleep(3)

# Test 2: Try booking API endpoint
print("\n2. Testing booking API endpoint...")
test_url = "https://booking.flyfrontier.com/Flight/InternalSelect?o1=SFO&d1=DEN&dd1=Dec%2024,%202025&ADT=1&mon=true&promo="

try:
    response = session.get(test_url, impersonate="chrome120", timeout=15)
    print(f"   Status: {response.status_code}")
    print(f"   Response length: {len(response.text)} bytes")

    # Check for PerimeterX block
    if "px-captcha" in response.text:
        print("   ⚠️  PerimeterX CAPTCHA detected")
    elif response.status_code == 403:
        print("   ❌ 403 Forbidden - Still blocked")
    elif response.status_code == 200:
        # Check if we got actual data
        if "journeys" in response.text or "flights" in response.text:
            print("   ✅ API ACCESS SUCCESS - Got flight data!")
        else:
            print("   ⚠️  200 OK but no flight data in response")
    else:
        print(f"   ⚠️  Unexpected status: {response.status_code}")

except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 60)
print("Test complete!")
print("\nIf you see '✅ API ACCESS SUCCESS', the bypass is working!")
print("You can now run: python3 gowild_fast_bypass.py")
