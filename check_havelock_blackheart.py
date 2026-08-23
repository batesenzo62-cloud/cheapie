"""One-off: check Thirsty Liquor Havelock North's real RTD collection page
for any Black Heart 4-pack we might be missing. Delete after use."""
import sys
sys.path.insert(0, ".")
import scrape_independent_stores as s

for cat, path in {"rtds": "collections/rtds", "spirits": "collections/spirits"}.items():
    url = f"https://thirstyliquorhavelocknorth.co.nz/{path}"
    print(f"=== {url} ===")
    try:
        products = s.scrape_shopify(url)
        black_heart = [p for p in products if "black heart" in p["name"].lower()]
        print(f"  {len(products)} total products, {len(black_heart)} Black Heart products:")
        for p in black_heart:
            print(f"    {p['name']} -> ${p['price']}")
    except Exception as e:
        print(f"  error: {e}")
