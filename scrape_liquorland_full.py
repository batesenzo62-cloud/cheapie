"""
Cheapie — full Liquorland catalogue scraper (no Firecrawl, no browser).

Liquorland's category pages embed a full JSON payload for the current page
in a plain <script> tag (window.category = {...}), including a real
pagination.totalItems count, and ?p=N genuinely returns page N server-side
(confirmed: distinct products per page via plain requests.get, no JS
needed) — replaces the old Firecrawl-based scraper, which only covered
4 of the site's 9 real categories and whose ?p=N pagination attempt
silently returned page 1 every time.

alcohol-free and other are deliberately excluded: alcohol-free is a mix of
items already scraped under beer/wine (e.g. Heineken 0.0%) plus generic
mixers; other is entirely non-alcoholic drinks (tonic water, soda, cola) —
neither is a genuine liquor category this app compares.

2026-07-30: a product's price is only revealed once a store is "selected"
via the site's preferred-store cookie — with none set, every item shows
status "choosestore" and a null price. Once a store IS selected, an item
that store doesn't currently stock comes back status "storeunavailable"
with sentinel placeholder values (price "0.00", was_price "99999.99")
instead of a real price or null — silently treating that as a real $0.00
price would be wrong, so it's filtered out explicitly (real_price() below).
Tried recovering these via a fallback list of large/flagship stores before
settling on single-store: on a genuinely fair test (an unrecovered page of
niche wine SKUs) trying 3 more large stores recovered zero additional real
prices while ~4x'ing total runtime — this reflects genuine national
long-tail stock gaps (no single store carries the full 15,000+ SKU catalog
at once), not a scraping gap, so it's honest to report a real "no price
currently available" rather than manufacture one by exhausting stores.
"""
import requests, re, json, time, csv, os

HEADERS = {"User-Agent": "Mozilla/5.0"}
STORE_ID = 4  # Liquorland Parnell — arbitrary, price confirmed identical across stores when available

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def init_session():
    SESSION.get("https://www.liquorland.co.nz/")
    SESSION.post(
        "https://www.liquorland.co.nz/api/stores/preferred",
        files={"storeid": (None, str(STORE_ID))},
    )


CATEGORIES = [
    ("beer", "https://www.liquorland.co.nz/beer", "beer"),
    ("craft-beer", "https://www.liquorland.co.nz/craft-beer", "beer"),
    ("cider", "https://www.liquorland.co.nz/cider", "beer"),
    ("wine", "https://www.liquorland.co.nz/wine", "wine"),
    ("spirits", "https://www.liquorland.co.nz/spirits", "spirits"),
    ("liqueurs", "https://www.liquorland.co.nz/liqueurs", "spirits"),
    ("rtd", "https://www.liquorland.co.nz/rtd", "rtd"),
]


def extract_category_json(html):
    idx = html.find("window.category")
    if idx == -1:
        return None
    start = html.find("...{", idx)
    if start == -1:
        return None
    start += 3
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(html)):
        c = html[i]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return html[start:i + 1]
    return None


# 2026-09-01 fix: reported directly, then confirmed live — "unitprice" is
# the field that actually responds to the site's own per-store preferred-
# store selection (e.g. real $31.99 vs $33.99 for the same barcode at two
# different branches, confirmed via /api/stores/preferred). "originalretail"
# does not: it's empty ("0.00") for the large majority of real, in-stock,
# correctly-priced items (confirmed directly: 539 of 696 real wine variants
# sampled), and for the minority where it IS populated it stayed identical
# across two different branches for 1065 of 1071 real matched products in a
# direct side-by-side test — i.e. it isn't personalized by store at all, it
# just happens to mirror unitprice for some products. Using it meant this
# scraper was both silently dropping most of the real catalogue as "no
# price available" AND, for whatever it kept, often not even reflecting the
# selected store's actual price.
def real_price(variant):
    p = variant.get("unitprice")
    if p in (None, "", 0, "0.00", 0.0):
        return None
    return p


def fetch_page(base_url, page):
    url = base_url if page == 1 else f"{base_url}?p={page}"
    for attempt in (1, 2, 3):
        try:
            r = SESSION.get(url, timeout=20)
            r.raise_for_status()
            raw = extract_category_json(r.text)
            if not raw:
                raise ValueError("no window.category JSON found on page")
            return json.loads(raw)
        except Exception as e:
            print(f"    attempt {attempt} error on page {page}: {e}")
            time.sleep(5)
    return None


def scrape_category(site_slug, url, app_category):
    rows = []
    no_price = 0
    page = 1
    total_items = None
    while True:
        data = fetch_page(url, page)
        if not data:
            print(f"  page {page}: gave up after retries")
            break
        if total_items is None:
            total_items = data["pagination"]["totalItems"]
            print(f"  {site_slug}: {total_items} total items")
        items = data.get("items", [])
        if not items:
            break
        for item in items:
            sc = item["stylecolour"]
            variant = sc["variants"][0] if sc.get("variants") else None
            if not variant:
                continue
            price = real_price(variant)
            if price is None:
                no_price += 1
                continue
            was_price = variant.get("originalunitprice")
            if was_price == price:
                was_price = None
            stock = variant.get("availablestorestock") or variant.get("storestock") or 0
            # 2026-09-02 fix: reported directly — "View product page" just
            # took you to the category page, not the actual product. The
            # 2026-08-13 conclusion that there's no per-product URL at all
            # was wrong — stylecolour.url is a real, working per-product
            # relative path (confirmed directly: fetched one live, real
            # 200, real page). Missed originally because "this site was
            # unreachable" at the time to verify against the live HTML;
            # falls back to the category page url only for the rare item
            # missing it.
            product_url = sc.get("url")
            product_url = f"https://www.liquorland.co.nz{product_url}" if product_url else url
            rows.append({
                "product_name": item.get("description"),
                "price": price,
                "was_price": was_price,
                "in_stock": stock is not None and stock > 0,
                "store": "Liquorland",
                "category": app_category,
                "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
                "url": product_url,
                "_barcode": variant.get("barcode"),
            })
        fetched_so_far = page * 24
        if fetched_so_far >= total_items or len(items) == 0:
            break
        page += 1
        time.sleep(0.3)
    print(f"  {site_slug}: {len(rows)} priced rows, {no_price} with no price available, across {page} page(s)")
    return rows


def main():
    init_session()

    seen_barcodes = set()
    seen_names = set()
    all_rows = []
    for site_slug, url, app_category in CATEGORIES:
        print(f"Scraping {site_slug}...")
        rows = scrape_category(site_slug, url, app_category)
        for row in rows:
            bc = row["_barcode"]
            if (bc and bc in seen_barcodes) or row["product_name"] in seen_names:
                continue
            if bc:
                seen_barcodes.add(bc)
            seen_names.add(row["product_name"])
            del row["_barcode"]
            all_rows.append(row)
        print(f"  {site_slug}: {len(rows)} rows scraped so far this run (running total: {len(all_rows)})")
        time.sleep(1)

    print(f"\nScraped {len(all_rows)} total fresh Liquorland rows.")

    # Merge straight into chain_store_prices.csv, replacing the old
    # "Liquorland" rows — safe to re-run on a schedule, same replace-not-
    # append approach as the other per-branch scrapers.
    #
    # 2026-08-14 fix: chain_store_prices.csv is gitignored (regenerated
    # data, not source) — fine on a machine where it already exists from a
    # previous run, but confirmed directly this crashed every single
    # scheduled GitHub Actions run so far, every day, at this exact line:
    # a fresh CI checkout never has this file at all, so a plain open() in
    # read mode threw FileNotFoundError before a single row ever reached
    # Supabase (and since a failed step halts the rest of the job, none of
    # the OTHER chains' scrapers even got to run afterward either). Treat
    # "file doesn't exist yet" the same as "file exists but is empty" —
    # this run's own fresh rows become the whole result either way.
    chain_path = "chain_store_prices.csv"
    default_fieldnames = ["product_name", "price", "was_price", "in_stock", "store", "category", "fetched_at", "url"]
    if os.path.exists(chain_path):
        with open(chain_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            chain_fieldnames = reader.fieldnames
            kept = [r for r in reader if r["store"] != "Liquorland"]
    else:
        chain_fieldnames = default_fieldnames
        kept = []

    for row in all_rows:
        row_out = {k: row.get(k, "") for k in chain_fieldnames}
        kept.append(row_out)

    with open(chain_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=chain_fieldnames)
        writer.writeheader()
        writer.writerows(kept)
    print(f"Wrote {len(kept)} total rows to {chain_path} ({len(all_rows)} fresh Liquorland rows)")


if __name__ == "__main__":
    main()
