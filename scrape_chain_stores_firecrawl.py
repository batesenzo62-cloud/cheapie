"""
Cheapie — chain store scraper using Firecrawl

Covers the big JS-rendered chains: Woolworths, New World, PAK'nSAVE.

2026-08-03: Liquorland removed from this scraper — it used to be here too,
but that approach only ever covered 4 of Liquorland's 9 real categories,
and its "confirmed" ?p=N pagination turned out to silently return page 1
every time (Firecrawl was calling it correctly; the assumption that this
site needed JS rendering to page through results was just wrong). Fully
replaced by scrape_liquorland_full.py, which scrapes every real category
directly via plain HTTP requests — no Firecrawl credits needed at all.
Left in TARGETS here, it would have re-introduced that stale, incomplete
data on this workflow's next scheduled run.

HOW TO RUN:
1. export FIRECRAWL_API_KEY="fc-your-key-here"
2. pip install -r requirements.txt
3. python3 scrape_chain_stores_firecrawl.py

NOTE on URLs: as of 2026-07-23 all URLs below were verified to exist via
search-engine indexing (title/snippet match for each page), which is a much
stronger signal than the original pattern-matched guesses. As of the same
date, beer/RTD targets have also been confirmed live via an actual Firecrawl
run (166 products found across Liquorland/Woolworths/New World); PAK'nSAVE
and the new wine/spirits targets below are URL-verified only, not yet
confirmed by a live scrape.

NOTE on spirits: by NZ law (Sale and Supply of Alcohol Act), supermarkets
can only sell beer, wine and cider — not spirits. That's why none of
Woolworths, New World or PAK'nSAVE have a "spirits" entry below — this
isn't a scraping gap, it's real (and it's why Liquorland, the one dedicated
bottle store that used to be in this list, needed spirits coverage that
this Firecrawl-based approach could never do properly anyway).

NOTE on wine: none of the three supermarket chains has one single "wine"
category the way they do for beer — it's split into red/white/rosé/etc.
siblings. Red, white, rosé and sparkling are scraped as separate targets
below, all tagged category "wine".

NOTE on cider: legal for supermarkets (unlike spirits) and was previously
just missing from TARGETS below — added for New World/PAK'nSAVE, mapped to
category "beer" (same convention already used for the independent chains,
e.g. Black Bull/Bottle-O's cider->beer mapping).

2026-08-12: added real pagination. Firecrawl already proved it can get
through Cloudflare (that's how the single-page version got its first real
products), so the open question was only ever whether the ?pg=N param
does anything — not whether Firecrawl can reach page 2 at all. Rather than
trust the param blindly (Liquorland's old ?p=N looked identical but
silently kept returning page 1 every time — see scrape_liquorland_full.py
for how that was caught), scrape_paginated_firecrawl() below compares each
page's product names against the previous page and stops the moment they
match, instead of just stopping on an arbitrary page cap.

If a target returns 0 products, share the printed debug output with
Claude and the URL can be corrected.
"""

import os
import time
import csv
import requests

API_KEY = os.environ.get("FIRECRAWL_API_KEY")
if not API_KEY:
    raise SystemExit(
        "Set the FIRECRAWL_API_KEY environment variable first — see the "
        "instructions at the top of this file."
    )

# Each target: (store_name, url, category). Not paginated — Woolworths'
# category URLs show no visible page param at all (possibly infinite
# scroll under the hood), and guessing one would repeat exactly the
# mistake this file's docstring already warns about.
TARGETS = [
    ("Woolworths", "https://www.woolworths.co.nz/shop/browse/beer-wine/beer/lager-ale-stout-beer", "beer"),
    ("Woolworths", "https://www.woolworths.co.nz/shop/browse/beer-wine/seltzer-alcoholic-kombucha", "rtd"),
    ("Woolworths", "https://www.woolworths.co.nz/shop/browse/beer-wine/red-wine", "wine"),
    ("Woolworths", "https://www.woolworths.co.nz/shop/browse/beer-wine/white-wine", "wine"),
]

# Each target: (store_name, url_template, category). url_template contains
# a literal "{page}" placeholder — New World/PAK'nSAVE's own URLs already
# use a confirmed real "?pg=N" param (unlike Woolworths above), so these
# go through scrape_paginated_firecrawl() instead of a single fetch.
PAGINATED_TARGETS = [
    ("New World", "https://www.newworld.co.nz/shop/category/beer-wine-and-cider/beer?pg={page}", "beer"),
    ("New World", "https://www.newworld.co.nz/shop/category/beer-wine-and-cider/cider?pg={page}", "beer"),
    ("New World", "https://www.newworld.co.nz/shop/category/beer-wine-and-cider/seltzers--other-alcoholic-drinks?pg={page}", "rtd"),
    ("New World", "https://www.newworld.co.nz/shop/category/beer-wine-and-cider/red-wine?pg={page}", "wine"),
    ("New World", "https://www.newworld.co.nz/shop/category/beer-wine-and-cider/white-wine?pg={page}", "wine"),
    ("New World", "https://www.newworld.co.nz/shop/category/beer-wine-and-cider/rose-wine?pg={page}", "wine"),
    ("New World", "https://www.newworld.co.nz/shop/category/beer-wine-and-cider/sparkling-wine?pg={page}", "wine"),
    ("PAK'nSAVE", "https://www.paknsave.co.nz/shop/category/beer-wine-and-cider/beer?pg={page}", "beer"),
    ("PAK'nSAVE", "https://www.paknsave.co.nz/shop/category/beer-wine-and-cider/cider?pg={page}", "beer"),
    ("PAK'nSAVE", "https://www.paknsave.co.nz/shop/category/beer-wine-and-cider/seltzers--other-alcoholic-drinks?pg={page}", "rtd"),
    ("PAK'nSAVE", "https://www.paknsave.co.nz/shop/category/beer-wine-and-cider/red-wine?pg={page}", "wine"),
    ("PAK'nSAVE", "https://www.paknsave.co.nz/shop/category/beer-wine-and-cider/white-wine?pg={page}", "wine"),
    ("PAK'nSAVE", "https://www.paknsave.co.nz/shop/category/beer-wine-and-cider/rose-wine?pg={page}", "wine"),
    ("PAK'nSAVE", "https://www.paknsave.co.nz/shop/category/beer-wine-and-cider/sparkling-wine?pg={page}", "wine"),
]

# Bounds the worst case if pagination turns out to be real but the site
# genuinely never runs out of pages (shouldn't happen for a single
# category at one supermarket chain, but this is real money per page).
MAX_PAGES_PER_TARGET = 15

SCHEMA = {
    "type": "object",
    "properties": {
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string"},
                    "price": {"type": "string"},
                    "was_price": {"type": ["string", "null"]},
                    "in_stock": {"type": "boolean"},
                },
                "required": ["product_name", "price"],
            },
        }
    },
    "required": ["products"],
}

PROMPT = (
    "Extract every product listed on this page, including its name, "
    "current price, the original price if it's on special, and whether "
    "it's currently in stock."
)


def scrape_with_firecrawl(url):
    submit = requests.post(
        "https://api.firecrawl.dev/v1/extract",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"urls": [url], "prompt": PROMPT, "schema": SCHEMA},
        timeout=60,
    )
    submit.raise_for_status()
    submit_data = submit.json()

    if "data" in submit_data:
        return submit_data

    job_id = submit_data.get("id")
    if not job_id:
        print(f"  Unexpected response, no job id: {submit_data}")
        return {"data": {}}

    for attempt in range(15):
        time.sleep(4)
        status_resp = requests.get(
            f"https://api.firecrawl.dev/v1/extract/{job_id}",
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=30,
        )
        status_resp.raise_for_status()
        status_data = status_resp.json()
        status = status_data.get("status")
        print(f"  Job status: {status} (check {attempt + 1})")
        if status == "completed":
            return status_data
        if status == "failed":
            print(f"  Job failed: {status_data}")
            return {"data": {}}

    print("  Gave up waiting after 60 seconds — job may still be processing.")
    return {"data": {}}


def scrape_target(store_name, url, category):
    result = scrape_with_firecrawl(url)
    return result.get("data", {}).get("products", []), result


def scrape_paginated_firecrawl(url_template):
    # Verifies the pagination param is real instead of trusting it: stops
    # the moment a page's product names exactly match the previous page's,
    # rather than trusting ?pg=N to keep advancing just because the URL
    # changed. See the module docstring for why this matters — Liquorland's
    # old ?p=N param looked identical to this and silently returned page 1
    # forever.
    all_products = []
    prev_names = None
    for page in range(1, MAX_PAGES_PER_TARGET + 1):
        url = url_template.format(page=page)
        result = scrape_with_firecrawl(url)
        products = result.get("data", {}).get("products", [])
        if not products:
            if page == 1:
                print(f"  Raw response for debugging: {result}")
            break
        names = frozenset(p.get("product_name", "") for p in products)
        if prev_names is not None and names == prev_names:
            print(f"  page {page} identical to page {page - 1} — pagination isn't real here, stopping")
            break
        print(f"  page {page}: {len(products)} products")
        all_products.extend(products)
        prev_names = names
        if page < MAX_PAGES_PER_TARGET:
            time.sleep(2)
    return all_products


def main():
    all_products = []
    for store_name, url, category in TARGETS:
        print(f"Scraping {store_name} ({category}) via Firecrawl...")
        try:
            products, last_result = scrape_target(store_name, url, category)
            print(f"  Found {len(products)} products total.")
            if not products:
                print(f"  Raw response for debugging: {last_result}")
            for p in products:
                p["store"] = store_name
                p["category"] = category
                p["fetched_at"] = time.strftime("%Y-%m-%d %H:%M")
                all_products.append(p)
        except Exception as exc:
            print(f"  Could not scrape {store_name} ({category}): {exc}")
        time.sleep(2)

    for store_name, url_template, category in PAGINATED_TARGETS:
        print(f"Scraping {store_name} ({category}) via Firecrawl (paginated)...")
        try:
            products = scrape_paginated_firecrawl(url_template)
            print(f"  Found {len(products)} products total.")
            for p in products:
                p["store"] = store_name
                p["category"] = category
                p["fetched_at"] = time.strftime("%Y-%m-%d %H:%M")
                all_products.append(p)
        except Exception as exc:
            print(f"  Could not scrape {store_name} ({category}): {exc}")
        time.sleep(2)

    if not all_products:
        # A real failure (e.g. Firecrawl out of credits), not just "nothing
        # matched" — must exit non-zero so this is actually visible (e.g. in
        # a scheduled GitHub Actions run) instead of looking like a quiet
        # success that happened to write zero rows.
        raise SystemExit("No products found across any target — see the errors printed above.")

    with open("chain_store_prices.csv", "w", newline="", encoding="utf-8") as f:
        fieldnames = list(all_products[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_products)

    print(f"Done. Wrote {len(all_products)} products to chain_store_prices.csv")


if __name__ == "__main__":
    main()
