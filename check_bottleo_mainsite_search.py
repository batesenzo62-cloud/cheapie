"""One-off: inspect thebottleo.co.nz/search's actual product results to
see whether this is a true national catalog or defaults to one specific
branch's data under the hood. Delete after use."""
import re
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
url = "https://www.thebottleo.co.nz/search?q=steinlager"
r = requests.get(url, headers=HEADERS, timeout=20)
html = r.text

# Same parse pattern as scrape_bottleo_products.py's parse_page()
for m in re.finditer(
    r'<a href="(/lines/[^"]*)">(?:(?!<a href="/lines/).)*?'
    r'talker__product-name">([^<]+)</span>\s*'
    r'(?:<span class="weak size talker__name__size">([^<]*)</span>)?'
    r'(?:(?!<a href="/lines/).)*?'
    r'price__sell"[^>]*>\$([\d.]+)<',
    html, re.S
):
    url_path, name, size, price = m.groups()
    print(f"{name} {size} -> ${price} (link: {url_path})")

# Check if there's any indication of which specific store this search is scoped to
print("\n=== looking for store/location context in the page ===")
loc_hints = re.findall(r'(store[_-]?name|current[_-]?store|selected[_-]?store)["\':]?\s*[:=]\s*["\']?([^"\'<>,}]{2,40})', html, re.I)
print(loc_hints[:10])
title_match = re.search(r"<title>([^<]*)</title>", html)
print("page title:", title_match.group(1) if title_match else None)
