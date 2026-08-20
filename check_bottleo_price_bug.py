"""One-off: find EVERY occurrence of 'Billy Maverick 6pk Cans' in the raw
page and dump the actual visible product-card HTML (not the analytics
JSON blob) to see what price a real shopper would actually see. Delete
after use."""
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

indices = [m.start() for m in re.finditer(re.escape("Billy Maverick 6pk Cans"), html)]
print("all occurrence indices:", indices)
for idx in indices:
    print(f"\n=== occurrence at {idx} ===")
    print(html[max(0,idx-300):idx+600])

# Also directly test what parse_page's regex itself captures, isolated
print("\n\n=== what parse_page's own regex captures for this product ===")
for m in re.finditer(
    r'<a href="(/lines/[^"]*)">(?:(?!<a href="/lines/).)*?'
    r'talker__product-name">([^<]+)</span>\s*'
    r'(?:<span class="weak size talker__name__size">([^<]*)</span>)?'
    r'(?:(?!<a href="/lines/).)*?'
    r'(?:talker__prices__was[^>]*>\s*was \$([\d.]+)\s*</span>(?:(?!<a href="/lines/).)*?)?'
    r'price__sell"[^>]*>\$([\d.]+)<',
    html, re.S
):
    if "Billy Maverick 6pk" in (m.group(2) or ""):
        print("full match:")
        print(repr(m.group(0)))
