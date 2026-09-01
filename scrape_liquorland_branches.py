"""
Cheapie — Liquorland per-branch product scraper.

Reported directly, then verified live: Liquorland prices are NOT uniform
across stores, contradicting the assumption baked into
scrape_liquorland_full.py (STORE_ID = 4, "price confirmed identical
across stores when available"). Confirmed directly using the site's own
real "preferred store" mechanism (POST /api/stores/preferred, then
re-fetch) — the same barcode (850848, "Kirin Hyoketsu Lemon 10-Pack")
showed $31.99 at Parnell/Kamo/Andersons Bay but $33.99 at Glen Innes/
Williamson Ave/Kaikohe/Mosgiel/Cableways and $32.99 at Howick, with no
regional pattern (Auckland alone had both the cheap and expensive price).
Consistent with Liquorland actually being individually-owned franchise
stores (confirmed via WebSearch earlier) — the single generic "Liquorland"
national-catalogue scrape fanned out to every branch via
expandGenericChainMatches was frequently just wrong for whichever
branches didn't happen to match Parnell's price.

Fetches the real store list directly from Liquorland's own store-locations
page (window.stores = {...} embedded JSON — real storeid, label, code for
all 167 branches) and matches each to this app's `stores` table by exact
name — confirmed directly this is a clean 1:1 match for all 167, no
collision risk (unlike Thirsty Liquor/Big Barrel, which needed manual
hardcoding for ambiguous cases).

Reuses scrape_liquorland_full.py's CATEGORIES list and scrape_category()
(same 7 real categories, same page-JSON parsing) — just re-points the
module's SESSION at a fresh session per branch (switching preferred store
via the same site mechanism the real Click & Collect UI uses) instead of
running once against a single hardcoded store.

2026-08-31: timed one full branch (all 7 categories, Parnell) directly —
~6.8 minutes, 672 real pages fetched. For all 167 branches that's roughly
19 hours sequentially, so this needs the same CHUNK_INDEX/CHUNK_COUNT
chunking already used for Super Liquor/Big Barrel — sized generously here
(8 chunks) from the start, learning from Big Barrel's first unchunked run
hitting GitHub Actions' 6h ceiling.

HOW TO RUN:
    python3 scrape_liquorland_branches.py
    # or, chunked (see scrape-branches.yml's liquorland-branches matrix job):
    CHUNK_INDEX=0 CHUNK_COUNT=8 python3 scrape_liquorland_branches.py
"""
import csv, time, os, json
import requests
import scrape_liquorland_full as sl

SUPABASE_URL = "https://gkkchssgamqfavomcnoq.supabase.co"
SUPABASE_KEY = "sb_publishable_0D5UFWvifa2lI9o5lPbK8Q_iOsnLW8b"

CHUNK_INDEX = int(os.environ.get("CHUNK_INDEX", "0"))
CHUNK_COUNT = int(os.environ.get("CHUNK_COUNT", "1"))


def fetch_liquorland_stores():
    # window.stores = {...} — real storeid/label/code for every branch,
    # embedded directly in the store-locations page's HTML.
    r = requests.get("https://www.liquorland.co.nz/store-locations", headers=sl.HEADERS, timeout=20)
    text = r.text
    i = text.find("window.stores = ")
    start = text.find("{", i)
    depth = 0
    end = start
    for k in range(start, len(text)):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                end = k + 1
                break
    return json.loads(text[start:end])


def fetch_db_store_ids():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/stores",
        headers={"apikey": SUPABASE_KEY},
        params={"select": "id,name", "name": "ilike.*Liquorland*", "limit": "1000"},
        timeout=20,
    )
    return {s["name"]: s["id"] for s in r.json()}


def build_branch_list():
    ll_stores = fetch_liquorland_stores()
    db_by_name = fetch_db_store_ids()
    branches = []
    for s in ll_stores.values():
        label = s["label"]
        store_id = db_by_name.get(label)
        if store_id:
            branches.append((label, s["storeid"], store_id))
        else:
            print(f"  WARNING: no stores row matched for '{label}' — skipping")
    branches.sort()  # stable order so [start::step] chunking is deterministic across parallel jobs
    return branches


def set_preferred_store(storeid):
    # Fresh session per branch — matches exactly what was verified live
    # (each store tested with its own clean session), rather than assuming
    # a shared session correctly re-scopes on every preferred-store switch.
    sl.SESSION = requests.Session()
    sl.SESSION.headers.update(sl.HEADERS)
    sl.SESSION.get("https://www.liquorland.co.nz/")
    sl.SESSION.post(
        "https://www.liquorland.co.nz/api/stores/preferred",
        files={"storeid": (None, str(storeid))},
    )


def main():
    branches = build_branch_list()[CHUNK_INDEX::CHUNK_COUNT]
    print(f"Chunk {CHUNK_INDEX + 1}/{CHUNK_COUNT}: {len(branches)} Liquorland branches this run")

    new_rows = []
    for label, ll_storeid, store_id in branches:
        print(f"Scraping {label} (Liquorland store {ll_storeid})...")
        set_preferred_store(ll_storeid)
        branch_products = 0
        for site_slug, url, app_category in sl.CATEGORIES:
            try:
                rows = sl.scrape_category(site_slug, url, app_category)
                for row in rows:
                    row["store"] = label
                    row["store_id"] = store_id
                    del row["_barcode"]
                    new_rows.append(row)
                branch_products += len(rows)
            except Exception as e:
                print(f"  {site_slug} error: {e}")
            time.sleep(0.5)
        print(f"  {branch_products} products")

    print(f"\nTotal new branch-specific rows: {len(new_rows)}")

    # Same "gitignored CSV, fresh checkout has none" handling already used
    # by every other per-branch scraper in this project.
    scraped_labels = {label for label, _, _ in branches}
    if os.path.exists("independent_store_prices.csv"):
        with open("independent_store_prices.csv") as f:
            existing = list(csv.DictReader(f))
    else:
        existing = []

    fieldnames = ["store", "category", "product_name", "price", "was_price", "in_stock", "url", "fetched_at", "store_id"]
    for row in existing:
        row.setdefault("store_id", "")

    # Drop this run's branches' old rows before appending fresh ones. The
    # generic "Liquorland" national-catalogue rows (scrape_liquorland_full.py,
    # still used as the fallback for any branch that isn't matched above)
    # are untouched — different `store` value, never in scraped_labels.
    kept = [row for row in existing if row["store"] not in scraped_labels]
    all_rows_out = kept + [{k: r.get(k, "") for k in fieldnames} for r in new_rows]
    with open("independent_store_prices.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows_out)

    print(f"Wrote {len(all_rows_out)} total rows ({len(new_rows)} fresh branch-specific Liquorland rows)")


if __name__ == "__main__":
    main()
