"""One-off: check if thebottleo.co.nz supports the same department/sidebar
JSON + category browse mechanism each branch subdomain uses, which would
let us scrape a genuine national generic catalog instead of borrowing one
specific branch's real data as a stand-in. Delete after use."""
import sys, re, requests
sys.path.insert(0, ".")
import scrape_bottleo_products as bo

base = "https://www.thebottleo.co.nz"
depts = bo.get_departments(base)
print("departments resolved via get_departments():", depts)

if depts:
    for cat, dept_id in list(depts.items())[:2]:
        url = f"{base}/search?q%5B%5D=category%3A{dept_id}"
        r = requests.get(url, headers=bo.HEADERS, timeout=20)
        products = bo.parse_page(r.text, base)
        print(f"\n{cat} ({dept_id}): {len(products)} products via page 1")
        for p in products[:5]:
            print(f"  {p['name']} -> ${p['price']}")
