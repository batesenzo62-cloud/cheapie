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
import csv, time, requests, os
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
    # 2026-08-12 fix: these six used to rely on match_store_id() finding
    # the branch label as a substring of a stores.name value — confirmed
    # directly (see fix_thirsty_branch_stores.py) that this silently fails
    # in two different ways: Whangaparaoa/Franich Street's real stores
    # exist but under generic "Thirsty Liquor Auckland" names with the
    # distinguishing detail only in the address, and Mt Eden/Huntsbury/
    # Tauranga/Dunedin either didn't exist in the table at all or (Dunedin)
    # only had OTHER real Dunedin branches that aren't this specific one —
    # meaning match_store_id() was either returning None (branch invisibly
    # dropped into "ships NZ-wide" instead of "near you") or, for Dunedin,
    # silently picking the wrong physical location. Hardcoded here instead,
    # same as Te Rapa always was.
    "Whangaparaoa": ("https://thirstyliquorwhangaparaoa.co.nz", "5d29c9f6-28e8-48a1-a567-7b14bc0f506e"),
    "Mt Eden": ("https://thirstyliquormteden.co.nz", "e85a574c-86ed-4dec-8044-77cdc4498416"),
    "Franich Street": ("https://thirstyliquorfranichst.co.nz", "01420451-b69e-4cb1-a76f-b6a1ac45f24d"),
    "Chapel Park": ("https://thirstyliquorchapelpark.co.nz", None),
    "Pukekohe": ("https://thirstyliquorpukekohe.co.nz", None),
    "Havelock North": ("https://thirstyliquorhavelocknorth.co.nz", None),
    "Levin": ("https://thirstyliquorlevin.co.nz", None),
    "Dunedin": ("https://thirstyliquordunedin.co.nz", "a8e86ef9-274b-43f2-9cbc-48c2e3d329ba"),
    "Islington": ("https://thirstyliquorislington.co.nz", None),
    "Huntsbury": ("https://thirstyliquorhuntsbury.co.nz", "e93e8684-524c-40fd-8dc0-b85bdefa3e6a"),
    "Tauranga": ("https://www.thirstyliquortauranga.co.nz", "c9e54a08-aae5-4eeb-b8a5-2a6c3168fcee"),
    "Te Rapa": ("https://tlterapa.co.nz", "377320fd-3b7c-424d-9ce0-b46f7c7893b9"),
    # 2026-08-14: found via a systematic audit of every branch with no
    # catalogue of its own — same staleness issue Bottle-O's store list
    # had (this file's own BRANCHES dict is really a one-time discovery
    # too, despite the module docstring's "found via the site's store
    # locator" claim). Both single, unambiguous stores matches in the
    # database (no address-collision risk like Dunedin's three real
    # branches had), so hardcoded directly rather than left to
    # match_store_id()'s substring guess.
    "Papakura": ("https://thirstyliquorpapakura.co.nz", "fb3a4d58-b84a-48cb-ad78-5523f049e985"),
    "Churchill Ave": ("https://thirstyliquorchurchillave.co.nz", "43f2041e-e673-48fb-a83e-637a16c7d48c"),
}
CATEGORIES = {"beer": "collections/beer", "rtd": "collections/rtds", "wine": "collections/wine", "spirits": "collections/spirits"}

# 2026-08-26: reported directly — asked for "2 for 1"-style bundle deals
# on the Deals tab. Confirmed there's no such thing on Super Liquor (their
# specials page has no comparison price in the markup at all, nothing to
# scrape), but Thirsty Liquor genuinely has a real collections/bundles
# page — e.g. "Jim Beam, Canadian Club, Chatelle 1L. Any Two For $99".
# These don't fit the was_price/price pair the Deals tab is built around
# (it's a multi-buy deal on one listing, not a single markdown), so the
# deal terms are just part of the product name for now rather than a
# separate price field — still real, useful information either way, and
# shows up in normal search/category browsing even before the Deals tab
# gains real support for this deal shape.
BUNDLE_CATEGORY_SLUG = "collections/bundles"


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

        # Bundles can span any category (a whisky/gin/rum multi-buy is
        # still "spirits", but nothing guarantees that) — classify_auto_
        # category (already proven for Black Bull's mixed-department
        # "classic" page) keyword-matches each product's own name instead
        # of assuming one fixed category for the whole collection.
        try:
            bundle_products = s.scrape_shopify(f"{base}/{BUNDLE_CATEGORY_SLUG}")
            for p in bundle_products:
                new_rows.append({
                    "store": store_name,
                    "store_id": store_id or "",
                    "category": s.classify_auto_category(p["name"]),
                    "product_name": p["name"],
                    "price": p["price"],
                    "was_price": p["was_price"],
                    "in_stock": p["in_stock"],
                    "url": p["url"],
                    "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
                })
        except Exception as e:
            print(f"  bundles error: {e}")
        time.sleep(1)

    print(f"\nTotal new branch-specific rows: {len(new_rows)}")

    # 2026-08-14 fix: this file is gitignored (regenerated data, not
    # source) — confirmed directly that a plain open() here crashed every
    # scheduled GitHub Actions run so far, since a fresh CI checkout never
    # has it. Treated as "no existing rows to preserve" rather than an
    # error — this run's own fresh rows still get written either way.
    scraped_store_names = {f"Thirsty Liquor {label}" for label in BRANCHES}
    if os.path.exists("independent_store_prices.csv"):
        with open("independent_store_prices.csv") as f:
            existing = list(csv.DictReader(f))
    else:
        existing = []

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
