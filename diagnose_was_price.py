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
    idx = html.find("item-box")
    if idx == -1:
        print("  no 'item-box' found at all")
        return
    print(html[idx:idx + 2500])


if __name__ == "__main__":
    dump("Big Barrel (beers)", "https://bigbarrel.co.nz/en/beers")
    dump("Super Liquor (Alexandra, beer)", "https://alexandra.superliquor.co.nz/beer")
