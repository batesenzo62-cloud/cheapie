"""One-off: check the granular RTD sub-collections (rum-rtds, other-rtds,
specials, hot-deals, bundles) for a Black Heart 4-pack our scraper's
generic "rtds" collection might not include. Delete after use."""
import sys
sys.path.insert(0, ".")
import scrape_independent_stores as s

base = "https://thirstyliquorhavelocknorth.co.nz"
for slug in ["rum-rtds", "other-rtds", "specials", "hot-deals", "bundles", "bourbon-rtds"]:
    url = f"{base}/collections/{slug}"
    print(f"=== {url} ===")
    try:
        products = s.scrape_shopify(url)
        black_heart = [p for p in products if "black heart" in p["name"].lower()]
        print(f"  {len(products)} total products, {len(black_heart)} Black Heart products:")
        for p in black_heart:
            print(f"    {p['name']} -> ${p['price']}")
        if not black_heart and products:
            print(f"    (sample of what IS here: {[p['name'] for p in products[:5]]})")
    except Exception as e:
        print(f"  error: {e}")
