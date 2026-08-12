"""
Cheapie — one-off diagnostic: why do Big Barrel/Super Liquor never show a
was_price, despite parse_nopcommerce_page() looking for .old-price?

Fetches a real category page from each and prints the raw HTML around the
first few price blocks, so the actual class names can be read directly
from a live response (this sandbox's own network can't currently reach
either site — GitHub Actions runs on a different network and isn't
affected).

HOW TO RUN:
    python3 diagnose_was_price.py
"""
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}


def dump(label, url):
    print(f"\n=== {label}: {url} ===")
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  ERROR: {e}")
        return
    html = r.text
    print(f"  status={r.status_code} size={len(html)}")
    print(f"  actual-price count: {html.count('actual-price')}")
    print(f"  old-price count: {html.count('old-price')}")
    idx = html.find("old-product-price")
    if idx == -1:
        idx = html.find("old-price")
    if idx != -1:
        print("  --- context around first old-price/old-product-price ---")
        print(html[max(0, idx - 100):idx + 400])
    else:
        # No discount anywhere on this page at all -- show one full
        # product's price block so the real (undiscounted) markup is
        # visible regardless.
        idx2 = html.find("actual-price")
        if idx2 != -1:
            print("  --- context around first actual-price (no old-price found anywhere on page) ---")
            print(html[max(0, idx2 - 300):idx2 + 300])


if __name__ == "__main__":
    dump("Big Barrel (craft beers, real products)", "https://bigbarrel.co.nz/en/craft-beers-2")
    dump("Big Barrel (wines, real products)", "https://bigbarrel.co.nz/en/wines")
    dump("Super Liquor (Alexandra, beer)", "https://alexandra.superliquor.co.nz/beer")
    dump("Super Liquor (Alexandra, wine)", "https://alexandra.superliquor.co.nz/wine")
