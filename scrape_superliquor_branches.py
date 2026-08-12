"""
Cheapie — Super Liquor per-branch scraper.

Covers every branch listed on Super Liquor's own store locator API
(GetStoresByState) that resolves to a real subdomain — 26 are confirmed
genuinely closed (redirect to /storeclosed) and are skipped automatically
since they simply won't have a Value/base URL worth trying.

Designed to be safe to re-run on a schedule: replaces all "Super Liquor *"
rows in independent_store_prices.csv with this run's fresh results, rather
than the interruption-resume logic used for the original one-off scrape
(that logic tracked already-written (store, category) pairs and *skipped*
them — correct for resuming after a crash mid-run, but would silently
skip every branch forever on any later scheduled re-run, since the rows
from the previous run are always already there).

HOW TO RUN:
    python3 scrape_superliquor_branches.py
"""
import csv, time, requests, os
import scrape_independent_stores as s

SUPABASE_URL = "https://gkkchssgamqfavomcnoq.supabase.co"
SUPABASE_KEY = "sb_publishable_0D5UFWvifa2lI9o5lPbK8Q_iOsnLW8b"
CSV_PATH = "independent_store_prices.csv"
CATEGORIES = {"beer": "beer", "rtd": "premix", "wine": "wine", "spirits": "spirits"}
DEFAULT_FIELDNAMES = ["store", "store_id", "category", "product_name", "price", "was_price", "in_stock", "url", "fetched_at"]

# 2026-08-13 fix: confirmed directly — a single run covering all 147
# online branches got killed at exactly 6h00m by GitHub Actions' hard job
# time limit for hosted runners (timeout-minutes can be set higher, but
# can't actually raise that platform ceiling — it's silently capped, not
# honoured). Split into CHUNK_COUNT parallel jobs (see
# .github/workflows/scrape-branches.yml), each running its own slice of
# the branch list via CHUNK_INDEX — [start::step] slicing interleaves
# branches across chunks rather than splitting into contiguous blocks, so
# no single chunk is skewed if branch catalogue depth varies regionally.
# Defaults to "no chunking" for a plain manual/local run.
CHUNK_INDEX = int(os.environ.get("CHUNK_INDEX", "0"))
CHUNK_COUNT = int(os.environ.get("CHUNK_COUNT", "1"))


def match_store_id(stores, label):
    matches = [st for st in stores if label.lower() in st["name"].lower()]
    return matches[0]["id"] if matches else None


def main():
    r = requests.get(f"{SUPABASE_URL}/rest/v1/stores?select=id,name&name=ilike.*Super+Liquor*",
                      headers={"apikey": SUPABASE_KEY})
    stores = r.json()

    r2 = requests.get("https://www.superliquor.co.nz/GetStoresByState", headers=s.HEADERS)
    branch_data = [b for b in r2.json()["stores"] if b["Value"]]
    branch_data = branch_data[CHUNK_INDEX::CHUNK_COUNT]
    print(f"Chunk {CHUNK_INDEX + 1}/{CHUNK_COUNT}: {len(branch_data)} branches this run")

    # 2026-08-14 fix: this file is gitignored (regenerated data, not
    # source) — confirmed directly a plain open() here crashed every
    # scheduled GitHub Actions run so far, since a fresh CI checkout never
    # has it. Treated as "no existing rows to preserve" rather than an
    # error — this run's own fresh rows still get written either way.
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH) as f:
            fieldnames = next(csv.reader(f))
        existing = list(csv.DictReader(open(CSV_PATH)))
    else:
        fieldnames = DEFAULT_FIELDNAMES
        existing = []
    kept = [row for row in existing if not row["store"].startswith("Super Liquor")]

    new_rows = []
    for b in branch_data:
        label = b["Text"].replace("Super Liquor", "").strip()
        base = b["Value"]
        store_id = match_store_id(stores, label)
        store_name = f"Super Liquor {label}"
        print(f"Scraping {store_name}...")
        for cat, path in CATEGORIES.items():
            products = None
            for attempt in (1, 2):
                try:
                    products = s.scrape_nopcommerce(f"{base}/{path}")
                    break
                except Exception as e:
                    print(f"  {cat} attempt {attempt} error: {e}")
                    if attempt == 1:
                        time.sleep(8)  # give their server a real break before retrying
            if products:
                for p in products:
                    new_rows.append({
                        "store": store_name, "store_id": store_id or "", "category": cat,
                        "product_name": p["name"], "price": p["price"], "was_price": p["was_price"],
                        "in_stock": p["in_stock"], "url": p["url"], "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
                    })
            time.sleep(3)  # polite delay between category requests
        time.sleep(3)

    all_rows = kept + new_rows
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nDone. Wrote {len(new_rows)} fresh Super Liquor branch rows ({len(all_rows)} total rows in file).")


if __name__ == "__main__":
    main()
