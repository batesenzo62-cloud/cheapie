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
    "Prefer": "return=representation",
}


def delete_chain(name_filter):
    r = requests.delete(
        f"{SUPABASE_URL}/rest/v1/products",
        headers=HEADERS,
        params={"store_name": f"ilike.*{name_filter}*", "store_id": "not.is.null"},
        timeout=60,
    )
    if r.status_code not in (200, 204):
        raise SystemExit(f"Delete failed for '{name_filter}' (status {r.status_code}): {r.text}")
    deleted = len(r.json()) if r.text else 0
    print(f"  deleted: {deleted} rows for store_name ilike '*{name_filter}*'")


def main():
    for name_filter in ["New World", "PAK*SAVE"]:
        print(f"Deleting old wrongly-named rows for {name_filter}...")
        delete_chain(name_filter)


if __name__ == "__main__":
    main()
