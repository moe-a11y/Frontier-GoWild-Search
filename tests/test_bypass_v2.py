#!/usr/bin/env python3
"""
Advanced bypass test - Using proper page flow instead of direct API access
"""

import random
import time

from curl_cffi import requests


def test_proper_flow():
    """Test accessing booking through proper page flow like a real user"""
    print("=" * 60)
    print("Advanced PerimeterX Bypass Test - Proper Flow")
    print("=" * 60)

    session = requests.Session()

    # Step 1: Visit homepage
    print("\n1. Visiting homepage...")
    try:
        resp = session.get(
            "https://www.flyfrontier.com/", impersonate="chrome120", timeout=20
        )
        print(f"   Status: {resp.status_code}")
        print(f"   Cookies: {len(session.cookies)}")
        time.sleep(random.uniform(2, 4))
    except Exception as e:
        print(f"   Error: {e}")
        return

    # Step 2: Visit the booking page (not API)
    print("\n2. Visiting booking page...")
    try:
        resp = session.get(
            "https://booking.flyfrontier.com/", impersonate="chrome120", timeout=20
        )
        print(f"   Status: {resp.status_code}")
        print(f"   Cookies: {len(session.cookies)}")

        if resp.status_code == 200:
            print("   ✅ Booking page accessible!")
        time.sleep(random.uniform(2, 4))
    except Exception as e:
        print(f"   Error: {e}")
        return

    # Step 3: Try flight select page (the actual user-facing search page)
    print("\n3. Accessing flight search page...")
    try:
        # Use the user-facing flight select page, not the internal API
        url = "https://booking.flyfrontier.com/Flight/Select"
        params = {
            "o1": "SFO",
            "d1": "DEN",
            "dd1": "12/24/2025",
            "ADT": "1",
            "mon": "true",
        }

        resp = session.get(
            url,
            params=params,
            impersonate="chrome120",
            timeout=20,
            allow_redirects=True,
        )

        print(f"   Status: {resp.status_code}")
        print(f"   Final URL: {resp.url}")
        print(f"   Response length: {len(resp.text)} bytes")

        # Check what we got
        if "px-captcha" in resp.text:
            print("   ⚠️  PerimeterX CAPTCHA detected")
        elif resp.status_code == 403:
            print("   ❌ 403 Forbidden")
        elif resp.status_code == 200:
            if "flight" in resp.text.lower() or "fare" in resp.text.lower():
                print("   ✅ GOT FLIGHT PAGE!")

                # Check for GoWild
                if "gowild" in resp.text.lower() or "go wild" in resp.text.lower():
                    print("   ✅✅ GoWild data present!")
                else:
                    print("   ⚠️  Page loaded but no GoWild mention")
            else:
                print("   ⚠️  200 OK but unexpected content")
        else:
            print(f"   ⚠️  Unexpected status: {resp.status_code}")

        # Save response for inspection
        with open("test_response.html", "w") as f:
            f.write(resp.text)
        print("   📄 Response saved to test_response.html")

    except Exception as e:
        print(f"   Error: {e}")
        return

    # Step 4: Try the InternalSelect API with all cookies from above
    print("\n4. Now trying InternalSelect API with warmed session...")
    try:
        api_url = "https://booking.flyfrontier.com/Flight/InternalSelect?o1=SFO&d1=DEN&dd1=Dec%2024,%202025&ADT=1&mon=true&promo="

        resp = session.get(api_url, impersonate="chrome120", timeout=20)

        print(f"   Status: {resp.status_code}")

        if "px-captcha" in resp.text:
            print("   ❌ Still blocked by PerimeterX")
        elif resp.status_code == 200:
            if "journeys" in resp.text or "flights" in resp.text:
                print("   ✅✅✅ API ACCESS SUCCESS!")
            else:
                print("   ⚠️  200 but no flight data")
        else:
            print(f"   Status: {resp.status_code}")

    except Exception as e:
        print(f"   Error: {e}")


if __name__ == "__main__":
    test_proper_flow()
