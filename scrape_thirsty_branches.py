"""
Cheapie — Thirsty Liquor per-branch scraper.

Covers every confirmed Thirsty Liquor branch subdomain found via the site's
store locator. Tauranga and Te Rapa are known incomplete: their
/collections/beer etc. URLs don't match this chain's usual pattern (custom
slugs — confirmed 404/redirect, not yet fixed), so they'll legitimately
scrape 0 rows each run until someone finds their real collection URLs.
Left in rather than silently dropped, per this project's "flag rather than
skip" convention.

Designed to be safe to re-run on a schedule: replaces this run's branches'
rows in independent_store_prices.csv rather than appending duplicates on
top of the previous run's.

HOW TO RUN:
    python3 scrape_thirsty_branches.py
"""
import csv, time, requests
import scrape_independent_stores as s

SUPABASE_URL = "https://gkkchssgamqfavomcnoq.supabase.co"
SUPABASE_KEY = "sb_publishable_0D5UFWvifa2lI9o5lPbK8Q_iOsnLW8b"

r = requests.get(f"{SUPABASE_URL}/rest/v1/stores?select=id,name&name=ilike.*Thirsty*",
                  headers={"apikey": SUPABASE_KEY})
stores = r.json()


def match_store_id(label):
    matches = [st for st in stores if label.lower() in st["name"].lower()]
    return matches[0]["id"] if matches else None


BRANCHES = {
    "Whangaparaoa": ("https://thirstyliquorwhangaparaoa.co.nz", None),
    "Mt Eden": ("https://thirstyliquormteden.co.nz", None),
    "Franich Street": ("https://thirstyliquorfranichst.co.nz", None),
    "Chapel Park": ("https://thirstyliquorchapelpark.co.nz", None),
    "Pukekohe": ("https://thirstyliquorpukekohe.co.nz", None),
    "Havelock North": ("https://thirstyliquorhavelocknorth.co.nz", None),
    "Levin": ("https://thirstyliquorlevin.co.nz", None),
    "Dunedin": ("https://thirstyliquordunedin.co.nz", None),
    "Islington": ("https://thirstyliquorislington.co.nz", None),
    "Huntsbury": ("https://thirstyliquorhuntsbury.co.nz", None),
    "Tauranga": ("https://www.thirstyliquortauranga.co.nz", None),
    "Te Rapa": ("https://tlterapa.co.nz", "377320fd-3b7c-424d-9ce0-b46f7c7893b9"),
}
CATEGORIES = {"beer": "collections/beer", "rtd": "collections/rtds", "wine": "collections/wine", "spirits": "collections/spirits"}


def main():
    new_rows = []
    for label, (base, fixed_store_id) in BRANCHES.items():
        store_id = fixed_store_id or match_store_id(label)
        store_name = f"Thirsty Liquor {label}"
        print(f"Scraping {store_name} (store_id={'matched' if store_id else 'unmatched'})...")
        for cat, path in CATEGORIES.items():
            try:
                products = s.scrape_shopify(f"{base}/{path}")
                for p in products:
                    new_rows.append({
                        "store": store_name,
                        "store_id": store_id or "",
                        "category": cat,
                        "product_name": p["name"],
                        "price": p["price"],
                        "was_price": p["was_price"],
                        "in_stock": p["in_stock"],
                        "url": p["url"],
                        "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
                    })
            except Exception as e:
                print(f"  {cat} error: {e}")
            time.sleep(1)
        time.sleep(1)

    print(f"\nTotal new branch-specific rows: {len(new_rows)}")

    scraped_store_names = {f"Thirsty Liquor {label}" for label in BRANCHES}
    with open("independent_store_prices.csv") as f:
        existing = list(csv.DictReader(f))

    fieldnames = list(s.PRODUCT_FIELDNAMES) + ["store_id"]
    for row in existing:
        row.setdefault("store_id", "")

    # Drop this run's branches' old rows before appending fresh ones — a
    # scheduled re-run must replace, not pile duplicates on top of, the
    # previous run's data for the same branches. Every other store's rows
    # (the generic "Thirsty Liquor" fallback, other chains, everything
    # else) are untouched.
    kept = [row for row in existing if row["store"] not in scraped_store_names]
    all_rows = kept + new_rows
    with open("independent_store_prices.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Wrote {len(all_rows)} total rows ({len(new_rows)} fresh branch-specific Thirsty Liquor rows)")


if __name__ == "__main__":
    main()
