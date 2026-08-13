"""
Cheapie — one-off: remove the duplicate "Black Bull Liquor High St" store row.

Confirmed directly: "Black Bull Liquor Hawera" (57 High Street, Hawera
4610) and "Black Bull Liquor High St" (57 High St, Hawera South) are the
same physical store, entered twice — blackbullliquorhawera.co.nz's own
site states its address as "57 High Street, Hawera 4610", matching the
"Hawera" row exactly. Confirmed via anon-key read first that the
"High St" row has zero referencing products (so nothing needs repointing
before deleting it) — this script only deletes that one row, nothing else.

Delete this file after running once — it's a one-time fix, not a
recurring job.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-service-role-or-secret-key"
    python3 dedupe_blackbull_hawera_store.py
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
    "Content-Type": "application/json",
}

DUPLICATE_STORE_ID = "11128166-5f64-4880-b9f9-2c34ba41b494"  # "Black Bull Liquor High St"


def main():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/products?select=product_name&store_id=eq.{DUPLICATE_STORE_ID}&limit=1",
        headers=HEADERS, timeout=30,
    )
    r.raise_for_status()
    if r.json():
        raise SystemExit("Aborting — this store now has referencing products; repoint them before deleting.")

    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/stores?select=id,name,address&id=eq.{DUPLICATE_STORE_ID}",
        headers=HEADERS, timeout=15,
    )
    r.raise_for_status()
    stores = r.json()
    if not stores:
        print("No store found with that id — nothing to do.")
        return
    print(f"Deleting duplicate store: {stores[0]}")

    resp = requests.delete(
        f"{SUPABASE_URL}/rest/v1/stores?id=eq.{DUPLICATE_STORE_ID}",
        headers={**HEADERS, "Prefer": "return=minimal"},
        timeout=15,
    )
    if resp.status_code in (200, 204):
        print("Deleted.")
    else:
        print(f"FAILED: {resp.status_code} {resp.text}")


if __name__ == "__main__":
    main()
