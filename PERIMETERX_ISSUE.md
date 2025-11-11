# 🚨 PerimeterX Bot Detection Issue

## Problem Discovered

Frontier Airlines uses **PerimeterX (HUMAN Security)** bot detection that blocks automated requests immediately with HTTP 403.

Response shows:
```json
{"appId": "PXVb73hTEg",
 "blockScript": "//captcha.perimeterx.net/PXVb73hTEg/captcha.js"
 ...
}
```

This means:
- ❌ Simple HTTP requests are blocked instantly
- ❌ Headers/User-Agent spoofing doesn't work
- ❌ Delays don't help
- ✅ Only real browsers with JavaScript can access the API

## Why This is Happening

PerimeterX detects bots through:
1. **TLS Fingerprinting** - Python requests library has different TLS signature than browsers
2. **JavaScript Challenges** - Requires executing JS code
3. **Browser Fingerprinting** - Checks for real browser environment
4. **Behavioral Analysis** - Mouse movements, timing patterns

## Solutions (Ranked by Feasibility)

### ✅ Option 1: Manual Search (Most Practical)
**Use Frontier's website manually with this organized approach:**

1. Open https://www.flyfrontier.com/travel/my-trips/go-wild
2. Log in with your GoWild pass
3. Search each route systematically
4. Use the tracking spreadsheet below

**Time estimate:** 30-45 minutes for 24 destinations

### ⚙️ Option 2: Browser Automation (Selenium/Playwright)
**Pros:**
- Can execute JavaScript
- Acts like real browser
- Can handle CAPTCHA challenges

**Cons:**
- Requires Selenium/Playwright installation
- Still slower (15-20s per request minimum)
- May still trigger CAPTCHAs but can solve them
- More complex code

**Implementation complexity:** Medium-High

### 💰 Option 3: Residential Proxies
**Pros:**
- Can bypass some bot detection
- Distributed requests

**Cons:**
- Expensive ($50-200/month)
- Still might not work with PerimeterX
- Requires subscription

**Not recommended for this use case**

### 🕐 Option 4: Try Different Times
**Sometimes helps:**
- Very late night (2-4 AM local time)
- Early morning (5-7 AM)
- Mid-week vs weekend

**Success rate:** Low (PerimeterX is always active)

## Recommended Approach: Organized Manual Search

### Manual Search Tracker Spreadsheet

Create a spreadsheet with these columns:

| Destination | Code | Out 12/11 | Out 12/12 | Ret 12/18 | Ret 12/19 | Ret 12/24 | Best Total |
|------------|------|-----------|-----------|-----------|-----------|-----------|------------|
| Denver | DEN | $60 | $65 | $70 | $68 | N/A | $128 |
| Las Vegas | LAS | $55 | $58 | $62 | $60 | $75 | $115 |
| ...

### Search Order (24 Popular Destinations)

**California (Close, Quick to check):**
1. LAX - Los Angeles
2. SAN - San Diego
3. ONT - Ontario
4. SNA - Orange County

**Major Hubs (Usually good deals):**
5. DEN - Denver
6. LAS - Las Vegas
7. PHX - Phoenix
8. ATL - Atlanta

**Southwest:**
9. SLC - Salt Lake City
10. AUS - Austin
11. DAL - Dallas

**Florida (Popular winter destinations):**
12. MIA - Miami
13. FLL - Fort Lauderdale
14. MCO - Orlando
15. TPA - Tampa

**Mexico/Caribbean (Vacation spots):**
16. CUN - Cancun
17. SJD - Los Cabos
18. PVR - Puerto Vallarta
19. PUJ - Punta Cana

**Other:**
20. SEA - Seattle
21. PDX - Portland
22. ORD - Chicago
23. JFK - New York
24. BOS - Boston

### Manual Search Process

For each destination:
1. Enter: SFO → [DESTINATION] → Dec 11 OR Dec 12
2. Note lowest GoWild price
3. Then search return: [DESTINATION] → SFO → Dec 18, 19, OR 24
4. Note lowest GoWild price
5. Calculate total
6. Move to next destination

**Time per destination:** ~2 minutes
**Total time for 24:** ~45 minutes

## Future Options (If Needed Regularly)

### Selenium Implementation
If you need to do this regularly, I can create a Selenium-based scraper that:
- Opens real Chrome browser
- Handles CAPTCHA (with manual solving)
- Automates the search process
- Takes longer but works

**Requirements:**
```bash
pip install selenium webdriver-manager
```

**Pros:**
- Works with PerimeterX
- Can handle CAPTCHAs
- Fully automated (mostly)

**Cons:**
- Slower (20-30s per route)
- Requires browser window open
- May still need manual CAPTCHA solving

### Would you like me to create a Selenium version?

## Bottom Line

**For one-time search:** Manual search (45 min) is fastest
**For regular searches:** Selenium automation worth the setup time

Given that this appears to be a one-time search for your December trip, the manual approach with the organized spreadsheet tracker is your best bet.

---

**Current Status:**
- ❌ requests-based scraper: BLOCKED by PerimeterX
- ✅ Manual search: Ready to go
- ⚙️ Selenium option: Available if needed
