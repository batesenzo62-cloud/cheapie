"""
Cheapie — one-off fix for Thirsty Liquor branches missing from `stores`.

scrape_thirsty_branches.py resolves each BRANCHES entry to a store_id by
substring-matching the branch label against the `stores` table's `name`
column (match_store_id()). Confirmed directly this silently fails for
several real branches:

- Franich Street, Whangaparaoa: real stores exist in the table, but under
  generic "Thirsty Liquor Auckland" names with the distinguishing detail
  only in the address column, not the name — a name-only substring match
  can never find them.
- Mt Eden, Huntsbury, Tauranga: don't exist in the table at all.
- Dunedin: the table has two "Thirsty Liquor Dunedin" entries (Mosgiel,
  Concord), and match_store_id() picks matches[0] arbitrarily — but
  neither is the real address of thirstyliquordunedin.co.nz (111 George
  Street, Central Dunedin), so this branch's product rows were being
  geo-tagged to the wrong physical location entirely, not just missing.

Real addresses confirmed directly from each branch's own site footer;
coordinates geocoded via Nominatim (same approach as scrape_bottleo_stores.py).
This is a one-time data fix, not an ongoing scraper — after this runs,
scrape_thirsty_branches.py's BRANCHES dict should hardcode these store_ids
directly (same pattern already used for Te Rapa) instead of relying on
match_store_id() for these six branches.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-service-role-or-secret-key"
    python3 fix_thirsty_branch_stores.py
"""
import os
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY environment variables first.")

NEW_STORES = [
    {
        "id": "e85a574c-86ed-4dec-8044-77cdc4498416",
        "name": "Thirsty Liquor Mt Eden",
        "address": "30 Enfield Street, Mount Eden, Auckland 1024",
        "latitude": -36.8692291,
        "longitude": 174.7632141,
        "region": None,
    },
    {
        "id": "e93e8684-524c-40fd-8dc0-b85bdefa3e6a",
        "name": "Thirsty Liquor Huntsbury",
        "address": "1/69 Centaurus Road, Huntsbury, Christchurch 8022",
        "latitude": -43.5655989,
        "longitude": 172.6477956,
        "region": None,
    },
    {
        "id": "c9e54a08-aae5-4eeb-b8a5-2a6c3168fcee",
        "name": "Thirsty Liquor Tauranga",
        "address": "65 Chapel Street, Tauranga",
        "latitude": -37.6739521,
        "longitude": 176.1649147,
        "region": None,
    },
    {
        "id": "a8e86ef9-274b-43f2-9cbc-48c2e3d329ba",
        "name": "Thirsty Liquor Dunedin (George Street)",
        "address": "111 George Street, Central Dunedin, Dunedin 9016",
        "latitude": -45.8724944,
        "longitude": 170.5043179,
        "region": None,
    },
]


def main():
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/stores?on_conflict=id",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
        json=NEW_STORES,
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise SystemExit(f"Insert failed (status {resp.status_code}): {resp.text}")
    inserted = resp.json()
    print(f"Inserted/updated {len(inserted)} stores:")
    for s in inserted:
        print(f"  {s['id']}  {s['name']}")


if __name__ == "__main__":
    main()
