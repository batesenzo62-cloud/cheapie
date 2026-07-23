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


def pack_size_fields(product_name, price):
    # unit_volume_ml is None whenever the name doesn't state a size at all
    # (see parse_pack_size.py) — price_per_litre stays None in that case
    # too, rather than guessing a size. unit_count is still recorded even
    # without a volume, since "12pk, size unknown" is still real information.
    unit_count, unit_volume_ml = parse_pack_size(product_name)
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
            rows.append({
                "product_name": name,
                "category": row.get("category") or "beer",
                "store_name": row.get("store"),
                "price": price,
                "was_price": parse_price(row.get("was_price")),
                "in_stock": parse_bool(row.get("in_stock")),
                "is_online": True,
                "source_url": row.get("url"),
                "fetched_at": row.get("fetched_at") or None,
                **pack_size_fields(name, price),
            })
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
            rows.append({
                "product_name": name,
                "category": row.get("category") or "beer",
                "store_name": row.get("store"),
                "price": price,
                "was_price": parse_price(row.get("was_price")),
                "in_stock": parse_bool(row.get("in_stock")),
                "is_online": False,
                "source_url": None,
                "fetched_at": row.get("fetched_at") or None,
                **pack_size_fields(name, price),
            })
    return rows


def main():
    print("Reading CSV files...")
    all_rows = []
    all_rows += load_independent_stores("independent_store_prices.csv")
    all_rows += load_chain_stores("chain_store_prices.csv")

    all_rows = [r for r in all_rows if r["product_name"] and r["price"] is not None]

    if not all_rows:
        print("No valid rows found to upload.")
        return

    # A single upsert statement errors if the same (store_name, product_name)
    # key appears twice in one batch ("ON CONFLICT DO UPDATE command cannot
    # affect row a second time") — our own scrapes occasionally produce exact
    # duplicates (e.g. pagination overlap), so the last occurrence wins here
    # before we ever send the request.
    deduped = {}
    for row in all_rows:
        deduped[(row["store_name"], row["product_name"])] = row
    all_rows = list(deduped.values())

    print(f"Upserting {len(all_rows)} rows to Supabase (update if it exists, insert if new)...")
    response = requests.post(TABLE_ENDPOINT, headers=HEADERS, json=all_rows, timeout=30)

    if response.status_code in (200, 201):
        print(f"Done. Upserted {len(all_rows)} products to Supabase.")
    else:
        print(f"Something went wrong (status {response.status_code}):")
        print(response.text)


if __name__ == "__main__":
    main()
