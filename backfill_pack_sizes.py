"""
Cheapie — backfill unit_count / unit_volume_ml / price_per_litre for
products already sitting in Supabase from before this feature existed.

load_data_to_supabase.py only ever inserts new rows, so this is a one-off
pass to fill in the same fields on everything that's already loaded.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-service-role-or-secret-key"
    python3 backfill_pack_sizes.py
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from parse_pack_size import parse_pack_size

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY environment variables first.")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def fetch_all_products():
    rows = []
    offset = 0
    page_size = 1000
    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/products",
            headers=HEADERS,
            params={"select": "id,product_name,price,category", "offset": offset, "limit": page_size},
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def price_per_litre(price, unit_count, unit_volume_ml):
    if price is None or not unit_volume_ml:
        return None
    litres = (unit_count * unit_volume_ml) / 1000
    return round(price / litres, 4) if litres > 0 else None


def patch_one(item):
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/products",
        headers={**HEADERS, "Prefer": "return=minimal"},
        params={"id": f"eq.{item['id']}"},
        json={
            "unit_count": item["unit_count"],
            "unit_volume_ml": item["unit_volume_ml"],
            "price_per_litre": item["price_per_litre"],
        },
        timeout=15,
    )
    return item["id"], resp.status_code


def main():
    print("Fetching existing products...")
    rows = fetch_all_products()
    print(f"  {len(rows)} rows to backfill.")

    payload = []
    for row in rows:
        unit_count, unit_volume_ml = parse_pack_size(row.get("product_name"), row.get("category"))
        ppl = price_per_litre(row.get("price"), unit_count, unit_volume_ml)
        payload.append({
            "id": row["id"],
            "unit_count": unit_count,
            "unit_volume_ml": unit_volume_ml,
            "price_per_litre": ppl,
        })

    # products.id is a GENERATED ALWAYS identity column, so the bulk
    # upsert-via-POST trick (used elsewhere in this project) is blocked by
    # Postgres itself. Falling back to one PATCH per row, parallelized to
    # keep ~2,500 rows from taking forever sequentially.
    updated = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(patch_one, item) for item in payload]
        for i, future in enumerate(as_completed(futures), 1):
            item_id, status = future.result()
            if status in (200, 204):
                updated += 1
            else:
                failed += 1
                print(f"  Failed on id={item_id}: HTTP {status}")
            if i % 250 == 0:
                print(f"  ...{i}/{len(payload)} processed")

    print(f"Done. {updated} updated, {failed} failed, out of {len(payload)}.")


if __name__ == "__main__":
    main()
