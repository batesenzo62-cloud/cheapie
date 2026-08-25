"""One-off: check /super-specials (real product page, likely has real
was_price data) and the promos.superliquor.co.nz link (looks like bundle/
multi-buy deal content). Delete after use."""
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}
base = "https://alexandra.superliquor.co.nz"

print("=== /super-specials ===")
r = requests.get(base + "/super-specials", headers=HEADERS, timeout=20)
print("status:", r.status_code, "bytes:", len(r.text))
soup = BeautifulSoup(r.text, "html.parser")
items = soup.select("div.item-box")
print(f"item-box count: {len(items)}")
for item in items[:8]:
    name_el = item.select_one(".product-title a, h2.product-title")
    name = name_el.get_text(strip=True) if name_el else "???"
    price_el = item.select_one(".prices .actual-price, .price.actual-price")
    price = price_el.get_text(strip=True) if price_el else "?"
    was_el = item.select_one(".prices .old-product-price, .old-product-price, .prices .old-price, .old-price")
    was = was_el.get_text(strip=True) if was_el else None
    print(f"  {name}: price={price} was={was}")

print("\n=== promos.superliquor.co.nz/oedfys1 ===")
r2 = requests.get("https://promos.superliquor.co.nz/oedfys1", headers=HEADERS, timeout=20)
print("status:", r2.status_code, "bytes:", len(r2.text))
text = BeautifulSoup(r2.text, "html.parser").get_text(" ", strip=True)
print("page text sample (first 2000 chars):")
print(text[:2000])
