#!/bin/bash

# Run the GoWild scraper for SFO flights tomorrow
# This will open a Chrome browser window

cd /Users/alimoe/Github/Frontier-GoWild-Search

echo "=========================================="
echo "Frontier GoWild Flight Scraper"
echo "=========================================="
echo ""
echo "Origin: SFO (San Francisco)"
echo "Date: Tomorrow"
echo ""
echo "IMPORTANT:"
echo "1. A Chrome browser window will open"
echo "2. If you see a CAPTCHA, solve it manually"
echo "3. The script will continue automatically"
echo "4. DO NOT close the browser window"
echo ""
echo "Press ENTER to start..."
read

# Run the script with automatic input
printf "SFO\n2\n" | /usr/bin/python3 gowild_scraper.py

echo ""
echo "Script completed!"
