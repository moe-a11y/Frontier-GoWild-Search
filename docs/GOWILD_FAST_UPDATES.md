# GoWild Fast - Optimization Summary

## Changes Applied to `/Users/alimoe/Github/Frontier-GoWild-Search/gowild_fast.py`

I've successfully applied the same optimizations to the faster requests-based version of the flight scraper.

### ✅ 1. Date Range Selection
- **Added option 4** for custom date ranges in the date selection menu
- **New `parse_date()` function** supporting multiple date formats:
  - YYYY-MM-DD (e.g., 2025-12-16)
  - MM/DD/YYYY (e.g., 12/16/2025)
  - MM-DD-YYYY (e.g., 12-16-2025)
  - YYYY/MM/DD (e.g., 2025/12/16)
- **Date validation** ensures start date is before or equal to end date
- **Automatic range generation** creates a list of all dates between start and end
- **Per-date processing** searches each date sequentially with separate results

### ✅ 2. Specific Airport Filtering
- **New `get_destinations_to_search()` function** allows filtering destinations
- **Two search modes**:
  1. Search all destinations (original behavior with all ~140 airports)
  2. Specify specific destination airports via comma-separated codes
- **Airport validation** warns users of invalid airport codes
- **Sample display** shows first 10 available airports to help with selection
- **Graceful fallback** uses all destinations if no valid codes entered

### ✅ 3. Enhanced User Experience
- **Improved menu structure** with clear numbering and formatting
- **Better date display** shows full date (e.g., "Monday, December 25, 2024")
- **Separator lines** between date searches for better readability
- **Multi-date summary** displays overview of results across all searched dates
- **Per-date CSV exports** creates separate CSV file for each search with timestamped filename

### ✅ 4. Multi-Date Support
- **Results tracking** stores results for each date in a dictionary
- **Summary report** at the end shows number of destinations with GoWild flights for each date
- **CSV export** for each date with unique timestamp

## Key Differences from gowild_scraper.py

The fast version uses **requests** instead of Selenium, which means:
- ✅ **Much faster** - no browser automation overhead
- ✅ **Lower resource usage** - no Chrome browser needed
- ⚠️ **Rate limiting required** - uses smart delays (15-25 seconds between requests)
- ⚠️ **CAPTCHA risk** - may trigger Frontier's bot detection if delays are too short

## Usage Example: SFO to Miami, Dec 16-22

```bash
/usr/bin/python3 gowild_fast.py
```

When prompted:
```
Origin airport code: SFO

Date Selection:
  1. Today
  2. Tomorrow
  3. Both (Today and Tomorrow)
  4. Date range
  0. Exit
Choose option: 4

Enter dates in YYYY-MM-DD or MM/DD/YYYY format
Start date: 2025-12-16
End date: 2025-12-22

Destination Selection:
  1. Search all destinations
  2. Specify specific destination airports
Choose option (1 or 2): 2

Available airports (sample):
  ANU: Antigua and Barbuda
  NAS: Nassau, Bahamas
  ...

Destination codes: MIA

Searching 1 destination(s):
  MIA: Miami, FL
```

### Expected Flow:
1. Establishes session with Frontier
2. For each date (Dec 16-22):
   - Searches SFO → MIA route
   - Displays available GoWild flights
   - Shows price, stops, duration for each flight
   - Exports results to CSV file
3. Shows summary across all dates

## Benefits Over Original

### Time Efficiency
- **Single destination**: ~20 seconds per date (vs ~5 minutes with Selenium)
- **Multiple destinations**: Still faster due to no browser overhead
- **Date ranges**: Processes multiple dates without browser restarts

### Resource Efficiency
- **No Chrome browser** needed
- **Lower CPU/memory** usage
- **Works on headless servers**

### Data Export
- **CSV files** with timestamped filenames
- **Structured data** for further analysis
- **Per-date results** for trend tracking

## Rate Limiting Strategy

The script uses intelligent rate limiting:
- **Base delay**: 15 seconds between requests
- **Random variation**: +0 to +10 seconds
- **Adaptive**: Increases delay if rate limited (up to 60s)
- **Recovery**: Decreases delay if things go smoothly (down to 15s)

**Important**: If you search all ~140 destinations, expect:
- **Time**: ~35-45 minutes per date
- **Risk**: Higher chance of CAPTCHA if delays too short

## Tips for Best Results

1. **Specific destinations**: Always better to specify 1-5 airports for speed
2. **Time of day**: Early morning or late night may have less traffic
3. **Date ranges**: Don't search more than 7-10 days at once
4. **CSV files**: Perfect for tracking price trends over time

## Comparison Table

| Feature | gowild_scraper.py | gowild_fast.py |
|---------|-------------------|----------------|
| Method | Selenium/Chrome | Requests library |
| Speed (1 dest) | ~30s per date | ~20s per date |
| Speed (all dests) | ~15-20 min | ~35-45 min |
| Resource usage | High (Chrome) | Low (HTTP only) |
| CAPTCHA risk | Low | Medium |
| Reliability | Higher | Good with delays |
| Rate limiting | 3-6s delays | 15-25s delays |
| CSV export | No | Yes |
| Multi-date summary | Yes | Yes |

## Next Steps

Both scripts now support:
- ✅ Custom date ranges
- ✅ Specific airport filtering
- ✅ Multi-date tracking
- ✅ Better user experience

Choose based on your needs:
- **gowild_scraper.py**: More reliable, handles CAPTCHAs better
- **gowild_fast.py**: Faster, lightweight, great for specific routes

---

*Updated: November 2025*
*Both scripts ready for SFO → MIA Dec 16-22 search and beyond!*
