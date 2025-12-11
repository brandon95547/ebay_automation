from pathlib import Path
from PIL import Image

import os, re, requests

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Load environment variables from .env file in this directory
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# Read URLs from environment (required)
EBAY_SELLING_URL = os.getenv("EBAY_SELLING_URL")
POSH_CLOSET_URL = os.getenv("POSH_CLOSET_URL")
POSH_CREATE_URL = os.getenv("POSH_CREATE_URL")

if not EBAY_SELLING_URL or not POSH_CLOSET_URL or not POSH_CREATE_URL:
    raise RuntimeError(
        "EBAY_SELLING_URL, POSH_CLOSET_URL, and POSH_CREATE_URL must be set in a .env file"
    )

# Persistent browser profile for login reuse
PROFILE_DIR = BASE_DIR / ".playwright-profile"

# Downloads folder
DOWNLOAD_DIR = BASE_DIR / "downloads"

def make_square_top_crop(image_path: Path):
    """
    Force image to 1:1 ratio by:
    - Centering horizontally
    - Anchoring at the TOP vertically
    - Cropping off the bottom if needed
    """
    try:
        img = Image.open(image_path)
        img = img.convert("RGB")

        width, height = img.size

        # Already square
        if width == height:
            return image_path

        # Square side is the smaller dimension
        side = min(width, height)

        # Center horizontally
        left = (width - side) // 2
        right = left + side

        # Anchor at TOP vertically: upper = 0, lower = side
        upper = 0
        lower = side

        img_cropped = img.crop((left, upper, right, lower))
        img_cropped.save(image_path, "JPEG", quality=95)

        print(f"  ✓ Cropped to 1:1 (top-anchored): {image_path.name}")
        return image_path

    except Exception as e:
        print(f"  ✗ Failed to crop {image_path.name} to 1:1: {e}")
        return image_path

def convert_webp_to_jpg(image_path: Path):
    if image_path.suffix.lower() != ".webp":
        return image_path  # nothing to do

    try:
        img = Image.open(image_path).convert("RGB")
        jpg_path = image_path.with_suffix(".jpg")
        img.save(jpg_path, "JPEG", quality=95)

        image_path.unlink()  # remove original .webp

        print(f"  ✓ Converted {image_path.name} → {jpg_path.name}")
        return jpg_path

    except Exception as e:
        print(f"  ✗ Failed to convert {image_path.name}: {e}")
        return image_path


def sanitize_for_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:80]

def map_ebay_category_to_posh(ebay_category: str, ebay_title: str, ebay_department: str):
    """
    Map eBay Clothing/Shoes/Accessories into a Poshmark
    (main_category, subcategory) pair.

    main_category: "Men" or "Women" (from eBay's Department)
    subcategory:   Posh top-level like "Shoes", "Jeans", "Accessories", "Other", etc.
    """

    cat = (ebay_category or "").lower()
    title = (ebay_title or "").lower()
    text = cat + " " + title

    # --- Main category from Department -----------------------------------
    dept = (ebay_department or "").strip()

    if dept in ("Men", "Women"):
        main_cat = dept
    elif dept.startswith("Unisex"):
        # Choose your default bucket for unisex
        main_cat = "Men"
    else:
        # If department is missing or odd, just default to Women
        main_cat = "Women"

    # convenience helper
    def has(*words):
        return any(w in text for w in words)

    # ----------------------------------------------------------------------
    # SHOES (Men's Shoes / Women's Shoes → "Shoes")
    # ----------------------------------------------------------------------
    if has("athletic shoes", "running shoes", "sneakers", "trainers",
           "boots", "ankle boots", "cowboy boots", "work boots",
           "sandals", "flip flops", "flip-flops",
           "heels", "pumps", "platforms", "wedges",
           "flats", "loafers", "oxfords", "mules", "clogs",
           "slippers", "house shoes",
           "casual shoes", "dress shoes", "comfort shoes"):
        return (main_cat, "Shoes")

    # ----------------------------------------------------------------------
    # JEANS / PANTS / SHORTS / SKIRTS
    # ----------------------------------------------------------------------
    if has("jeans", "denim"):
        return (main_cat, "Jeans")

    if has("leggings", "yoga pants"):
        # women has "Pants & Jumpsuits", men has "Pants"
        return (main_cat, "Pants & Jumpsuits" if main_cat == "Women" else "Pants")

    if has("pants", "trousers", "chinos", "slacks", "cargo pants", "capris"):
        return (main_cat, "Pants & Jumpsuits" if main_cat == "Women" else "Pants")

    if has("shorts", "boardshorts", "gym shorts", "bike shorts"):
        return (main_cat, "Shorts")

    if has("skirt", "skirts", "skort"):
        return (main_cat, "Skirts")

    # ----------------------------------------------------------------------
    # TOPS / SHIRTS / SWEATERS / JACKETS & COATS
    # ----------------------------------------------------------------------
    # Tops & Shirts
    if has("t-shirt", "tee", "graphic tee", "tank top", "crop top", "tube top"):
        # Women has "Tops", Men has "Shirts"
        return (main_cat, "Tops" if main_cat == "Women" else "Shirts")

    if has("shirt", "button-front", "button-down", "polo", "henley", "dress shirt", "flannel"):
        return (main_cat, "Shirts")

    if has("blouse"):
        return (main_cat, "Tops")

    # Sweaters / Hoodies
    if has("sweater", "cardigan", "pullover", "jumper",
           "hoodie", "hooded sweatshirt", "sweatshirt", "crewneck"):
        return (main_cat, "Sweaters")

    # Jackets & Coats
    if has("coat", "jacket", "parka", "puffer", "anorak",
           "trench", "overcoat", "blazer", "vest", "windbreaker", "fleece"):
        return (main_cat, "Jackets & Coats")

    # ----------------------------------------------------------------------
    # DRESSES / JUMPSUITS / OUTFITS (Women)
    # ----------------------------------------------------------------------
    if main_cat == "Women":
        if has("dress", "sundress", "maxi dress", "cocktail dress", "gown"):
            return (main_cat, "Dresses")
        if has("jumpsuit", "romper", "playsuit"):
            return (main_cat, "Pants & Jumpsuits")
        if has("outfit", "set", "two piece set", "2 piece set", "matching set"):
            return (main_cat, "Pants & Jumpsuits")  # or "Tops" – pick your preference

    # ----------------------------------------------------------------------
    # INTIMATES / SLEEP / SWIM / UNDERWEAR & SOCKS
    # ----------------------------------------------------------------------
    if has("bra", "bralette", "lingerie", "panties", "underwear", "boxers", "briefs"):
        return (main_cat, "Intimates & Sleepwear" if main_cat == "Women" else "Underwear & Socks")

    if has("pajamas", "pyjamas", "sleepwear", "nightgown", "nightshirt", "robe"):
        return (main_cat, "Intimates & Sleepwear" if main_cat == "Women" else "Sleepwear & Robes")

    if has("swimwear", "bikini", "one piece", "one-piece", "swimsuit", "trunks", "rashguard"):
        return (main_cat, "Swim")

    if has("socks", "hosiery", "tights", "pantyhose", "stockings"):
        return (main_cat, "Underwear & Socks" if main_cat == "Men" else "Intimates & Sleepwear")

    # ----------------------------------------------------------------------
    # ACCESSORIES / BAGS / JEWELRY / GROOMING
    # ----------------------------------------------------------------------
    if has("handbag", "purse", "tote", "crossbody", "shoulder bag", "backpack", "wallet", "clutch"):
        return (main_cat, "Bags")

    if has("belt", "belt buckle", "hat", "beanie", "cap", "scarf", "wrap",
           "gloves", "mittens", "earmuffs", "visor", "headband", "hair accessory",
           "keychain", "key chain", "tie", "bow tie", "suspenders", "umbrella"):
        return (main_cat, "Accessories")

    if has("necklace", "bracelet", "ring", "earrings", "jewelry", "jewellery", "anklet", "brooch", "pin"):
        return (main_cat, "Jewelry" if main_cat == "Women" else "Accessories")

    if has("makeup", "lipstick", "foundation", "eyeshadow", "mascara", "concealer"):
        return (main_cat, "Makeup")

    if has("skincare", "skin care", "serum", "moisturizer", "cleanser", "lotion"):
        return (main_cat, "Skincare")

    if has("hair care", "shampoo", "conditioner", "hair spray", "styling gel"):
        return (main_cat, "Hair")

    if has("grooming", "razor", "shaving", "beard", "aftershave", "cologne"):
        return (main_cat, "Grooming")

    # ----------------------------------------------------------------------
    # GLOBAL / TRADITIONAL WEAR
    # ----------------------------------------------------------------------
    if has("kimono", "sari", "salwar", "hanbok", "dashiki", "kaftan", "kilt"):
        return (main_cat, "Global & Traditional Wear")

    # ----------------------------------------------------------------------
    # FALLBACK: dump into misc "Other" for that department
    # ----------------------------------------------------------------------
    return (main_cat, "Other")

def fill_posh_fields_from_ebay(
    posh_page,
    ebay_title: str,
    ebay_description: str,
    ebay_size: str,
    ebay_condition: str,
    ebay_price: int | None,
):
    # --- Title ---
    if ebay_title:
        posh_page.fill("input[data-vv-name='title']", ebay_title[:80])

    # --- Description ---
    if ebay_description:
        posh_page.fill(
            "textarea[data-vv-name='description']",
            ebay_description[:1500],
        )

    # --- Size: use Custom field and inject eBay size ---
    if ebay_size:
        # 1) Open the size dropdown
        size_dropdown = posh_page.locator("div.dropdown[selectortestlocator='size']")
        size_dropdown.wait_for(state="visible", timeout=10000)
        size_dropdown.click()

        # 2) Click the "Custom" tab (if it's there)
        try:
            posh_page.locator(
                "a.navigation--horizontal__link span",
                has_text="Custom",
            ).first.click()
        except Exception:
            pass  # already on Custom

        # 3) Wait for custom size input
        posh_page.wait_for_selector("div.listing-editor__custom_sizes", timeout=10000)
        size_input = posh_page.wait_for_selector("#customSizeInput0", timeout=10000)

        # 4) Fill size with subtle suffix so Posh accepts it
        clean_size = f"{ebay_size} – tag"
        size_input.fill(clean_size)

        # 5) Click the Save button (next to the input)
        posh_page.locator(
            "div.listing-editor__custom_sizes button.btn.btn--secondary"
        ).first.click()

        # 6) Click the blue Done button to close the size dialog
        done_button = posh_page.locator(
            "div[selectortestlocator='size'] button.btn.btn--primary[data-et-name='apply']"
        )
        done_button.wait_for(state="visible", timeout=10000)
        done_button.click()
        print("✓ Size set and Done clicked")

        # tiny pause so the dialog can animate closed
        posh_page.wait_for_timeout(300)
    else:
        raise RuntimeError("No eBay size found; cannot create a valid Poshmark listing.")

    code = map_ebay_condition_to_posh_code(ebay_condition)
    if code:
        # Open the condition dropdown (the element itself has data-test="dropdown")
        cond_dropdown = posh_page.locator(
            "div.dropdown.listing-editor__input--half[menuclickdismiss]"
        )
        cond_dropdown.first.wait_for(state="visible", timeout=10000)
        cond_dropdown.first.click()

        # Click the appropriate condition option
        posh_page.click(
            f"div[data-et-name='listing_condition'][data-et-prop-content='{code}']"
        )

    # --- Price ---
    if ebay_price is not None:
        posh_page.fill(
            "input[data-vv-name='listingPrice']",
            str(ebay_price),
        )
        # Click the Done button inside the Add Price modal
        posh_page.click(
            "div[data-test='modal-container'].listing-price-suggestion-modal "
            "div[data-test='modal-footer'] button.btn--primary"
        )
        print("✓ Price set and Done clicked")


def map_ebay_condition_to_posh_code(ebay_condition: str) -> str | None:
    if not ebay_condition:
        return None

    text = ebay_condition.lower()

    # Very rough but practical mappings – expand as needed
    if "new with tags" in text or "new-with-tags" in text:
        return "nwt"   # New With Tags
    if "new without tags" in text or "new without tag" in text or "like new" in text or "excellent" in text:
        return "uln"   # Like New
    if "good" in text or "gently used" in text:
        return "ug"    # Good
    if "fair" in text or "visible wear" in text or "some wear" in text:
        return "uf"    # Fair

    # default: Good
    return "ug"

def set_posh_category(posh_page, main_cat: str, cat_label: str) -> bool:
    """
    Set Poshmark category to:

        <main_cat> > <cat_label>

    Example: "Men" > "Shirts", "Women" > "Jeans".

    Returns True if both clicks succeed, False otherwise.
    """

    if not main_cat or not cat_label:
        print("Missing main_cat or cat_label for Posh category.")
        return False

    print(f"Setting Poshmark category → {main_cat} > {cat_label}")

    # Open the category dropdown
    try:
        posh_page.click("div.listing-editor__category-container [data-test='dropdown']")
    except Exception as e:
        print(f"✗ Could not open category dropdown: {e}")
        return False

    main_key = (main_cat or "").strip().lower()

    # --- 1) Click Men / Women (top-level) ---
    try:
        if main_key == "men":
            posh_page.click("a.dropdown__link.dropdown__menu__item[data-et-name='men']")
        elif main_key == "women":
            posh_page.click("a.dropdown__link.dropdown__menu__item[data-et-name='women']")
        else:
            main_re = re.compile(rf"^\s*{re.escape(main_cat)}\s*$")
            posh_page.locator(
                "a.dropdown__link.dropdown__menu__item p",
                has_text=main_re,
            ).first.click()
    except Exception as e:
        print(f"✗ Failed to click main category {main_cat}: {e}")
        return False

    # Give Posh a moment to update the second list after choosing Men/Women
    posh_page.wait_for_timeout(200)

    # --- 2) Click the main category under that department (Shirts, Jeans, etc.) ---
    try:
        cat_re = re.compile(rf"^\s*{re.escape(cat_label)}\s*$")
        posh_page.locator(
            "li.dropdown__link.dropdown__menu__item div",
            has_text=cat_re,
        ).first.click()
    except Exception as e:
        print(f"✗ Could not click category {cat_label}: {e}")
        return False

    # (Optional) Close the dropdown so it’s not hovering
    try:
        posh_page.keyboard.press("Escape")
    except Exception:
        pass

    return True

def get_ebay_description(page) -> str:
    """Extracts description text from the iframe with id='desc'."""
    try:
        frame = page.frame(name="desc") or page.frame(url=re.compile(".*desc.*"))
        if not frame:
            print("[desc] iframe #desc not found.")
            return ""

        desc = frame.eval_on_selector(
            ".x-item-description-child",
            "el => el.innerText.trim()"
        )

        if desc:
            print("[desc] Description found inside iframe #desc.")
            return desc

        print("[desc] .x-item-description-child not found inside iframe.")
        return ""

    except Exception as e:
        print(f"[desc] Error extracting description: {e}")
        return ""

def download_ebay_images(page, ebay_title: str):
    # Get image URLs only from the FIRST carousel container
    img_urls = page.eval_on_selector(
        ".ux-image-carousel.img-transition-medium",  # first match only
        """(container) => {
            const items = container.querySelectorAll('.ux-image-carousel-item');
            return Array.from(items)
                .map(item => item.firstChild && item.firstChild.currentSrc)
                .filter(src => !!src);
        }"""
    )

    if not img_urls:
        print("\nNo images found in the FIRST eBay carousel.")
        return

    print("\nFound the following image URLs on the eBay listing:")
    for u in img_urls:
        print("  -", u)

    save_dir = DOWNLOAD_DIR

    print(f"\nDownloading {len(img_urls)} images to: {save_dir}")

    for idx, url in enumerate(img_urls, start=1):
        ext = url.split("?")[0].split(".")[-1].lower()
        if ext not in {"jpg", "jpeg", "png", "gif", "webp"}:
            ext = "jpg"

        filename = save_dir / f"{sanitize_for_filename(ebay_title)}_{idx:02d}.{ext}"

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            with open(filename, "wb") as f:
                f.write(resp.content)
            print(f"  ✓ Saved {filename.name}")

            # Convert WEBP → JPG if needed
            filename = convert_webp_to_jpg(filename)
            
            # Ensure 1:1 ratio, top-anchored crop
            filename = make_square_top_crop(filename)
        except Exception as e:
            print(f"  ✗ Failed to download {url}: {e}")


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
        ebay_title = (
            page.locator(
                "h1.x-item-title__mainTitle span.ux-textspans--BOLD"
            )
            .first.inner_text()
            .strip()
        )
        print(f"\nEBAY LISTING TITLE:\n{ebay_title}")
        
        # Department (Men, Women, etc.)
        try:
            ebay_department = page.eval_on_selector(
                "dl.ux-labels-values--department dd .ux-textspans",
                "el => el.textContent.trim()"
            )
        except Exception:
            ebay_department = None

        print(f"EBAY DEPARTMENT: {ebay_department}")

        # Size (e.g. S, M, L, 10, 32x32, etc.)
        try:
            ebay_size = page.eval_on_selector(
                "dl.ux-labels-values--size dd .ux-textspans",
                "el => el.textContent.trim()"
            )
        except Exception:
            ebay_size = None

        print(f"EBAY SIZE: {ebay_size}")
        
        # Condition (e.g. "New with tags", "Pre-owned", "Excellent", etc.)
        try:
            ebay_condition = page.eval_on_selector(
                "dl.ux-labels-values--condition dd .ux-textspans",
                "el => el.textContent.trim()"
            )
        except Exception:
            ebay_condition = None

        print(f"EBAY CONDITION: {ebay_condition}")
        
        # Price → int
        try:
            raw_price = page.eval_on_selector(
                "div.x-price-primary .ux-textspans",
                "el => el.textContent.trim()"
            )
            ebay_price = int(round(float(re.sub(r'[^0-9.]', '', raw_price))))
        except Exception:
            ebay_price = None

        print(f"EBAY PRICE INT: {ebay_price}")

        # Get eBay description from iframe #desc
        ebay_description = get_ebay_description(page)
        print(f"\nEBAY DESCRIPTION (first 200 chars): {ebay_description[:200]!r}")

        # Get eBay category from last breadcrumb item
        ebay_category = page.eval_on_selector(
            "nav.breadcrumbs ul li:last-child span",
            "el => el.textContent.trim()"
        )
        print(f"\nEBAY CATEGORY: {ebay_category}")
        print(f"\nEBAY LISTING TITLE:\n{ebay_title}")
        print(f"\nEBAY DESCRIPTION (truncated):\n{ebay_description[:200]}")

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
        titles = [el.inner_html().strip() for el in title_loc.all()]
        total_listings = len(titles)
        print(f"\nTotal listing cards detected: '{total_listings}'")

        # STEP 5: Check if eBay title is already present in Poshmark titles
        ebay_norm = ebay_title.lower().strip()
        print("### TITLE ###" + ebay_norm)

        matches = []
        for t in titles:
            t_norm = t.lower().strip()
            if ebay_norm in t_norm or t_norm in ebay_norm:
                matches.append(t)

        if matches:
            print("\nRESULT: Listing FOUND in Poshmark closet.")
            print("Matching titles:")
            for m in matches:
                print(f"  - {m}")

        else:
            print("\nRESULT: Listing NOT found in Poshmark closet.")

            # Download images from the current eBay listing page
            download_ebay_images(page, ebay_title)

            # Navigate Poshmark tab to the Create Listing page
            print(f"\nOpening Poshmark Create Listing page: {POSH_CREATE_URL}")
            posh_page.goto(POSH_CREATE_URL, wait_until="domcontentloaded")

            # Wait for the file input to exist
            posh_page.wait_for_selector("#img-file-input", timeout=15000)

            # Find all JPG files downloaded for this eBay listing
            jpg_files = sorted(
                DOWNLOAD_DIR.glob(f"{sanitize_for_filename(ebay_title)}_*.jpg")
            )

            if not jpg_files:
                print("\nNo JPG files found to upload.")
            else:
                print(f"\nUploading {len(jpg_files)} images to Poshmark...")

                # Upload directly to the file input (bypasses OS dialog)
                posh_page.set_input_files(
                    "#img-file-input",
                    [str(path) for path in jpg_files],
                )

                print("✓ Upload complete")
                # Wait for Apply button to appear in the popup and click it
                try:
                    posh_page.wait_for_selector("button[data-et-name='apply']", timeout=15000)
                    posh_page.click("button[data-et-name='apply']")
                    print("✓ Apply button clicked")
                except Exception as e:
                    print(f"✗ Failed to click Apply button: {e}")
                    
            main_cat, cat_label = map_ebay_category_to_posh(
                ebay_category,
                ebay_title,
                ebay_department,
            )

            category_ok = set_posh_category(posh_page, main_cat, cat_label)
            if not category_ok:
                raise RuntimeError("Failed to set Poshmark category; cannot continue.")

            fill_posh_fields_from_ebay(
                posh_page,
                ebay_title=ebay_title,
                ebay_description=ebay_description,
                ebay_size=ebay_size,
                ebay_condition=ebay_condition,
                ebay_price=ebay_price,
            )
            
            # === Final Steps: Next → List This Item ===
            try:
                # Click the NEXT button after all fields are filled
                posh_page.wait_for_selector("button[data-et-name='next']", timeout=15000)
                posh_page.click("button[data-et-name='next']")
                print("✓ Next button clicked")
            except Exception as e:
                print(f"✗ Failed to click Next button: {e}")

            # LIST THIS ITEM
            try:
                posh_page.wait_for_selector("button[data-et-name='list']", timeout=15000)
                posh_page.click("button[data-et-name='list']")
                print("✓ List This Item clicked")
            except Exception as e:
                print(f"✗ Failed to click List This Item button: {e}")

        print("\nReview the browser if you want. Press ENTER here to close...")
        input()

        browser.close()


if __name__ == "__main__":
    main()
