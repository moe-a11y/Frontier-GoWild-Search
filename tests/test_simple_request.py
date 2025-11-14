#!/usr/bin/env python3
import html
import json

import requests
from bs4 import BeautifulSoup

url = "https://booking.flyfrontier.com/Flight/InternalSelect?o1=SFO&d1=LAS&dd1=Nov%2011,%202025&ADT=1&mon=true&promo="

print("Testing SFO to LAS for Nov 11, 2025...")
response = requests.get(url)
print(f"Status: {response.status_code}")
print(f"Length: {len(response.text)} bytes")

# Check for CAPTCHA
if "px-captcha" in response.text:
    print("❌ CAPTCHA detected")
else:
    print("✅ No CAPTCHA!")

# Try to extract flight data
soup = BeautifulSoup(response.text, "html.parser")
scripts = soup.find("script", type="text/javascript")
if scripts:
    print("✅ Found JavaScript data!")
    decoded_data = html.unescape(scripts.text)
    try:
        decoded_data = decoded_data[
            decoded_data.index("{") : decoded_data.index(";") - 1
        ]
        data = json.loads(decoded_data)
        if "journeys" in data:
            flights = data.get("journeys", [{}])[0].get("flights", [])
            print(f"✅ Found {len(flights)} flights!")
            # Count GoWild flights
            gowild = [f for f in flights if f.get("isGoWildFareEnabled")]
            print(f"🎯 {len(gowild)} GoWild flights available from SFO to LAS!")

            # Show details of first GoWild flight
            if gowild:
                first = gowild[0]
                print(f"\nFirst GoWild flight details:")
                print(f"  Price: ${first.get('goWildFare')}")
                print(f"  Duration: {first.get('duration')}")
                print(f"  Stops: {first.get('stopsText')}")
        else:
            print("⚠️ No journey data found")
    except Exception as e:
        print(f"Error parsing: {e}")
else:
    print("❌ No script tag found")
