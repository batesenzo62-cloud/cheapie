"""One-off: check whether Super Liquor has a dedicated specials/promotions
page not in our CATEGORIES dict, since the sampled beer category page had
zero items on special right now. Delete after use."""
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}
base = "https://alexandra.superliquor.co.nz"

# Check homepage nav for any specials/promo links
r = requests.get(base + "/", headers=HEADERS, timeout=20)
soup = BeautifulSoup(r.text, "html.parser")
nav_links = soup.select("a[href]")
promo_links = [a["href"] for a in nav_links if any(w in a["href"].lower() or w in a.get_text(" ", strip=True).lower() for w in ["special", "promo", "deal", "sale", "clearance"])]
print("promo-looking nav links:", set(promo_links))

# Try common specials URL patterns directly
for path in ["/specials", "/promotions", "/deals", "/on-sale", "/clearance", "/specials-1"]:
    url = base + path
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        item_count = resp.text.count("item-box")
        old_price_count = resp.text.count("old-product-price") + resp.text.count("old-price")
        print(f"{path}: status={resp.status_code} item-box mentions={item_count} old-price mentions={old_price_count}")
    except Exception as e:
        print(f"{path}: error {e}")
