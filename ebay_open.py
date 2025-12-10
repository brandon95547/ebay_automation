from pathlib import Path
import os

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Load environment variables from .env file in this directory
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# Read URLs from environment (required)
EBAY_SELLING_URL = os.getenv("EBAY_SELLING_URL")
POSH_CLOSET_URL = os.getenv("POSH_CLOSET_URL")

if not EBAY_SELLING_URL or not POSH_CLOSET_URL:
    raise RuntimeError(
        "EBAY_SELLING_URL and POSH_CLOSET_URL must be set in a .env file"
    )

# Persistent browser profile for login reuse
PROFILE_DIR = BASE_DIR / ".playwright-profile"

# Downloads folder (future use)
DOWNLOAD_DIR = BASE_DIR / "downloads"


def main():
    PROFILE_DIR.mkdir(exist_ok=True)
    DOWNLOAD_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            accept_downloads=True,
            downloads_path=str(DOWNLOAD_DIR),
            args=["--start-maximized"],
        )

        # Use existing page or new one
        page = browser.pages[0] if browser.pages else browser.new_page()

        # STEP 1: Go to eBay Active Listings
        print(f"Opening eBay Active Listings page: {EBAY_SELLING_URL}")
        page.goto(EBAY_SELLING_URL, wait_until="domcontentloaded")

        try:
            page.wait_for_selector("a[href*='/itm/']", timeout=15000)
        except PlaywrightTimeoutError:
            print("\nNo listing links found on the eBay Active Listings page.")
            print("Make sure you're logged in and have active listings.")
            input("\nPress ENTER to close browser...")
            browser.close()
            return

        # Click first listing
        first_listing = page.locator("a[href*='/itm/']").first
        first_listing.click()
        page.wait_for_load_state("domcontentloaded")

        # Get title of eBay listing
        ebay_title = page.locator("h1.x-item-title__mainTitle span.ux-textspans--BOLD").first.inner_text().strip()
        print(f"\nEBAY LISTING TITLE:\n{ebay_title}")

        # STEP 2: Open Poshmark closet
        print(f"\nOpening Poshmark closet: {POSH_CLOSET_URL}")
        posh_page = browser.new_page()
        posh_page.goto(POSH_CLOSET_URL, wait_until="domcontentloaded")

        # STEP 3: Scroll down until no more items load
        print("\nScrolling Poshmark closet to load all items...")
        previous_height = 0

        while True:
            posh_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            posh_page.wait_for_timeout(1500)

            current_height = posh_page.evaluate("document.body.scrollHeight")

            if current_height == previous_height:
                print("Reached bottom of closet — all items should be loaded.")
                break

            previous_height = current_height

        # STEP 4: Collect all card titles (a.tile__title)
        title_loc = posh_page.locator("a.tile__title")
        titles = [t.strip() for t in title_loc.all_inner_texts()]
        total_listings = len(titles)

        print(f"\nTotal listing cards detected: {total_listings}")

        # STEP 5: Check if eBay title is already present in Poshmark titles
        ebay_norm = ebay_title.lower().strip()

        matches = []
        for t in titles:
            t_norm = t.lower().strip()
            # LOG what we're comparing
            print("=== TITLE CHECK ===")
            print(f"Ebay Title:     {ebay_title}")
            print(f"Checking Title: {t}")
            print(f"ebay_norm:      {ebay_norm}")
            print(f"t_norm:         {t_norm}")
            print("-------------------")
            if ebay_norm in t_norm or t_norm in ebay_norm:
                matches.append(t)

        if matches:
            print("\nRESULT: Listing FOUND in Poshmark closet.")
            print("Matching titles:")
            for m in matches:
                print(f"  - {m}")
        else:
            print("\nRESULT: Listing NOT found in Poshmark closet.")

        print("\nReview the browser if you want. Press ENTER here to close...")
        input()

        browser.close()


if __name__ == "__main__":
    main()
