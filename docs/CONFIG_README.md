# Configuration Management

## Centralized Configuration (`config.py`)

All blackout dates and destination information are now centralized in `/Users/alimoe/Github/Frontier-GoWild-Search/config.py`.

### What's Included

1. **GoWild Blackout Dates**
   - `GOWILD_BLACKOUT_DATES_2025`
   - `GOWILD_BLACKOUT_DATES_2026`
   - `GOWILD_BLACKOUT_DATES_2027`
   - `GOWILD_BLACKOUT_DATES` (combined list)

2. **SFO Direct Destinations**
   - `SFO_DIRECT_DESTINATIONS` (dictionary of airport codes and names)

3. **Helper Functions**
   - `is_blackout_date(date_str)` - Check if a date is a blackout date
   - `get_destination_name(code)` - Get destination name from airport code
   - `get_all_destination_codes()` - Get list of all destination codes

### How to Use

All scripts now import from the centralized config:

```python
from config import GOWILD_BLACKOUT_DATES, SFO_DIRECT_DESTINATIONS, is_blackout_date
```

### Updating Blackout Dates

When Frontier announces new blackout dates:

1. Visit: https://www.flyfrontier.com/deals/gowild-pass/
2. Open `/Users/alimoe/Github/Frontier-GoWild-Search/config.py`
3. Add new dates to the appropriate year list (e.g., `GOWILD_BLACKOUT_DATES_2027`)
4. Dates are in `YYYY-MM-DD` format
5. The combined list (`GOWILD_BLACKOUT_DATES`) is automatically updated

### Updating SFO Destinations

When Frontier adds/removes routes from SFO:

1. Verify current routes at: https://www.flyfrontier.com/
2. Open `/Users/alimoe/Github/Frontier-GoWild-Search/config.py`
3. Update the `SFO_DIRECT_DESTINATIONS` dictionary
4. Format: `"CODE": "City Name"`

### Scripts Updated

All scripts now use the centralized config:
- `gowild_fast.py`
- `gowild_fast_bypass.py`
- `gowild_undetected.py`
- `gowild_WORKING.py`
- `roundtrip_search.py`
- `roundtrip_fast.py`

### Benefits

✅ **Single Source of Truth** - Update once, applies everywhere
✅ **Easy Maintenance** - No need to search through multiple files
✅ **Version Control** - Track changes to dates and destinations
✅ **Consistency** - All scripts use the same data
