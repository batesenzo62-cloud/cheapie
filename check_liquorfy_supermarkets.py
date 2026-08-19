"""
One-off diagnostic, phase 2: pull real priced New World/Woolworths/
PAK'nSAVE products from Liquorfy's /products API now that we know it
requires lat/lon/radius. Delete after use.
"""
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://api.liquorfy.co.nz/products"
# Napier, roughly central to a decent chunk of stores we already track
PARAMS_BASE = {"lat": -39.4928, "lon": 176.9120, "radius_km": 500, "page_size": 8, "unique_products": "true"}

for chain in ["new_world", "countdown", "paknsave"]:
    print(f"=== chain={chain} ===")
    params = dict(PARAMS_BASE, chain=chain)
    r = requests.get(BASE, headers=HEADERS, params=params, timeout=20)
    print(f"status={r.status_code}")
    if r.status_code == 200:
        items = r.json().get("items", [])
        print(f"item count: {len(items)}")
        for it in items[:6]:
            price = it.get("price", {})
            print(f"  - {it.get('name')} | {price.get('store_name')} | ${price.get('price_nzd')} | promo=${price.get('promo_price_nzd')} | {it.get('product_url')}")
    else:
        print(r.text[:400])
    print()
