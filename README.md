# eBay Automation Project

This project automates interactions with eBay in a controlled and safe way.

## Purpose

The initial goal is:

* Launch a browser using the existing logged-in session
* Open the **eBay → Selling → Active Listings** page

This lays the foundation for:

* Scrolling listings
* Extracting titles, descriptions, prices
* Downloading images
* Preparing Poshmark listings

All of this is done **locally** — the user has full control.

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

You will now see your shell prompt prefixed like this:

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
