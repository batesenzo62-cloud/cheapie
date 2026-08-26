"""
Cheapie — one-off fix for Big Barrel branches missing from `stores` entirely.

Reported directly: clicking the Big Barrel pin in Havelock North showed
generic national-catalogue prices even though the branch has its own real
website (havelock.bigbarrel.co.nz). Investigating that led to a much
bigger finding — Big Barrel runs a subdomain-per-branch site (same shape
as Bottle-O), confirmed live for 47 of its ~53 listed branches, but the
`stores` table only had 34 Big Barrel rows to begin with. These 16
branches have a real, scrapeable subdomain shop and simply never had a
row here at all (no pin on the map, nothing for scrape_bigbarrel_branches.py
to attach product rows to).

Real coordinates geocoded via Nominatim (same approach as
scrape_bottleo_stores.py / fix_thirsty_branch_stores.py) from each
branch's own suburb/street, read from its own site's <meta description>
tag (bigbarrel.co.nz's own corporate "all shops" listing page and branch
info pages don't expose street addresses in static HTML, only branch
names). Several results are suburb-level rather than a precise street
address — real house-number-level OSM data didn't exist for every one of
these; suburb-level is still far more accurate than the previous "no pin
at all" state, and consistent with the precision already accepted
elsewhere in this app for stores geocoded this way.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-service-role-or-secret-key"
    python3 add_bigbarrel_stores.py
"""
import os
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY environment variables first.")

NEW_STORES = [
    {"id": "9c26ede4-d3c2-4662-b6fe-49e3cb2e0cb8", "name": "Big Barrel Taita, Lower Hutt",
     "address": "Taita, Lower Hutt, New Zealand", "latitude": -41.1848423, "longitude": 174.9564147,
     "region": "Wellington"},
    {"id": "fcc1cea0-6110-4700-82b8-7be6e96a8b3a", "name": "Big Barrel Cloverlea, Palmerston North",
     "address": "Cloverlea, Palmerston North, New Zealand", "latitude": -40.3449611, "longitude": 175.5870035,
     "region": "Manawatu-Whanganui"},
    {"id": "6740436a-c4ae-4491-9994-3fd1c4905d37", "name": "Big Barrel Concord, Dunedin",
     "address": "12C Main South Road, Lookout Point, Concord, Dunedin, New Zealand", "latitude": -45.9021144, "longitude": 170.4571603,
     "region": "Otago"},
    {"id": "d6d8c984-0203-4422-a206-1cd334e971d4", "name": "Big Barrel Highbury, Palmerston North",
     "address": "Highbury Avenue, Highbury, Palmerston North, New Zealand", "latitude": -40.3599999, "longitude": 175.5864979,
     "region": "Manawatu-Whanganui"},
    {"id": "2bcd7c8c-387a-4dd1-b4ff-802abbae3ac3", "name": "Big Barrel Masterton, Wairarapa",
     "address": "Masterton, Wairarapa, New Zealand", "latitude": -40.9495524, "longitude": 175.6594413,
     "region": "Wellington"},
    {"id": "e4dedae6-6944-45c6-8525-a7f92573e252", "name": "Big Barrel New Plymouth",
     "address": "King Street, Westown, New Plymouth, New Zealand", "latitude": -39.0574167, "longitude": 174.0704357,
     "region": "Taranaki"},
    {"id": "70067443-a832-48a7-a454-446ec9382a92", "name": "Big Barrel Otaki, Kapiti Coast",
     "address": "Otaki, Kapiti Coast, New Zealand", "latitude": -40.7585374, "longitude": 175.1470152,
     "region": "Wellington"},
    {"id": "1c98b096-207d-43f3-a4aa-eba2b629c3f3", "name": "Big Barrel Remarkables, Queenstown",
     "address": "Hawthorne Drive, Remarkables Park, Frankton, Queenstown, New Zealand", "latitude": -45.0256885, "longitude": 168.7428336,
     "region": "Otago"},
    {"id": "cd677122-1822-4854-9f7c-4676ac5f8149", "name": "Big Barrel Riverside, Whanganui",
     "address": "Riverside, Whanganui, New Zealand", "latitude": -39.9324904, "longitude": 175.0519306,
     "region": "Manawatu-Whanganui"},
    {"id": "2e63543b-d2d3-43b2-8c13-edf86a30e443", "name": "Big Barrel Stortford Lodge, Hastings",
     "address": "Stortford Lodge, Frimley, Hastings, New Zealand", "latitude": -39.6300894, "longitude": 176.8305360,
     "region": "Hawke's Bay"},
    {"id": "21bba0f0-1e79-4cd9-9cb2-29a08675e608", "name": "Big Barrel Tremaine, Palmerston North",
     "address": "Tremaine Avenue, Palmerston North, New Zealand", "latitude": -40.3354428, "longitude": 175.6192923,
     "region": "Manawatu-Whanganui"},
    {"id": "a63237b3-0e92-445a-8fff-7d3c1346f74b", "name": "Big Barrel Waitangirua, Porirua",
     "address": "Niagara Street, Waitangirua, Porirua, New Zealand", "latitude": -41.1294110, "longitude": 174.8794242,
     "region": "Wellington"},
    {"id": "bac0d412-3327-41f2-ba9e-ae5b94a472bc", "name": "Big Barrel Whanganui East",
     "address": "Whanganui East, Whanganui, New Zealand", "latitude": -39.9177958, "longitude": 175.0604386,
     "region": "Manawatu-Whanganui"},
    {"id": "9a85bb56-c227-4363-9aa0-69f41244ba4f", "name": "Big Barrel Devon Rd, New Plymouth",
     "address": "Devon Road, Fitzroy, New Plymouth, New Zealand", "latitude": -39.0514805, "longitude": 174.1084193,
     "region": "Taranaki"},
    {"id": "4c670fc2-0ee9-431d-9db6-d72a2ab39624", "name": "Big Barrel Kent Terrace, Wellington",
     "address": "Kent Terrace, Mount Victoria, Wellington, New Zealand", "latitude": -41.2935140, "longitude": 174.7843131,
     "region": "Wellington"},
    {"id": "37bfc8e1-16f0-4525-a4fc-f7036e0300ff", "name": "Big Barrel Kaikorai Valley, Dunedin",
     "address": "Kaikorai Valley, Dunedin, New Zealand", "latitude": -45.9020121, "longitude": 170.4460455,
     "region": "Otago"},
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
