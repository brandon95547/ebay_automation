# eBay Automation Project

This project automates interactions with eBay in a controlled and safe way.

## Purpose

The initial goal is:

- Launch a browser using the existing logged-in session
- Open the eBay Selling → Active Listings page

This lays the foundation for:

- Scrolling listings
- Extracting titles, descriptions, prices
- Downloading images
- Preparing Poshmark listings

All of this is done **locally** and the user has full control.

## Setup

### 1. Create project folder

```bash
mkdir ebay_automation
cd ebay_automation
```

### 2. Running
python ebay_open.py