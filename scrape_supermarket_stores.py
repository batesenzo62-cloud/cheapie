"""
Cheapie — New World / PAK'nSAVE store locations.

Both are Foodstuffs brands running the same Next.js site template. Their
main shop/category pages are behind Cloudflare (confirmed: 403, same as
Woolworths' Akamai block) — but their store-finder and individual store
pages are plain server-rendered HTML with a full __NEXT_DATA__ JSON blob
embedded, no blocking at all. That blob includes exact real coordinates
per store (no external geocoding needed, unlike the Bottle-O store list).

Woolworths has no equivalent: confirmed directly its store-locator page is
a client-side Angular shell with zero server-rendered store data, and its
whole site (not just /shop/) blocks headless browser automation at the
protocol level even with stealth patching — there's currently no free way
to get real Woolworths branch locations at all.

Since the actual shop/pricing pages remain blocked for both New World and
PAK'nSAVE, these branches will show the existing generic national
catalogue (Firecrawl-scraped, in chain_store_prices.csv) with the
standard "not confirmed for this specific store" disclaimer when clicked
— same honest pattern already used for Liquorland/Big Barrel. PAK'nSAVE
currently has zero rows in that generic catalogue at all (never
successfully scraped), so PAK'nSAVE branches will show "no products
found" until that's fixed separately.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-service-role-or-secret-key"
    python3 scrape_supermarket_stores.py
"""
import os, re, json, time, uuid
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}
STORES_JSON = "supermarket_stores.json"


def extract_next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        return None
    return json.loads(m.group(1))


def get_new_world_store_urls():
    r = requests.get("https://www.newworld.co.nz/store-finder", headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = extract_next_data(r.text)
    sf = data["props"]["pageProps"]["page"]["page_content"]["content_blocks"][1]["store_finder"]["regionStoreGroupings"]
    urls = []
    for island in ("northIsland", "southIsland"):
        for region in sf.get(island, []):
            for store in region["stores"]:
                urls.append("https://www.newworld.co.nz" + store["url"])
    return urls


def get_paknsave_store_urls():
    r = requests.get("https://www.paknsave.co.nz/store-finder", headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = extract_next_data(r.text)
    stores = data["props"]["pageProps"]["contentstackStores"]
    return ["https://www.paknsave.co.nz" + s["url"] for s in stores]


def get_store_details(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    data = extract_next_data(r.text)
    page = data["props"]["pageProps"]["page"]
    contact = page.get("contact_details") or {}
    if "latitude" not in contact or "longitude" not in contact:
        return None
    return {
        "name": page.get("title"),
        "address": contact.get("address"),
        "lat": contact["latitude"],
        "lng": contact["longitude"],
    }


def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY environment variables first.")

    try:
        with open(STORES_JSON) as f:
            known = {s["url"]: s for s in json.load(f)}
    except FileNotFoundError:
        known = {}

    print("Fetching New World store list...")
    nw_urls = get_new_world_store_urls()
    print(f"  {len(nw_urls)} New World stores")

    print("Fetching PAK'nSAVE store list...")
    pns_urls = get_paknsave_store_urls()
    print(f"  {len(pns_urls)} PAK'nSAVE stores")

    all_urls = nw_urls + pns_urls
    results = []
    for i, url in enumerate(all_urls):
        if url in known:
            results.append(known[url])
            continue
        try:
            details = get_store_details(url)
        except Exception as e:
            details = None
            print(f"  [{i+1}/{len(all_urls)}] {url} -> ERROR: {e}")
        if details and details["name"] and details["address"]:
            entry = {**details, "url": url, "store_id": str(uuid.uuid4())}
            results.append(entry)
            print(f"  [{i+1}/{len(all_urls)}] {entry['name']}")
        else:
            print(f"  [{i+1}/{len(all_urls)}] {url} -> incomplete data, skipped")
        time.sleep(0.5)

    with open(STORES_JSON, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {len(results)} stores to {STORES_JSON}")

    rows = [
        {
            "id": s["store_id"],
            "name": s["name"],
            "address": s["address"],
            "latitude": s["lat"],
            "longitude": s["lng"],
            "region": None,
        }
        for s in results
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
    print(f"Upserted {len(rows)} supermarket stores to Supabase.")


if __name__ == "__main__":
    main()
