"""One-off: check a real Bottle-O branch's real beer department page for
multi-buy text (using the same real department-resolution logic as
scrape_bottleo_products.py), since the earlier guessed-category-ID check
was invalid. Not a permanent scraper."""
import re
import scrape_bottleo_products as bp

base = bp.base_url("albany")
depts = bp.get_departments(base)
print("departments:", depts)

for slug, dept_id in depts.items():
    products = bp.scrape_department(base, dept_id)
    multibuy = [p for p in products if re.search(r"\b(?:any\s+)?\d{1,2}\s+for\s+\$", p["name"], re.I)]
    print(f"{slug}: {len(products)} products, {len(multibuy)} with multibuy-looking names")

# Also raw-scan the actual department page HTML for "for $" promo badges
# outside what parse_page's regex captures (e.g. a badge on the card the
# name/price regex doesn't reach).
import requests
sample_url = f"{base}/search?q%5B%5D=category%3A{list(depts.values())[0]}" if depts else base
r = requests.get(sample_url, headers=bp.HEADERS, timeout=20)
print("sample url:", sample_url)
print("sample page status:", r.status_code, "len:", len(r.text))
matches = re.findall(r".{0,40}\bfor\s+\$\s?\d.{0,20}", r.text, re.I)
print(f"raw ' for $' matches on page: {len(matches)}")
for m in matches[:10]:
    print("  ->", repr(m))
