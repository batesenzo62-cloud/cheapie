"""
Cheapie — New World / PAK'nSAVE per-branch product scraper.

Both chains have been stuck on a single Firecrawl-scraped national
catalogue (scrape_chain_stores_firecrawl.py) since real per-branch
pricing was ruled out as too expensive (~$333/mo Growth tier just for
monthly updates). Investigated a completely different, genuinely free
path instead — checking for a hidden JSON API first, per direct request,
before considering anything closer to bot-detection evasion.

Confirmed live, directly:
- www.newworld.co.nz / www.paknsave.co.nz are Cloudflare-challenge
  protected (403 "Just a moment...") — the shop/category HTML pages
  can't be reached with plain requests, matching earlier findings.
- BUT api-prod.newworld.co.nz / api-prod.paknsave.co.nz — the real
  internal API both sites' own frontend calls for product search — has
  NO such protection. Confirmed with a plain requests.post(), no
  browser, no stealth, no cookies from a prior "real" session: 200 OK,
  real structured JSON with real prices.
- The anonymous auth token these API calls need is itself obtained from
  www.{domain}/api/user/get-current-user — also plain HTTP, no
  Cloudflare challenge (only the *page* routes are protected, not the
  /api/ ones). So the entire pipeline — token, store list, paginated
  per-store product search — never touches the protected surface at
  all. This isn't a workaround for the site's bot protection; it's a
  different, unprotected part of the same site.

Real store lists (from /v1/edge/store) matched to this app's `stores`
table by a normalized name (handles macrons — Māngere/Mangere,
Tūrangi/Turangi — and St/Street, Mt/Mount, Dr/Drive abbreviation
differences) — confirmed directly: 148/149 New World and 56/57
PAK'nSAVE matched automatically, the 2 remaining odd ones covered by
NAME_ALIASES below. Existing stores' own store_id (already real,
already used elsewhere in this app) is reused rather than creating
duplicate rows — unlike Big Barrel/Liquorland, no new store rows were
needed here at all.

NOTE on multi-buy deals: each promotion object already carries
multiProducts/threshold/rewardValue fields (confirmed live — e.g.
threshold=2, multiProducts=true would mean a real "2 for $rewardValue"
deal), which is exactly the structured data the multi-buy deals feature
needs. Not wired into this CSV yet since the products table doesn't have
multibuy_quantity/multibuy_total_price columns yet (separate, still-
queued task) — see extract_rows() below, which already captures these
fields on each row internally, just doesn't write them out until those
columns exist.

HOW TO RUN:
    BRAND=paknsave python3 scrape_foodstuffs_products.py
    BRAND=newworld python3 scrape_foodstuffs_products.py
    # or, chunked:
    BRAND=paknsave CHUNK_INDEX=0 CHUNK_COUNT=2 python3 scrape_foodstuffs_products.py
"""
import csv
import os
import re
import time
import unicodedata

import requests

SUPABASE_URL = "https://gkkchssgamqfavomcnoq.supabase.co"
SUPABASE_KEY = "sb_publishable_0D5UFWvifa2lI9o5lPbK8Q_iOsnLW8b"

BRAND = os.environ.get("BRAND", "paknsave")
if BRAND not in ("paknsave", "newworld"):
    raise SystemExit("Set BRAND to 'paknsave' or 'newworld'.")
DOMAIN = f"{BRAND}.co.nz"
DB_NAME_FILTER = "PAK*SAVE" if BRAND == "paknsave" else "New World"
STORE_LABEL_PREFIX = "PAK'nSAVE" if BRAND == "paknsave" else "New World"

CHUNK_INDEX = int(os.environ.get("CHUNK_INDEX", "0"))
CHUNK_COUNT = int(os.environ.get("CHUNK_COUNT", "1"))

HEADERS_BASE = {"User-Agent": "Mozilla/5.0"}

# 2026-09-02: NZ law (Sale and Supply of Alcohol Act) means supermarkets
# can't sell spirits — same reasoning already documented in
# scrape_chain_stores_firecrawl.py — so there's no spirits mapping here,
# consistent with that. "Lower Alcohol Drinks" and "Alcohol Free Drinks"
# (real top-level categories in the site's own tree) are deliberately
# excluded — the former mixes real-but-weak alcohol with wine in a way
# that doesn't cleanly map to one app category, the latter is genuinely
# 0% by definition, same exclusion this app already applies elsewhere.
TOP_CATEGORY = "Beer, Wine & Cider"
CATEGORIES = [
    ("Beer", "beer"),
    ("Craft Beer", "beer"),
    ("Cider", "beer"),
    ("Seltzers & Other Alcoholic Drinks", "rtd"),
    ("Champagne & Sparkling Wine", "wine"),
    ("Red Wine", "wine"),
    ("White Wine", "wine"),
    ("Rose Wine", "wine"),
    ("Moscato & Sweet Wine", "wine"),
    ("Cask Wine", "wine"),
    ("Mini Wine Bottles & Cans", "wine"),
]

# Covers the 2 real-store names normalize() can't reconcile on its own
# (confirmed directly — every other store matched automatically):
# "New World Metro Willis St" (API) vs "New World Willis Street Metro"
# (this app's stores table) has "Metro" in a different position; PAK'nSAVE
# Napier City (API) vs this app's plain "PAK'nSAVE Napier".
NAME_ALIASES = {
    "new world metro willis street": "new world willis street metro",
    "paknsave napier city": "paknsave napier",
}


def normalize(name):
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower()
    name = re.sub(r"pak'?n\s*save", "paknsave", name)
    name = re.sub(r"\bmt\b", "mount", name)
    name = re.sub(r"\bst\b", "street", name)
    name = re.sub(r"\bdr\b", "drive", name)
    name = re.sub(r"\brd\b", "road", name)
    name = re.sub(r"[^a-z0-9]+", " ", name)
    name = name.strip()
    return NAME_ALIASES.get(name, name)


def get_token():
    for attempt in range(3):
        try:
            r = requests.post(
                f"https://www.{DOMAIN}/api/user/get-current-user",
                headers={**HEADERS_BASE, "content-type": "application/json"},
                json={"fingerprintUser": "cheapie-scraper", "fingerprintGuest": "cheapie-scraper"},
                timeout=20,
            )
            r.raise_for_status()
            return r.json()["access_token"]
        except Exception as e:
            print(f"  token attempt {attempt + 1} error: {e}")
            time.sleep(5)
    raise RuntimeError("Could not get an access token after 3 attempts")


def get_real_stores(token):
    r = requests.get(
        f"https://api-prod.{DOMAIN}/v1/edge/store",
        headers={"authorization": f"Bearer {token}", **HEADERS_BASE},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["stores"]


def fetch_db_store_ids():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/stores",
        headers={"apikey": SUPABASE_KEY},
        params={"select": "id,name", "name": f"ilike.*{DB_NAME_FILTER}*", "limit": "1000"},
        timeout=20,
    )
    return r.json()


def build_branch_list(token):
    real_stores = get_real_stores(token)
    db_stores = fetch_db_store_ids()
    db_by_norm = {}
    for s in db_stores:
        db_by_norm.setdefault(normalize(s["name"]), []).append(s)

    branches = []
    for s in real_stores:
        n = normalize(s["name"])
        matches = db_by_norm.get(n)
        if matches and len(matches) == 1:
            branches.append((s["name"], s["id"], matches[0]["id"]))
        else:
            print(f"  WARNING: no unique stores row matched for '{s['name']}' (norm='{n}') — skipping")
    branches.sort()  # stable order so [start::step] chunking is deterministic across parallel jobs
    return branches


def fetch_category_page(token, real_store_id, category_name, page):
    headers = {"authorization": f"Bearer {token}", "content-type": "application/json", **HEADERS_BASE}
    body = {
        "algoliaQuery": {
            "attributesToHighlight": [],
            "attributesToRetrieve": ["productID", "Type", "sponsored", "category0NI", "category1NI", "category2NI"],
            "facets": ["brand", "category2NI", "onPromotion", "productFacets", "tobacco"],
            "filters": f'stores:{real_store_id} AND category0NI:"{TOP_CATEGORY}" AND category1NI:"{category_name}"',
            "hitsPerPage": 50,
            "maxValuesPerFacet": 100,
            "page": page,
            "analyticsTags": ["fs#WEB:desktop"],
        },
        "algoliaFacetQueries": [],
        "storeId": real_store_id,
        "hitsPerPage": 50,
        "page": page,
        "sortOrder": "NI_POPULARITY_ASC",
        "tobaccoQuery": False,
        "precisionMedia": {"adDomain": "CATEGORY_PAGE", "adPositions": [3, 6, 9], "publishImpressionEvent": False, "disableAds": True},
    }
    for attempt in range(3):
        r = requests.post(
            f"https://api-prod.{DOMAIN}/v1/edge/search/paginated/products",
            headers=headers, json=body, timeout=20,
        )
        if r.status_code == 401:
            raise PermissionError("token expired")
        if r.ok:
            return r.json()
        print(f"    attempt {attempt + 1}: status {r.status_code}")
        time.sleep(3)
    return None


def scrape_category(token, real_store_id, category_name):
    all_products = []
    page = 0
    while True:
        data = fetch_category_page(token, real_store_id, category_name, page)
        if not data:
            break
        all_products.extend(data.get("products", []))
        total_pages = data.get("totalPages", 1)
        page += 1
        if page >= total_pages:
            break
        time.sleep(0.3)
    return all_products


def extract_rows(store_label, store_id, app_category, products):
    rows = []
    for p in products:
        price_info = p.get("singlePrice") or {}
        price_cents = price_info.get("price")
        if price_cents is None:
            continue
        name = (p.get("name") or "").strip()
        display = (p.get("displayName") or "").strip()
        full_name = f"{name} {display}".strip()
        if not full_name:
            continue

        # Not written to the CSV yet (products table has no multibuy_*
        # columns) — kept here so wiring in the multi-buy deals feature
        # later only means adding these two keys to the output dict.
        multibuy_quantity = None
        multibuy_total_price = None
        for promo in p.get("promotions", []):
            if promo.get("multiProducts") and (promo.get("threshold") or 1) > 1:
                multibuy_quantity = promo["threshold"]
                multibuy_total_price = promo["rewardValue"] / 100

        rows.append({
            "store": store_label,
            "store_id": store_id,
            "category": app_category,
            "product_name": full_name,
            "price": price_cents / 100,
            "was_price": "",
            "in_stock": bool(p.get("availability")),
            "url": "",
            "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
            "_multibuy_quantity": multibuy_quantity,
            "_multibuy_total_price": multibuy_total_price,
        })
    return rows


def main():
    token = get_token()
    token_fetched_at = time.time()
    branches = build_branch_list(token)[CHUNK_INDEX::CHUNK_COUNT]
    print(f"Chunk {CHUNK_INDEX + 1}/{CHUNK_COUNT}: {len(branches)} {STORE_LABEL_PREFIX} branches this run")

    new_rows = []
    for label, real_store_id, store_id in branches:
        # Token is valid ~28 minutes (confirmed directly from its own exp
        # claim) — refresh proactively rather than waiting for a 401 mid-
        # branch, so a slow chunk never loses a partially-scraped branch
        # to an expired token.
        if time.time() - token_fetched_at > 20 * 60:
            token = get_token()
            token_fetched_at = time.time()

        print(f"Scraping {label} ({real_store_id})...")
        branch_products = 0
        for category_name, app_category in CATEGORIES:
            try:
                products = scrape_category(token, real_store_id, category_name)
                rows = extract_rows(label, store_id, app_category, products)
                new_rows.extend(rows)
                branch_products += len(rows)
            except PermissionError:
                token = get_token()
                token_fetched_at = time.time()
                try:
                    products = scrape_category(token, real_store_id, category_name)
                    rows = extract_rows(label, store_id, app_category, products)
                    new_rows.extend(rows)
                    branch_products += len(rows)
                except Exception as e:
                    print(f"  {category_name} error after token refresh: {e}")
            except Exception as e:
                print(f"  {category_name} error: {e}")
            time.sleep(0.3)
        print(f"  {branch_products} products")

    print(f"\nTotal new branch-specific rows: {len(new_rows)}")

    scraped_labels = {label for label, _, _ in branches}
    if os.path.exists("independent_store_prices.csv"):
        with open("independent_store_prices.csv") as f:
            existing = list(csv.DictReader(f))
    else:
        existing = []

    fieldnames = ["store", "category", "product_name", "price", "was_price", "in_stock", "url", "fetched_at", "store_id"]
    for row in existing:
        row.setdefault("store_id", "")

    kept = [row for row in existing if row["store"] not in scraped_labels]
    all_rows_out = kept + [{k: r.get(k, "") for k in fieldnames} for r in new_rows]
    with open("independent_store_prices.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows_out)

    print(f"Wrote {len(all_rows_out)} total rows ({len(new_rows)} fresh branch-specific {STORE_LABEL_PREFIX} rows)")


if __name__ == "__main__":
    main()
