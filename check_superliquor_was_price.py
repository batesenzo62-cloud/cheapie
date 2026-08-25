"""One-off: Super Liquor shows zero was_price rows in the DB despite the
nopCommerce parser having a specific, previously-verified was_price
selector (confirmed working for Big Barrel, same platform). Check a real
live Super Liquor branch page directly to see if their actual HTML uses a
different class, or if there's genuinely nothing on special right now.
Delete after use."""
import sys, re, requests
sys.path.insert(0, ".")
import scrape_independent_stores as s
from bs4 import BeautifulSoup

# Get a real Super Liquor branch URL
r = requests.get("https://www.superliquor.co.nz/GetStoresByState", headers=s.HEADERS, timeout=20)
branches = [b for b in r.json()["stores"] if b["Value"]]
print(f"{len(branches)} real branches found")
test_branch = branches[0]
print("testing branch:", test_branch["Text"], test_branch["Value"])

base = test_branch["Value"]
url = f"{base}/beer"
resp = requests.get(url, headers=s.HEADERS, timeout=20)
print("status:", resp.status_code, "bytes:", len(resp.text))

soup = BeautifulSoup(resp.text, "html.parser")
items = soup.select("div.item-box")
print(f"item-box count: {len(items)}")

# Check the actual class names present on price-related elements for the first few items
for item in items[:5]:
    name_el = item.select_one(".product-title a, h2.product-title")
    name = name_el.get_text(strip=True) if name_el else "???"
    price_divs = item.select("[class*=price]")
    classes_found = set()
    for d in price_divs:
        classes_found.update(d.get("class", []))
    print(f"  {name}: price-related classes = {classes_found}")

# Also check overall page for any "old-price"/"was"/"special" indicators anywhere
full_text = resp.text
for marker in ["old-product-price", "old-price", "was-price", "special-price", "sale-price", "discount"]:
    count = full_text.count(marker)
    print(f"occurrences of {marker!r} in raw HTML: {count}")
