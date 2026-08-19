"""
One-off diagnostic: does liquorfy.co.nz have real New World / Woolworths
(Countdown) pricing data? Those two chains block our own scrapers outright
(Cloudflare), so if Liquorfy genuinely has them, that's a real gap they
cover that we don't. Checks the chain filter on their /products API and
pulls a few sample products + prices per chain. Delete after use.

HOW TO RUN:
    python3 check_liquorfy_supermarkets.py
"""
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://api.liquorfy.co.nz/products"


def main():
    for chain in ["new_world", "countdown", "pak_n_save", "paknsave", "woolworths"]:
        url = f"{BASE}?chain={chain}&page_size=5&unique_products=true"
        print(f"=== chain={chain} ===")
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            print(f"status={r.status_code}")
            if r.status_code == 200:
                data = r.json()
                items = data.get("items", data if isinstance(data, list) else [])
                print(f"item count: {len(items)}")
                for it in items[:5]:
                    price = it.get("price", {})
                    print(f"  - {it.get('name')} | {price.get('store_name')} | ${price.get('price_nzd')} | url={it.get('product_url')}")
            else:
                print(r.text[:500])
        except Exception as e:
            print(f"error: {e}")
        print()

    # Also try the autocomplete endpoint for a common supermarket-heavy search
    for term in ["Speight's", "Corona", "Villa Maria"]:
        url = f"{BASE.rsplit('/',1)[0]}/products/autocomplete?q={term}&limit=15"
        print(f"=== autocomplete q={term} ===")
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                items = r.json()
                chains = sorted(set(it.get("chain") for it in items))
                print(f"chains seen: {chains}")
                for it in items:
                    if it.get("chain") in ("new_world", "countdown", "pak_n_save", "paknsave", "woolworths"):
                        print(f"  supermarket hit: {it}")
            else:
                print(f"status={r.status_code}: {r.text[:300]}")
        except Exception as e:
            print(f"error: {e}")
        print()


if __name__ == "__main__":
    main()
