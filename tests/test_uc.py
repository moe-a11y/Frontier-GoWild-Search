import time

import undetected_chromedriver as uc

if __name__ == "__main__":
    print("Creating driver...")
    driver = uc.Chrome(headless=False)

    print("✓ Browser opened successfully!")

    print("Loading Frontier website...")
    driver.get(
        "https://booking.flyfrontier.com/Flight/InternalSelect?o1=SFO&d1=LAS&dd1=Nov%2010,%202025&ADT=1&mon=true&promo="
    )
    time.sleep(15)

    print(f"Page title: {driver.title}")
    print(f"Page length: {len(driver.page_source)}")

    # Check for CAPTCHA
    if "px-captcha" in driver.page_source or "perimeterx" in driver.page_source.lower():
        print("⚠️  CAPTCHA still present")
    else:
        print("✓ No CAPTCHA - successfully bypassed!")

    with open("test_page2.html", "w") as f:
        f.write(driver.page_source)
    print("Saved page to test_page2.html")

    driver.quit()
    print("Done!")
