"""
One-off diagnostic, phase 2: Liquorfy's own API attributed three different
promo prices to three different Black Bull Liquor branches (Opunake, The
Peg, Manurewa) but all three product_urls pointed at the SAME domain
(blackbullliquorhornbyhub.co.nz) — the same kind of branch-misattribution
bug this project already found and fixed in its own app. This checks each
product's REAL current price directly on the site the URL actually points
to, and (where a branch has its own independent site) on that branch's own
site too, to see whether Liquorfy's per-branch prices are genuine or just
one scraped catalogue relabelled under multiple branch names.

HOW TO RUN:
    python3 check_liquorfy_sample.py
"""
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# (liquorfy's claimed store, liquorfy's claimed price, liquorfy's product_url,
#  a real independent site to cross-check against if one exists)
SAMPLES = [
    {
        "name": "Cody'S Gold 7% 12pk Can",
        "liquorfy_store": "Black Bull Liquor Opunake",
        "liquorfy_price": 29.99,
        "liquorfy_was": 34.99,
        "liquorfy_url": "https://blackbullliquorhornbyhub.co.nz/products/codys-gold-7-12pk-can",
        "own_site_guess": "https://blackbullliquoropunake.co.nz",
    },
    {
        "name": "Woodstock 7% 18pk Cans",
        "liquorfy_store": "Black Bull Liquor The Peg",
        "liquorfy_price": 44.99,
        "liquorfy_was": 48.99,
        "liquorfy_url": "https://blackbullliquorhornbyhub.co.nz/products/woodstock-7-18-pk-cans",
        "own_site_guess": "https://blackbullliquorthepeg.co.nz",
    },
    {
        "name": "Woodstock Bourbon & Cola Zero Sugar 7% 18pk Cans",
        "liquorfy_store": "Black Bull Liquor Manurewa",
        "liquorfy_price": 44.99,
        "liquorfy_was": 46.99,
        "liquorfy_url": "https://blackbullliquorhornbyhub.co.nz/products/woodstock-bourbon-cola-zero-sugar-7-18pk-cans",
        "own_site_guess": "https://blackbullliquormanurewa.co.nz",
    },
]


def fetch_shopify_price(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return f"HTTP {r.status_code}"
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        # crude: grab anything that looks like a price near the top of the page
        import re
        prices = re.findall(r"\$\d+\.\d{2}", text[:4000])
        return f"OK, prices seen near top of page: {prices[:6]}"
    except Exception as e:
        return f"error: {e}"


def main():
    for s in SAMPLES:
        print(f"=== {s['name']} ===")
        print(f"Liquorfy says: {s['liquorfy_store']} — ${s['liquorfy_price']} (was ${s['liquorfy_was']})")
        print(f"Liquorfy's product_url: {s['liquorfy_url']}")
        print(f"  -> {fetch_shopify_price(s['liquorfy_url'])}")
        print(f"That branch's own likely site: {s['own_site_guess']}")
        r = requests.get(s['own_site_guess'], headers=HEADERS, timeout=15)
        print(f"  -> homepage status: {r.status_code}")
        print()


if __name__ == "__main__":
    main()
