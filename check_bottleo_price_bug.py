"""One-off: fetch a live Bottle-O branch's RTD page and run the actual
parse_page() from scrape_bottleo_products.py against real current HTML to
see if the impossibly-cheap-price bug (e.g. Jameson 10-pack for $4.50) is
still live in the scraper today, or if it's stale data from before the
2026-08-13 regex fix. Delete after use."""
import sys, re, json
sys.path.insert(0, ".")
import scrape_bottleo_products as bo
import requests

base = bo.base_url("whangaparaoa")
depts = bo.get_departments(base)
print("departments:", depts)

rtd_slug = None
for slug, cat in bo.WANTED_SLUGS.items():
    if cat == "rtd":
        rtd_slug = slug
        break
print("rtd slug:", rtd_slug)

dept_id = depts.get(rtd_slug)
print("dept_id:", dept_id)
if dept_id:
    url = f"{base}/search?q%5B%5D=category%3A{dept_id}"
    r = requests.get(url, headers=bo.HEADERS, timeout=20)
    print("status:", r.status_code, "len:", len(r.text))
    products = bo.parse_page(r.text, base)
    print(f"parsed {len(products)} products")
    for p in products[:60]:
        print(f"  {p['name']!r} -> ${p['price']} url={p['url']}")

    # Save raw HTML for manual inspection of one specific suspicious card
    with open("/tmp/bottleo_rtd_raw.html", "w") as f:
        f.write(r.text)
