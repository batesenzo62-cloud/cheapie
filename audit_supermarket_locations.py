"""
Cheapie — audit New World store coordinates against OpenStreetMap.

Reported directly: "New World Havelock North" showed on the map in its
old location. Confirmed the store's own site (which scrape_supermarket_
stores.py trusts as the coordinate source) reports a coordinate ~450m
from where OpenStreetMap has "New World" tagged as an actual supermarket
POI on Cooper Street -- the store's own database appears to still have a
stale coordinate from before it relocated, even though its own address
text and everything else about the listing is otherwise correct.

This can't be caught by re-scraping New World's own site again (it would
just report the same stale coordinate) -- needs an independent source.
OpenStreetMap's Overpass API is used here: a real, community-maintained,
POI-tagged (shop=supermarket) location, not just an address geocode.

Woolworths isn't covered -- there's currently no Woolworths location data
in the stores table at all to audit (never successfully scraped, see
scrape_supermarket_stores.py's own docstring).

Matching logic: for each New World store already in the stores table,
find the nearest real OSM "New World" supermarket POI. If it's within
MAX_TRUSTED_DISTANCE_KM, that's almost certainly the same physical store
(New World doesn't have multiple branches within a few hundred metres of
each other) -- if the OSM coordinate differs from what's currently stored
by more than FLAG_DISTANCE_KM, it's corrected. Anything with no
sufficiently-close OSM match at all is left untouched and reported, not
guessed at.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-service-role-or-secret-key"
    python3 audit_supermarket_locations.py
"""
import math
import os
import time

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

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_QUERY = """
[out:json][timeout:90];
area["ISO3166-1"="NZ"][admin_level=2]->.nz;
(
  node["shop"="supermarket"]["name"~"New World",i](area.nz);
  way["shop"="supermarket"]["name"~"New World",i](area.nz);
);
out center;
"""

# New World stores are never within a few hundred metres of each other —
# a real match within this radius is almost certainly the same store.
MAX_TRUSTED_DISTANCE_KM = 3.0
# Only correct when the discrepancy is large enough to matter for "which
# pin shows on the map" — not chasing GPS-noise-level differences.
FLAG_DISTANCE_KM = 0.15


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def fetch_osm_new_world():
    for attempt in (1, 2, 3):
        try:
            r = requests.post(OVERPASS_URL, data={"data": OVERPASS_QUERY}, timeout=90)
            r.raise_for_status()
            elements = r.json().get("elements", [])
            points = []
            for e in elements:
                lat = e.get("lat") or (e.get("center") or {}).get("lat")
                lon = e.get("lon") or (e.get("center") or {}).get("lon")
                name = (e.get("tags") or {}).get("name", "")
                if lat is not None and lon is not None:
                    points.append((lat, lon, name))
            return points
        except Exception as e:
            print(f"  Overpass attempt {attempt} failed: {e}")
            time.sleep(5)
    return []


def main():
    print("Fetching New World stores from Supabase...")
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/stores?select=id,name,address,latitude,longitude&name=ilike.*New+World*",
        headers=HEADERS, timeout=30,
    )
    r.raise_for_status()
    stores = r.json()
    print(f"  {len(stores)} New World stores in the database")

    print("Fetching real New World locations from OpenStreetMap...")
    osm_points = fetch_osm_new_world()
    print(f"  {len(osm_points)} New World POIs found on OSM")
    if not osm_points:
        raise SystemExit("Could not fetch OSM data — aborting rather than comparing against nothing.")

    corrected, unchanged, unmatched = [], [], []
    for store in stores:
        lat, lng = store["latitude"], store["longitude"]
        best = min(osm_points, key=lambda p: haversine_km(lat, lng, p[0], p[1]))
        dist = haversine_km(lat, lng, best[0], best[1])
        if dist > MAX_TRUSTED_DISTANCE_KM:
            unmatched.append((store, dist))
            continue
        if dist > FLAG_DISTANCE_KM:
            print(f"  Correcting {store['name']}: {dist*1000:.0f}m off (was {lat:.5f},{lng:.5f} -> {best[0]:.5f},{best[1]:.5f})")
            resp = requests.patch(
                f"{SUPABASE_URL}/rest/v1/stores?id=eq.{store['id']}",
                headers={**HEADERS, "Prefer": "return=minimal"},
                json={"latitude": best[0], "longitude": best[1]},
                timeout=15,
            )
            if resp.status_code in (200, 204):
                corrected.append(store["name"])
            else:
                print(f"    FAILED to update: {resp.status_code} {resp.text}")
        else:
            unchanged.append(store["name"])

    print(f"\nDone. {len(corrected)} corrected, {len(unchanged)} already accurate, {len(unmatched)} no confident OSM match (left untouched):")
    for store, dist in unmatched:
        print(f"  {store['name']} — nearest OSM match {dist:.1f}km away, too far to trust")


if __name__ == "__main__":
    main()
