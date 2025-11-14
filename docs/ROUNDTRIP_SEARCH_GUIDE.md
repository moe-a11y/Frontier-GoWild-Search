# Round-Trip Flight Search Guide

## 🎯 Goal
Find the best GoWild round-trip deals from SFO departing Dec 11-12, returning Dec 18, 19, or 24.

## ⚠️ Network Issues Encountered
The automated search experienced connectivity issues (timeouts and CAPTCHA rate limiting). This is likely due to:
1. Network connectivity issues
2. Frontier's aggressive rate limiting
3. Time of day (high traffic periods)

## ✅ Scripts Created

### 1. **`/Users/alimoe/Github/Frontier-GoWild-Search/roundtrip_fast.py`** (Recommended)
- Searches 24 popular destinations only
- Faster execution (~20-30 minutes with good connectivity)
- Pre-configured for your request
- Best for quick results

**Popular destinations included:**
- Major hubs: DEN, LAS, PHX, ATL
- California: LAX, SAN, ONT, SNA
- Southwest: SLC, AUS, DAL
- Florida: MIA, FLL, MCO, TPA
- Mexico/Caribbean: CUN, SJD, PVR, PUJ
- Other: SEA, PDX, ORD, JFK, BOS

### 2. **`/Users/alimoe/Github/Frontier-GoWild-Search/roundtrip_search.py`** (Comprehensive)
- Searches ALL 108 destinations
- Takes 1-2 hours to complete
- Finds every possible option
- Best for exhaustive search

## 🚀 How to Run

### Option A: Run When Network Improves (Recommended)
```bash
cd /Users/alimoe/Github/Frontier-GoWild-Search
/usr/bin/python3 roundtrip_fast.py
```

**Best times to run:**
- Late night / early morning (less traffic)
- Off-peak hours
- When you have stable internet connection

### Option B: Run Overnight (Background)
```bash
cd /Users/alimoe/Github/Frontier-GoWild-Search
nohup /usr/bin/python3 roundtrip_fast.py > roundtrip_results.txt 2>&1 &
```

Check results later:
```bash
cat roundtrip_results.txt
```

## 📊 What the Script Does

### Phase 1: Outbound Flights
1. Searches SFO → all destinations on Dec 11, 2025
2. Searches SFO → all destinations on Dec 12, 2025
3. Collects all destinations with GoWild flights

### Phase 2: Return Flights
For each destination found in Phase 1:
1. Searches destination → SFO on Dec 18, 2025
2. Searches destination → SFO on Dec 19, 2025
3. Searches destination → SFO on Dec 24, 2025

### Phase 3: Results
1. Compiles all round-trip combinations
2. Calculates total prices
3. Sorts by best deals
4. Shows top 15 deals
5. Exports everything to CSV

## 📁 Output

### Console Output
- Real-time progress for each route
- Summary of outbound flights found
- Summary of return flights found
- All round-trip combinations grouped by destination
- Top 15 best deals highlighted

### CSV File
Saved as: `roundtrip_sfo_YYYYMMDD_HHMMSS.csv`

Contains:
- Rank (sorted by price)
- Destination code & name
- Outbound & return dates
- Trip duration (days)
- Outbound price
- Return price
- Total price
- Number of flight options

## 🔧 Manual Alternative Approach

If automated search continues to fail, you can search manually using the single-route script:

### Step 1: Search Outbound from SFO
```bash
/usr/bin/python3 gowild_fast.py
# Choose: SFO → Date range → Dec 11-12 → Search all destinations
```

### Step 2: Note destinations with flights
From the output, note which destinations had GoWild flights

### Step 3: Search Returns for Each Destination
For each destination found (e.g., LAS, DEN, etc.):
```bash
/usr/bin/python3 gowild_fast.py
# Choose: LAS → Date range → Dec 18,19,24 → Specific destination → SFO
```

### Step 4: Compile Manually
Create spreadsheet with:
- Destination
- Outbound date + price
- Return date + price
- Total price

## 💡 Tips for Success

### Rate Limiting
- **Delays between requests:** 15-25 seconds (built into script)
- **If CAPTCHA triggered:** Script automatically increases delays
- **If persistent issues:** Try at a different time

### Network Connectivity
- Use wired connection if possible
- Avoid VPN (can trigger rate limits)
- Try during off-peak hours

### Blackout Dates
The script automatically skips these blackout dates:
- Dec 20-23 (Christmas week)
- Dec 26 (day after Christmas)

Note: Dec 24 is NOT a blackout date and will be searched.

## 🏆 Expected Results Format

### Top Deals Example:
```
1. LAS - Las Vegas
   💰 $120.50 total ($60.25 out + $60.25 return)
   📅 2025-12-11 → 2025-12-18 (7 days)
   ✈️  3 outbound, 2 return options

2. DEN - Denver
   💰 $135.80 total ($68.40 out + $67.40 return)
   📅 2025-12-12 → 2025-12-19 (7 days)
   ✈️  2 outbound, 3 return options
```

### Full Results Example:
```
✈️  LAS - Las Vegas
   📅 2025-12-11 → 2025-12-18 (7 days)
      Out: $60.25 | Return: $60.25 | Total: $120.50
      (3 outbound, 2 return flights)
   📅 2025-12-11 → 2025-12-19 (8 days)
      Out: $60.25 | Return: $65.30 | Total: $125.55
      (3 outbound, 1 return flights)
```

## 🔄 Troubleshooting

### "Connection timeout" errors
- Check internet connection
- Try again later (server may be down)
- Use different time of day

### "CAPTCHA triggered" / "Rate limit"
- Normal after several requests
- Script automatically slows down
- If persistent, try tomorrow

### No outbound flights found
- Check if dates are blackout dates
- Verify airport codes are correct
- Try different dates

### Script hangs/freezes
- Press Ctrl+C to stop
- Wait 30 minutes before retrying
- Consider using overnight background mode

## 📝 Next Steps

1. **Wait for better network conditions** (recommended)
2. **Run script overnight** using nohup command
3. **Try manual approach** if automated continues to fail
4. **Check results CSV** for comprehensive data

---

**Scripts Ready:**
- ✅ `/Users/alimoe/Github/Frontier-GoWild-Search/roundtrip_fast.py` (24 destinations, ~20-30 min)
- ✅ `/Users/alimoe/Github/Frontier-GoWild-Search/roundtrip_search.py` (108 destinations, ~1-2 hours)

**Status:** Ready to run when network connectivity improves.
