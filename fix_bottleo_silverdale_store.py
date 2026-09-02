"""
Cheapie — one-off fix for Bottle-O Silverdale, missing from `stores`.

Reported directly: today's scheduled load aborted entirely partway
through (63,000 of 94,706 rows) with a foreign-key violation — a row
referenced store_id 4cc027c0-8a7d-4f04-8a43-20780f4f696e (Bottle-O
Silverdale, per bottleo_stores.json), which was never actually a real
row in the stores table. Root cause: bottleo_stores.json already had
lat/lng as null for this entry — its address ("1F Polarity Rise,
Stanmore Bay, Silverdale, Auckland 0932, New Zealand") doesn't geocode
via Nominatim at all (confirmed directly, empty result), so whatever
process assigned it a store_id never actually inserted the row.
Suburb-level "Silverdale, Auckland" does geocode — same precision
already accepted elsewhere in this app when a precise street address
isn't available (e.g. several Big Barrel branches).

load_data_to_supabase.py was also fixed separately (drops any row whose
store_id doesn't match a real stores row, instead of aborting the whole
batch) so a future case like this can't repeat this failure — this
script just gives Silverdale a real row so its rows stop being dropped
at all.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-service-role-or-secret-key"
    python3 fix_bottleo_silverdale_store.py
"""
import os
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY environment variables first.")

NEW_STORE = {
    "id": "4cc027c0-8a7d-4f04-8a43-20780f4f696e",
    "name": "Bottle-O Silverdale",
    "address": "1F Polarity Rise, Stanmore Bay, Silverdale, Auckland 0932, New Zealand",
    "latitude": -36.6176801,
    "longitude": 174.6769045,
    "region": "Auckland",
}


def main():
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/stores?on_conflict=id",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
        json=[NEW_STORE],
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise SystemExit(f"Insert failed (status {resp.status_code}): {resp.text}")
    inserted = resp.json()
    print(f"Inserted/updated {len(inserted)} store(s):")
    for s in inserted:
        print(f"  {s['id']}  {s['name']}")


if __name__ == "__main__":
    main()
