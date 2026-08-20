"""One-off: check price__units text across several products (both
correctly-priced multi-packs and the broken Billy Maverick 6pk) to find
the actual site convention for per-unit vs per-pack pricing. Delete after
use."""
import sys, re
sys.path.insert(0, ".")
import scrape_bottleo_products as bo
import requests

base = bo.base_url("whangaparaoa")
depts = bo.get_departments(base)
dept_id = depts.get("rtd")
url = f"{base}/search?q%5B%5D=category%3A{dept_id}"
r = requests.get(url, headers=bo.HEADERS, timeout=20)
html = r.text

# Capture product name + price + price__units for every product card
for m in re.finditer(
    r'talker__product-name">([^<]+)</span>\s*'
    r'(?:<span class="weak size talker__name__size">([^<]*)</span>)?.*?'
    r'price__sell"[^>]*>\$([\d.]+)</strong>\s*'
    r'(?:<span class="price__units weak">\s*([^<]*?)\s*</span>)?',
    html, re.S
):
    name, size, price, units = m.groups()
    print(f"{name!r} | size={size!r} | price=${price} | units={units!r}")
