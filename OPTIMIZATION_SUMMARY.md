# Script Optimization Summary

## Changes Made to `/Users/alimoe/Github/Frontier-GoWild-Search/gowild_scraper.py`

### 1. Date Range Feature
- **Added new option 4** in the date selection menu for custom date ranges
- **New function `parse_date()`**: Accepts multiple date formats
  - YYYY-MM-DD (e.g., 2025-12-16)
  - MM/DD/YYYY (e.g., 12/16/2025)
  - MM-DD-YYYY (e.g., 12-16-2025)
  - YYYY/MM/DD (e.g., 2025/12/16)
- **Date validation**: Ensures start date is before or equal to end date
- **Automatic range generation**: Creates a list of all dates between start and end dates

### 2. Specific Airport Selection Feature
- **New function `get_destinations_to_search()`**: Allows filtering destinations
- **Two modes**:
  1. Search all destinations (original behavior)
  2. Specify specific destination airports by comma-separated codes
- **Airport validation**: Warns users of invalid airport codes
- **Sample display**: Shows first 10 available airports to help selection
- **Graceful fallback**: Uses all destinations if no valid codes entered

### 3. Improved User Experience
- **Better formatted menus** with clear numbering and spacing
- **Separator lines** between date searches for better readability
- **Full date display**: Shows day of week and full date (e.g., "Monday, December 25, 2024")
- **Keyboard interrupt handling**: Graceful exit with Ctrl+C
- **Per-date reset**: Clears destination results for each date to show accurate availability

## How to Use

### Testing Example: SFO to Miami, December 16-22, 2025

Run the script:
```bash
/usr/bin/python3 gowild_scraper.py
```

When prompted, enter:
```
Origin IATA airport code: SFO

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

Enter destination airport codes separated by commas (e.g., LAX,JFK,ORD)
Destination codes: MIA
```

### Example: Multiple Destinations, Single Date
```
Origin IATA airport code: LAX
Choose option: 2  (Tomorrow)

Destination Selection:
Choose option (1 or 2): 2
Destination codes: LAS,PHX,SFO,SAN
```

### Example: All Destinations, Date Range
```
Origin IATA airport code: DEN
Choose option: 4  (Date range)
Start date: 12/20/2025
End date: 12/25/2025

Destination Selection:
Choose option (1 or 2): 1  (Search all destinations)
```

## Technical Details

### Date Range Processing
The script generates all dates in the specified range and searches them sequentially:
- Each date opens the same Chrome browser window
- Results are displayed separately for each date
- Available destinations are reset and recalculated for each date

### Airport Code Validation
- Entered codes are converted to uppercase automatically
- Invalid codes trigger warnings but don't stop execution
- If all codes are invalid, the script falls back to searching all destinations

### Browser Behavior
- Opens a single Chrome browser instance using undetected-chromedriver
- Reuses the same browser window for all destination checks
- Implements random delays (3-6 seconds) between requests to avoid rate limiting
- Gracefully handles browser window closures

## Benefits

1. **Flexibility**: Search any date range, not just today/tomorrow
2. **Efficiency**: Filter to specific destinations instead of checking all 114 airports
3. **Better Planning**: See availability across multiple days at once
4. **User-Friendly**: Multiple date format support and clear prompts
5. **Time-Saving**: Focus searches on desired routes (e.g., just Miami from SFO)

## Notes

- Chrome browser will open automatically and navigate through the Frontier booking pages
- Each destination check includes a 3-6 second delay to prevent rate limiting
- Results show all GoWild-eligible flights with price, stops, and timing details
- The script will create/update a `destinations.txt` file with search results
