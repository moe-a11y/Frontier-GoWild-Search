#!/usr/bin/env python3
"""
Ultra-slow test - try ONE request with maximum stealth
"""

import json
import time
from datetime import datetime

import requests


def test_single_request():
    """Test a single request with maximum delays"""

    print("🔬 Ultra-Slow Single Request Test")
    print("=" * 60)
    print()

    # Create session with realistic headers
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.flyfrontier.com/",
            "Origin": "https://www.flyfrontier.com",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }
    )

    # First, visit the main page
    print("Step 1: Visiting Frontier homepage...")
    try:
        resp = session.get("https://www.flyfrontier.com/", timeout=30)
        print(f"   Status: {resp.status_code}")
        time.sleep(10)
    except Exception as e:
        print(f"   Error: {e}")
        return

    # Wait like a human
    print("\nStep 2: Waiting 15 seconds...")
    time.sleep(15)

    # Now try ONE flight search
    origin = "SFO"
    dest = "DEN"
    date = "Dec%2011,%202025"

    url = f"https://booking.flyfrontier.com/Flight/InternalSelect?o1={origin}&d1={dest}&dd1={date}&ADT=1&mon=true&promo="

    print(f"\nStep 3: Searching {origin} → {dest} on Dec 11, 2025")
    print(f"   URL: {url}")
    print(f"   Waiting 5 more seconds before request...")
    time.sleep(5)

    try:
        resp = session.get(url, timeout=30)
        print(f"\n✅ Response received!")
        print(f"   Status Code: {resp.status_code}")
        print(f"   Response Length: {len(resp.text)} bytes")
        print(f"   Content-Type: {resp.headers.get('Content-Type', 'N/A')}")

        # Check for CAPTCHA
        if "captcha" in resp.text.lower() or "challenge" in resp.text.lower():
            print(f"\n❌ CAPTCHA detected in response")
            print(f"\n   First 500 chars of response:")
            print(f"   {resp.text[:500]}")
        else:
            # Try to parse as JSON
            try:
                data = resp.json()
                print(f"\n✅ Valid JSON response received")
                print(f"   Keys: {list(data.keys())}")

                if "journeys" in data:
                    flights = data["journeys"][0].get("flights", [])
                    print(f"\n   Found {len(flights)} flights")

                    gowild = [f for f in flights if f.get("isGoWildFareEnabled")]
                    print(f"   GoWild flights: {len(gowild)}")

                    if gowild:
                        for i, flight in enumerate(gowild[:3], 1):
                            price = flight.get("goWildFare", "N/A")
                            print(f"\n   Flight {i}:")
                            print(f"      Price: ${price}")
                            print(f"      Stops: {flight.get('stops', 'N/A')}")

            except json.JSONDecodeError:
                print(f"\n❌ Response is not valid JSON")
                print(f"\n   First 1000 chars:")
                print(f"   {resp.text[:1000]}")

    except Exception as e:
        print(f"\n❌ Request failed: {e}")


if __name__ == "__main__":
    test_single_request()
