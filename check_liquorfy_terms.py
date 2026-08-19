"""One-off: does Woolworths price the same product identically across
distant NZ regions, or does it vary by branch like New World/PAK'nSAVE?
A handful of manual requests for a factual check, not a pipeline. Delete
after use."""
import requests
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://api.liquorfy.co.nz/products"

# Two NZ locations far apart: Auckland and Dunedin
LOCATIONS = [("Auckland", -36.8485, 174.7633), ("Dunedin", -45.8788, 170.5028)]

for label, lat, lon in LOCATIONS:
    print(f"=== {label} — Woolworths/countdown beer products within 10km ===")
    params = {"lat": lat, "lon": lon, "radius_km": 10, "chain": "countdown", "page_size": 10, "unique_products": "true", "category": "beer"}
    r = requests.get(BASE, headers=HEADERS, params=params, timeout=20)
    print(f"status={r.status_code}")
    if r.status_code == 200:
        items = r.json().get("items", [])
        for it in items:
            price = it.get("price", {})
            print(f"  {it.get('id')} | {it.get('name')} | {price.get('store_name')} | ${price.get('price_nzd')}")
    print()
