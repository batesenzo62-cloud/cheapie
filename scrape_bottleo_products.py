"""
Cheapie — Bottle-O per-branch product scraper.

Bottle-O runs on a white-label platform (MyFoodLink) with a subdomain per
branch (albany.shop.thebottleo.co.nz, etc. — a couple of branches resolve
to a different base domain, *.myfoodlink.com, handled the same way since
the subdomain string in bottleo_stores.json already contains the full
host). Prices/category listings are server-rendered on plain GET requests
to /search?q[]=category:{id}&page=N — no JS/Playwright/Firecrawl needed.
Confirmed pagination end: a page with fewer than 48 items has no further
page link and is genuinely the last page.

Category IDs are per-store, not shared across the chain (confirmed:
Albany's "Beer" id 404'd on every other store tried) — each store embeds a
link to its own sidebar/{store_id}/{version}.json on its homepage; that
JSON's department list uses the same slugs (beer, wine, spirits, rtd,
port-1, cider) everywhere even though the ids differ, so each store's own
ids are resolved from its own homepage first, every run.

The store list itself (name, subdomain, coordinates, real Supabase
store_id) lives in bottleo_stores.json, committed alongside this script —
that data changes rarely (branches don't relocate often) and refreshing it
means re-geocoding everything, so it's kept out of this frequent-refresh
script. Re-run scrape_bottleo_stores.py separately, occasionally, if
Bottle-O opens/closes locations.

One store (picked for having a large, representative catalogue) is also
written under the plain "Bottle-O" name with no store_id — the fallback
catalogue shown (with an honest "not confirmed for this specific store"
disclaimer) for the ~80 Bottle-O locations that don't have their own
online shop at all.

Departments map to this app's 4-category taxonomy: Cider -> beer, Port ->
wine (same reasoning as Liquorland's craft-beer/cider -> beer, liqueurs ->
spirits mapping). Confectionery, Non Alcoholic, and Gifts departments are
deliberately excluded — not real liquor products this app compares.

HOW TO RUN:
    python3 scrape_bottleo_products.py
"""
import requests, re, time, csv, json, os

DEFAULT_FIELDNAMES = ["store", "category", "product_name", "price", "was_price", "in_stock", "url", "fetched_at", "store_id"]

HEADERS = {"User-Agent": "Mozilla/5.0"}

WANTED_SLUGS = {
    "beer": "beer",
    "wine": "wine",
    "spirits": "spirits",
    "rtd": "rtd",
    "port-1": "wine",
    "cider": "beer",
}

# Representative store used as the generic fallback catalogue for branches
# with no online shop of their own — picked once for having one of the
# largest, most complete catalogues among the online-enabled branches.
FALLBACK_STORE_NAME = "Bottle-O Kingsland"


def base_url(subdomain):
    if subdomain.endswith("/"):
        subdomain = subdomain.rstrip("/")
    if "myfoodlink.com" in subdomain:
        return f"https://{subdomain}"
    return f"https://{subdomain}.shop.thebottleo.co.nz"


def get_departments(base):
    try:
        r = requests.get(base + "/", headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"    could not load homepage: {e}")
        return {}
    m = re.search(r'(dtgxwmigmg3gc\.cloudfront\.net/sidebar/[a-zA-Z0-9/_.-]+\.json[^"\']*)', r.text)
    if not m:
        print("    no sidebar JSON link found on homepage")
        return {}
    sidebar_url = "https://" + m.group(1).replace("&amp;", "&")
    try:
        r2 = requests.get(sidebar_url, headers=HEADERS, timeout=20)
        r2.raise_for_status()
        data = r2.json()
    except Exception as e:
        print(f"    could not load sidebar JSON: {e}")
        return {}
    result = {}
    for d in data.get("departments", []):
        if d.get("slug") in WANTED_SLUGS and d["slug"] not in result:
            result[d["slug"]] = d["id"]
    return result


def parse_page(html):
    products = []
    for m in re.finditer(
        r'talker__product-name">([^<]+)</span>\s*'
        r'(?:<span class="weak size talker__name__size">([^<]*)</span>)?.*?'
        r'price__sell"[^>]*>\$([\d.]+)<',
        html, re.S
    ):
        name, size, price = m.groups()
        full_name = f"{name.strip()} {size.strip()}" if size else name.strip()
        products.append({"name": full_name, "price": price})
    return products


def scrape_department(base, dept_id):
    all_products = []
    page = 1
    while True:
        url = f"{base}/search?page={page}&q%5B%5D=category%3A{dept_id}" if page > 1 else f"{base}/search?q%5B%5D=category%3A{dept_id}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
        except Exception as e:
            print(f"    page {page} error: {e}")
            break
        products = parse_page(r.text)
        all_products += products
        if len(products) < 48:
            break
        page += 1
        time.sleep(0.4)
    return all_products


def scrape_store(store):
    base = base_url(store["subdomain"])
    store_name = f"Bottle-O {store['name']}"
    print(f"Scraping {store_name} ({base})...")

    depts = get_departments(base)
    if not depts:
        print("  skipping — could not resolve departments")
        return []
    print(f"  resolved {len(depts)} departments: {list(depts.keys())}")

    rows = []
    seen_names = set()
    for slug, app_category in WANTED_SLUGS.items():
        dept_id = depts.get(slug)
        if not dept_id:
            continue
        products = scrape_department(base, dept_id)
        for p in products:
            if p["name"] in seen_names:
                continue
            seen_names.add(p["name"])
            rows.append({
                "store": store_name,
                "category": app_category,
                "product_name": p["name"],
                "price": p["price"],
                "was_price": "",
                "in_stock": True,
                "url": "",
                "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
                "store_id": store["store_id"],
            })
        time.sleep(0.3)
    print(f"  {len(rows)} products")
    return rows


def main():
    with open("bottleo_stores.json") as f:
        stores = json.load(f)
    online_stores = [s for s in stores if s.get("online") and s.get("subdomain")]
    print(f"{len(online_stores)} online Bottle-O stores to scrape")

    all_new_rows = []
    for i, store in enumerate(online_stores):
        print(f"[{i + 1}/{len(online_stores)}]", end=" ")
        all_new_rows += scrape_store(store)
        time.sleep(0.5)

    fallback_rows = [dict(r, store="Bottle-O", store_id="") for r in all_new_rows if r["store"] == FALLBACK_STORE_NAME]
    all_new_rows += fallback_rows
    print(f"\nTotal fresh Bottle-O rows (incl. {len(fallback_rows)} generic fallback rows): {len(all_new_rows)}")

    # 2026-08-14 fix: this file is gitignored (regenerated data, not
    # source) — confirmed directly a plain open() here crashed every
    # scheduled GitHub Actions run so far, since a fresh CI checkout never
    # has it. Treated as "no existing rows to preserve" rather than an
    # error — this run's own fresh rows still get written either way.
    scraped_store_names = {f"Bottle-O {s['name']}" for s in online_stores} | {"Bottle-O"}
    if os.path.exists("independent_store_prices.csv"):
        with open("independent_store_prices.csv", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            kept = [row for row in reader if row["store"] not in scraped_store_names]
    else:
        fieldnames = DEFAULT_FIELDNAMES
        kept = []

    for row in all_new_rows:
        kept.append({k: row.get(k, "") for k in fieldnames})

    with open("independent_store_prices.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)
    print(f"Wrote {len(kept)} total rows to independent_store_prices.csv")


if __name__ == "__main__":
    main()
