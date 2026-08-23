"""
Cheapie — load scraped CSV data into Supabase

Reads independent_store_prices.csv and chain_store_prices.csv and upserts
their rows into the "products" table in your Supabase project, matched on
(store_name, product_name) — safe to re-run on a schedule: existing
products get their price/stock/etc. refreshed in place, new ones get
inserted, nothing is ever duplicated. Requires the unique constraint from
add_unique_constraint.sql to already exist on the table.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-service-role-or-secret-key"
    python3 load_data_to_supabase.py
"""

import os
import csv
import re
import time
import requests

from parse_pack_size import parse_pack_size

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit(
        "Set SUPABASE_URL and SUPABASE_KEY environment variables first."
    )

# on_conflict targets the (store_name, product_name) unique constraint —
# see add_unique_constraint.sql. Without it, every re-run just inserts a
# fresh copy of everything (this bit us for real once already).
TABLE_ENDPOINT = f"{SUPABASE_URL}/rest/v1/products?on_conflict=store_name,product_name"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}


# The highest genuine price anywhere in our real scraped data is ~$1,050
# (a champagne magnum) — found products with prices in the billions caused
# by a retailer's own broken GA4 tracking script (item barcode leaking into
# the price field on their site, not a scraping bug). $5,000 gives a wide
# safety margin above any real bottle while rejecting that corruption.
MAX_PLAUSIBLE_PRICE = 5000


# 2026-08-24 fix: reported directly — most of what shows up browsing
# Spirits is mixed drinks (premixed cocktails, canned RTD-style products),
# not straight spirits. A one-time DB patch fixed the 109 known cases at
# the time, but a handful were already back under "spirits" again within
# days — every store's own site still lists them under its "Spirits"
# department, and this project's scrapers still just inherit whatever
# category label each source page/URL was tagged with (same root-cause
# shape as the Summit Ultra beer-vs-spirits fix earlier this session).
# Reclassifying at load time instead of patching the DB after the fact
# means this survives every future scheduled scrape, not just today's.
#
# Patterns were built from a manual review of every distinct product name
# under spirits at the time — a few patterns tried initially caused real
# false positives and were narrowed or dropped: "X & Ginger Gin/Rum/Vodka"
# is a flavour name, not a mixer, so "and/& ginger" was dropped entirely;
# "Cocktail Glass Gift Pack" bundles a glass, not a drink, so "cocktail" is
# excluded when immediately followed by "glass"; "Pale & Dry Cognac" is a
# real cognac style term, so "& dry" excludes when preceded by "pale".
_RTD_PATTERNS = [
    re.compile(p, re.I) for p in [
        # "and/& (up to 2 extra words, e.g. Zero Sugar/Diet) cola/tonic/etc."
        r"(?:and|&)\s*(?:\w+\s+){0,2}cola\b",
        r"(?<!pale )(?:and|&)\s*(?:\w+\s+){0,2}dry\b",
        r"(?:and|&)\s*(?:\w+\s+){0,2}tonic\b",
        r"(?:and|&)\s*(?:\w+\s+){0,2}soda\b(?!.*\bsiphon\b)",
        r"(?:and|&)\s*(?:\w+\s+){0,2}lemonade\b",
        r"ready.to.serve", r"\bcocktail\b(?!\s+glass)", r"\bspritz\b",
        r"\bmojito\b", r"pina\s+colada", r"pineapple\s+colada",
        r"\bbuzzballz\b",
    ]
]
# Canned multipacks with no other RTD wording (e.g. "Malibu Watermelon
# 10x250ml Cans", "Wild Turkey 101 7% 10x330ml Cans") — genuine full-
# strength spirits are essentially never packaged in small multi-can packs
# at all, that's exclusively an RTD/premixed convention, so this doesn't
# need a stated ABV the way the false-positive review elsewhere here does.
# "cans" and the can-sized volume can appear in either order depending on
# the source site's wording, so these are checked independently rather
# than as one ordered pattern.
_CAN_VOLUME = re.compile(r"\b\d+\s*x?\s*(250|330|355|375|440)\s*ml", re.I)
_CAN_WORD = re.compile(r"\bcans?\b", re.I)


def reclassify_category(product_name, category):
    if category != "spirits" or not product_name:
        return category
    name = product_name
    if any(p.search(name) for p in _RTD_PATTERNS):
        return "rtd"
    if _CAN_VOLUME.search(name) and _CAN_WORD.search(name):
        return "rtd"
    return category


# Non-alcoholic mixers/mocktails occasionally turn up tagged as spirits on
# a retailer's own site (they're shelved near real spirits in-store) — they
# don't belong under any alcohol category at all, so these are dropped
# entirely rather than reclassified. "non alcoholic" alone is a strong,
# general signal; the specific brands below cover real cases (Schweppes/
# Fever-Tree ginger ale, Master of Mixes) that don't say it explicitly.
_MIXER_BRANDS = ["schweppes", "fever-tree", "fever tree", "fentimans", "master of mixes"]


def is_nonalcoholic_mixer(product_name, category):
    if category != "spirits" or not product_name:
        return False
    name = product_name.lower()
    if "non alcoholic" in name or "non-alcoholic" in name:
        return True
    if any(b in name for b in _MIXER_BRANDS) and not re.search(r"\d+(\.\d+)?\s*%", name):
        return True
    return False


def parse_price(raw):
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9.]", "", str(raw))
    if not cleaned:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if value > MAX_PLAUSIBLE_PRICE:
        return None
    return value


def parse_bool(raw):
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("true", "1", "yes")


def pack_size_fields(product_name, price, category=None):
    # unit_volume_ml is None whenever the name doesn't state a size at all
    # (see parse_pack_size.py) — price_per_litre stays None in that case
    # too, rather than guessing a size. unit_count is still recorded even
    # without a volume, since "12pk, size unknown" is still real information.
    #
    # 2026-08-14 walk-back: this used to null out price_per_litre entirely
    # below MIN_PLAUSIBLE_PRICE_PER_UNIT, on the theory that no real listing
    # goes that low. Reported directly, and checked live against the actual
    # retailer site: "Steinlager Classic Bottles 24 x 330mL" really is
    # $15.99 at Bottle-O Kingsland right now (a genuine duplicate listing
    # next to a $55.99 one) — a real deal this was hiding. But the exact
    # same check on a different flagged row ("Desperados Teq Beer 6x330b"
    # at $4.50) found it's genuinely stale/wrong — the live price is
    # $24.99, no duplicate. Price alone can't tell these apart; suppressing
    # the ranking outright was too blunt and cost a real find. The app now
    # shows a caveat instead (see MIN_PLAUSIBLE_PRICE_PER_UNIT's use in
    # cheapie-prototype.html) rather than hiding the number here.
    unit_count, unit_volume_ml = parse_pack_size(product_name, category)
    price_per_litre = None
    if price is not None and unit_volume_ml:
        litres = (unit_count * unit_volume_ml) / 1000
        if litres > 0:
            price_per_litre = round(price / litres, 4)
    return {
        "unit_count": unit_count,
        "unit_volume_ml": unit_volume_ml,
        "price_per_litre": price_per_litre,
    }


def load_independent_stores(filename):
    rows = []
    if not os.path.exists(filename):
        print(f"  Skipping {filename} — file not found in this folder.")
        return rows
    with open(filename, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("product_name")
            price = parse_price(row.get("price"))
            category = row.get("category") or "beer"
            if is_nonalcoholic_mixer(name, category):
                continue
            category = reclassify_category(name, category)
            row_out = {
                "product_name": name,
                "category": category,
                "store_name": row.get("store"),
                "price": price,
                "was_price": parse_price(row.get("was_price")),
                "in_stock": parse_bool(row.get("in_stock")),
                "is_online": True,
                "source_url": row.get("url"),
                "fetched_at": row.get("fetched_at") or None,
                **pack_size_fields(name, price, category),
            }
            # store_id ties a row to one confirmed physical branch (added
            # 2026-07-27 for per-branch deals scraping) — most rows still
            # won't have one, since most chains only expose one national
            # price list. Always include the key (None when absent), since
            # PostgREST's bulk upsert rejects a batch where rows don't all
            # share the exact same set of keys ("All object keys must
            # match") — this bit us for real once already.
            store_id = (row.get("store_id") or "").strip()
            row_out["store_id"] = store_id or None
            rows.append(row_out)
    return rows


def load_chain_stores(filename):
    rows = []
    if not os.path.exists(filename):
        print(f"  Skipping {filename} — file not found in this folder.")
        return rows
    with open(filename, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("product_name")
            price = parse_price(row.get("price"))
            category = row.get("category") or "beer"
            if is_nonalcoholic_mixer(name, category):
                continue
            category = reclassify_category(name, category)
            rows.append({
                "product_name": name,
                "category": category,
                "store_name": row.get("store"),
                "price": price,
                "was_price": parse_price(row.get("was_price")),
                "in_stock": parse_bool(row.get("in_stock")),
                "is_online": False,
                # 2026-08-13 fix: hardcoded None regardless of what the CSV
                # actually had — reported directly that Liquorland products
                # never had a "View product page" link at all. Its own
                # scraper does write a real url column now (falls back to
                # the category page, since it has no per-product URL
                # available); this was silently discarding it either way.
                "source_url": row.get("url") or None,
                "fetched_at": row.get("fetched_at") or None,
                "store_id": None,
                **pack_size_fields(name, price, category),
            })
    return rows


def main():
    print("Reading CSV files...")
    all_rows = []
    all_rows += load_independent_stores("independent_store_prices.csv")
    all_rows += load_chain_stores("chain_store_prices.csv")

    all_rows = [r for r in all_rows if r["product_name"] and r["price"] is not None]

    if not all_rows:
        raise SystemExit("No valid rows found to upload — both CSVs were empty or missing.")

    # A single upsert statement errors if the same (store_name, product_name)
    # key appears twice in one batch ("ON CONFLICT DO UPDATE command cannot
    # affect row a second time") — our own scrapes occasionally produce exact
    # duplicates (e.g. pagination overlap), so the last occurrence wins here
    # before we ever send the request.
    deduped = {}
    for row in all_rows:
        deduped[(row["store_name"], row["product_name"])] = row
    all_rows = list(deduped.values())

    # A single request for the whole batch works fine up to a few tens of
    # thousands of rows (confirmed — 11K and 21K both went through as one
    # request earlier), but ~198K rows timed out entirely, even at a raised
    # 120s timeout: too much for one request/transaction. Chunking keeps
    # each request's payload and Postgres-side work bounded regardless of
    # how large the source data grows.
    CHUNK_SIZE = 3000
    print(f"Upserting {len(all_rows)} rows to Supabase in chunks of {CHUNK_SIZE} (update if it exists, insert if new)...")
    for i in range(0, len(all_rows), CHUNK_SIZE):
        chunk = all_rows[i:i + CHUNK_SIZE]
        chunk_num = i // CHUNK_SIZE + 1
        total_chunks = (len(all_rows) + CHUNK_SIZE - 1) // CHUNK_SIZE
        # A transient 5xx (seen for real: a one-off Cloudflare 520) shouldn't
        # abort ~65 otherwise-successful chunks — retry a couple of times
        # with a short backoff before giving up on this chunk for good.
        response = None
        for attempt in (1, 2, 3):
            response = requests.post(TABLE_ENDPOINT, headers=HEADERS, json=chunk, timeout=120)
            if response.status_code in (200, 201):
                break
            if response.status_code >= 500 and attempt < 3:
                print(f"  chunk {chunk_num}/{total_chunks} attempt {attempt} got {response.status_code}, retrying...")
                time.sleep(5)
        if response.status_code not in (200, 201):
            # Must actually fail the process (not just print) — otherwise this
            # error is invisible to anything checking the exit code, including
            # the GitHub Actions run that's meant to surface it.
            raise SystemExit(f"Upsert failed on chunk {chunk_num}/{total_chunks} (status {response.status_code}): {response.text}")
        print(f"  chunk {chunk_num}/{total_chunks} done ({len(chunk)} rows)")

    print(f"Done. Upserted {len(all_rows)} products to Supabase.")


if __name__ == "__main__":
    main()
