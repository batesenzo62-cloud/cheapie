"""
Cheapie — Bottle-O store list refresh.

Refreshes bottleo_stores.json (the store list scrape_bottleo_products.py
reads) and the `stores` table in Supabase. Run this occasionally (branches
don't open/close often) — not on the same frequent schedule as the product
scraper, since it re-geocodes anything new via Nominatim's rate-limited
free API (1 request/second) and there's no reason to hit that repeatedly
for data that barely changes.

Pipeline:
  1. Parse the full store list from Bottle-O's own store-chooser page
     (shop.thebottleo.co.nz) — name, internal store id, address, and
     whether the branch has its own online shop ("Shop Now") or not
     ("Store Info" only, so no product data exists for it anywhere).
  2. For online-enabled branches only, resolve the real subdomain by
     following the "Shop Now" redirect once (a couple of branches land on
     a raw *.myfoodlink.com domain instead of the branded subdomain — both
     forms are handled the same way downstream).
  3. Geocode any address not already in bottleo_stores.json (safe to
     re-run: existing stores keep their previous coordinates and Supabase
     id rather than being re-geocoded and re-inserted every time).
  4. Upsert into Supabase's `stores` table and rewrite bottleo_stores.json.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-service-role-or-secret-key"
    python3 scrape_bottleo_stores.py
"""
import os, re, json, time, uuid, html as html_module
from urllib.parse import unquote
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}
GEOCODE_HEADERS = {"User-Agent": "CheapieApp/1.0 (research)"}
STORES_JSON = "bottleo_stores.json"


def parse_store_list():
    r = requests.get("https://shop.thebottleo.co.nz/", headers=HEADERS, timeout=30)
    r.raise_for_status()
    content = r.text
    blocks = content.split('class="StoreCard StoreCard--WithStoreAttributes"')[1:]
    stores = []
    for block in blocks:
        name_m = re.search(r'class="StoreCard__Name">([^<]+)<', block)
        addr_m = re.search(r'maps\.google\.com\?q=([^"#]+)', block)
        id_m = re.search(r'href="/([a-f0-9]{24})/i_choose_you"', block)
        cta_m = re.search(r'href="/[a-f0-9]{24}/i_choose_you"[^>]*>(.*?)</a>', block, re.S)
        online = False
        if cta_m:
            cta_text = re.sub(r'<[^>]+>', '', cta_m.group(1)).strip()
            online = 'Shop Now' in cta_text
        if name_m and id_m:
            addr = unquote(addr_m.group(1)).replace('+', ' ') if addr_m else None
            stores.append({
                'name': name_m.group(1).strip(),
                'store_id_ext': id_m.group(1),
                'address': addr,
                'online': online,
            })
    return stores


def resolve_subdomain(store_id_ext):
    r = requests.get(f"https://shop.thebottleo.co.nz/{store_id_ext}/i_choose_you",
                      headers=HEADERS, timeout=15, allow_redirects=True)
    final_url = r.url
    return final_url.split("://")[1].split(".shop.thebottleo.co.nz")[0]


def geocode(addr):
    r = requests.get("https://nominatim.openstreetmap.org/search",
                      params={"q": addr + ", New Zealand", "format": "json", "limit": 1},
                      headers=GEOCODE_HEADERS, timeout=15)
    data = r.json()
    return (float(data[0]['lat']), float(data[0]['lon'])) if data else None


def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY environment variables first.")

    try:
        with open(STORES_JSON) as f:
            known = {s["store_id_ext"]: s for s in json.load(f)}
    except FileNotFoundError:
        known = {}

    print("Fetching current Bottle-O store list...")
    current = parse_store_list()
    print(f"Found {len(current)} stores ({sum(1 for s in current if s['online'])} online)")

    updated = []
    new_count = 0
    for s in current:
        prior = known.get(s["store_id_ext"])
        entry = {
            "name": s["name"],
            "store_id_ext": s["store_id_ext"],
            "address": s["address"],
            "online": s["online"],
            "subdomain": prior.get("subdomain") if prior else None,
            "lat": prior.get("lat") if prior else None,
            "lng": prior.get("lng") if prior else None,
            "store_id": prior.get("store_id") if prior else str(uuid.uuid4()),
        }

        if s["online"] and not entry["subdomain"]:
            try:
                entry["subdomain"] = resolve_subdomain(s["store_id_ext"])
                print(f"  resolved subdomain for {s['name']}: {entry['subdomain']}")
            except Exception as e:
                print(f"  could not resolve subdomain for {s['name']}: {e}")
            time.sleep(0.5)

        if entry["lat"] is None:
            result = geocode(entry["address"])
            if result:
                entry["lat"], entry["lng"] = result
                print(f"  geocoded {s['name']}: {result}")
            else:
                print(f"  could not geocode {s['name']} ('{entry['address']}') — skipping map placement")
            time.sleep(1.1)

        if not prior:
            new_count += 1
        updated.append(entry)

    print(f"\n{new_count} new stores since last run.")

    with open(STORES_JSON, "w") as f:
        json.dump(updated, f, indent=2)
    print(f"Wrote {STORES_JSON}")

    # Upsert into Supabase — on_conflict on id means existing stores get
    # refreshed in place (e.g. a corrected address) rather than duplicated,
    # and genuinely new stores get inserted.
    rows = [
        {
            "id": s["store_id"],
            "name": f"Bottle-O {s['name']}",
            "address": s["address"],
            "latitude": s["lat"],
            "longitude": s["lng"],
            "region": None,
        }
        for s in updated if s["lat"] is not None
    ]
    resp = requests.post(
        f"{supabase_url}/rest/v1/stores?on_conflict=id",
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        json=rows,
        timeout=60,
    )
    if resp.status_code not in (200, 201):
        raise SystemExit(f"Store upsert failed (status {resp.status_code}): {resp.text}")
    print(f"Upserted {len(rows)} Bottle-O stores to Supabase.")


if __name__ == "__main__":
    main()
