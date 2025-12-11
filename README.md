# eBay Automation Project

This project automates interactions with eBay and Poshmark in a controlled and safe way.

## Purpose

The initial goal is:

* Launch a browser using the existing logged-in session
* Open the **eBay → Selling → Active Listings** page

This lays the foundation for:

* Scrolling listings
* Extracting titles, descriptions, categories, prices
* Downloading images
* Preparing Poshmark listings
* Uploading images
* (Soon) Autofilling Poshmark listing fields

All of this is done **locally** — the user has full control.

---

# 📌 Project Call Tree / Flow Diagram

This shows the **exact execution path** of the automation script.

```
main()
│
├── setup_directories()
│
├── launch_playwright()
│   │
│   └── browser = chromium.launch_persistent_context()
│
├── open_ebay_active_listings()
│   │
│   ├── wait_for_active_listings()
│   └── click_first_listing()
│
├── extract_ebay_data()
│   │
│   ├── get_title()
│   ├── get_description()
│   ├── get_category()
│   ├── get_size()            (later)
│   ├── get_condition()       (later)
│   └── get_price()           (later)
│
├── open_poshmark_closet()
│   │
│   └── scroll_until_no_more_items()
│
├── compare_title_with_poshmark()
│   │
│   ├── if match_found:
│   │       └── STOP (listing already exists)
│   │
│   └── if NOT found:
│
│       ├── download_ebay_images()
│       │   │
│       │   ├── extract_zoom_image_urls()
│       │   ├── download_files()
│       │   ├── convert_webp_to_jpg()
│       │   └── make_square_top_crop()
│       │
│       ├── open_poshmark_create_listing()
│       │
│       ├── upload_images_to_poshmark()
│       │   └── set_input_files()
│       │
│       └── click_apply_button()
│
└── wait_for_user_and_close_browser()
```

---

## Setup

### 1. Create the project folder

```bash
mkdir ebay_automation
cd ebay_automation
```

---

### 2. Create and enter the Python 3.12 virtual environment

#### Create the venv

```bash
python3 -m venv .venv
```

#### Enter (activate) the venv

**macOS / Linux:**

```bash
source .venv/bin/activate
```

**Windows PowerShell:**

```powershell
.venv\Scripts\Activate.ps1
```

**Windows Command Prompt:**

```cmd
.venv\Scripts\activate.bat
```

Your shell prompt will now show:

```
(.venv) $
```

---

### 3. Install dependencies

```bash
pip install -r requirements.txt
playwright install
```

---

### 4. Running

```bash
python ebay_open.py
```

---