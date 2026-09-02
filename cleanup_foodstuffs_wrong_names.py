"""
Cheapie — one-off cleanup for New World/PAK'nSAVE rows scraped before the
brand-name fix (scrape_foodstuffs_products.py, 2026-09-03).

Every branded product's own brand ("Steinlager", "Speight's", ...) was
missing from product_name up to this point — reported directly, then
confirmed live. Re-running the fixed scraper alone would leave the old,
wrongly-named rows behind as orphaned duplicates (the upsert key includes
product_name, which is changing for every branded row), so this deletes
every existing per-branch New World/PAK'nSAVE row first — the next
scheduled scrape re-populates them correctly. Only rows with a real
store_id are targeted (the confirmed per-branch data this whole fix is
about) — nothing else is touched.

2026-09-03 fix: the first version filtered on `store_name ilike
'*New World*'` directly against the products table — confirmed directly
this hits a real Postgres statement timeout (same class of issue already
hit and fixed for the coverage-check queries and load_data_to_supabase.py's
store_id validation earlier this session), since a leading-wildcard ilike
forces a full scan of a 400K+-row table. Gets the real store_ids from the
small `stores` table first instead, deletes by exact store_id (indexed,
fast), one store at a time and with `Prefer: return=minimal` (no reason to
have Postgres build and return the full deleted row set) rather than one
giant multi-store delete statement.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-service-role-or-secret-key"
    python3 cleanup_foodstuffs_wrong_names.py
"""
import os
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY environment variables first.")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Prefer": "return=minimal",
}


def get_store_ids(name_filter):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/stores",
        headers={"apikey": SUPABASE_KEY},
        params={"select": "id,name", "name": f"ilike.*{name_filter}*", "limit": "1000"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def delete_store(store_id, store_name):
    for attempt in range(3):
        r = requests.delete(
            f"{SUPABASE_URL}/rest/v1/products",
            headers=HEADERS,
            params={"store_id": f"eq.{store_id}"},
            timeout=30,
        )
        if r.status_code in (200, 204):
            return
        print(f"    attempt {attempt + 1} for {store_name} ({store_id}): status {r.status_code} {r.text[:150]}")
    raise SystemExit(f"Delete failed for {store_name} ({store_id}) after 3 attempts")


def main():
    for name_filter in ["New World", "PAK*SAVE"]:
        stores = get_store_ids(name_filter)
        print(f"Deleting old wrongly-named rows for {len(stores)} {name_filter} stores...")
        for s in stores:
            delete_store(s["id"], s["name"])
        print(f"  done: {len(stores)} stores cleared")


if __name__ == "__main__":
    main()
