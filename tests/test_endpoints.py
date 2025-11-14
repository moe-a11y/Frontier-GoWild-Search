#!/usr/bin/env python3
"""
Test different Frontier API endpoints to find ones without CAPTCHA
"""

import json

import requests

# Try different potential API endpoints
endpoints = [
    # Booking API (current target - has CAPTCHA)
    "https://booking.flyfrontier.com/Flight/InternalSelect?o1=SFO&d1=LAS&dd1=Nov%2011,%202025&ADT=1&mon=true&promo=",
    # Try mobile API
    "https://mobile.flyfrontier.com/api/flights",
    # Try different booking endpoints
    "https://www.flyfrontier.com/api/booking/search",
    "https://api.flyfrontier.com/booking/search",
    # Try the main website's search
    "https://www.flyfrontier.com/travel/flight-search/",
    # Try low fare calendar
    "https://www.flyfrontier.com/travel/low-fare-calendar/",
]

print("Testing Frontier Airlines endpoints for CAPTCHA...\n")

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"
    }
)

for endpoint in endpoints:
    print(f"Testing: {endpoint}")
    try:
        response = session.get(endpoint, timeout=10)
        print(f"  Status: {response.status_code}")

        # Check for CAPTCHA
        has_captcha = (
            "px-captcha" in response.text or "perimeterx" in response.text.lower()
        )
        print(f"  CAPTCHA: {'YES ❌' if has_captcha else 'NO ✓'}")
        print(f"  Length: {len(response.text)} bytes")

        if not has_captcha and response.status_code == 200:
            print(f"  ✅ POTENTIAL WINNER! No CAPTCHA detected")
            print(f"  Content preview: {response.text[:200]}")

    except Exception as e:
        print(f"  Error: {e}")

    print()

print("\nDone!")
