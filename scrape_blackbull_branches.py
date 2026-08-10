"""
Cheapie — Black Bull Liquor per-branch scraper.

Covers the 4 confirmed independently-run Black Bull-branded Shopify sites.
No central store locator exists for this "chain" (each branch is
independently operated under the shared brand name), so this list is
manually maintained rather than discovered from a locator API.

Designed to be safe to re-run on a schedule: replaces these 4 branches'
rows in independent_store_prices.csv rather than appending duplicates on
top of the previous run's.

HOW TO RUN:
    python3 scrape_blackbull_branches.py
"""
import csv, time
import scrape_independent_stores as s

BRANCHES = {
    "Greenwood": ("https://blackbullliquorgreenwood.co.nz", "5aaeedcc-78f6-4d0c-b71f-7c6416222479",
                  {"beer": "beer", "wine": "wine", "spirits": "spirits", "rtd": "rtds"}),
    "Thames": ("https://blackbullliquorthames.co.nz", "e80a34a2-5935-48ce-a2aa-2509c3bb3f5e",
               {"beer": "beer", "wine": "wine", "spirits": "spirits", "rtd": "rtds"}),
    "Porirua": ("https://blackbullporirua.co.nz", "4a753608-aba4-4183-870b-08d9d2a20a1e",
                {"beer": "beer-cider", "wine": "wine", "spirits": "spirits", "rtd": "rtd"}),
    "Hornby": ("https://blackbullliquorhornbyhub.co.nz", "0e3daec4-a8ec-44dd-a049-3a8b2efa7477",
               {"beer": "beer-cider", "wine": "wine", "spirits": "spirits", "rtd": "rtds"}),
}


def main():
    new_rows = []
    for label, (base, store_id, cats) in BRANCHES.items():
        store_name = f"Black Bull Liquor {label}"
        print(f"Scraping {store_name}...")
        for cat, path in cats.items():
            try:
                products = s.scrape_shopify(f"{base}/collections/{path}")
                for p in products:
                    new_rows.append({
                        "store": store_name, "store_id": store_id, "category": cat,
                        "product_name": p["name"], "price": p["price"], "was_price": p["was_price"],
                        "in_stock": p["in_stock"], "url": p["url"], "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
                    })
            except Exception as e:
                print(f"  {cat} error: {e}")
            time.sleep(1)
        time.sleep(1)

    print(f"\nTotal fresh rows: {len(new_rows)}")

    scraped_store_names = {f"Black Bull Liquor {label}" for label in BRANCHES}
    with open("independent_store_prices.csv") as f:
        fieldnames = next(csv.reader(f))
    existing = list(csv.DictReader(open("independent_store_prices.csv")))
    kept = [row for row in existing if row["store"] not in scraped_store_names]

    all_rows = kept + new_rows
    with open("independent_store_prices.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Wrote {len(all_rows)} total rows ({len(new_rows)} fresh Black Bull rows)")


if __name__ == "__main__":
    main()
