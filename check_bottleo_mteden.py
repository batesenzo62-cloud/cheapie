"""One-off: Mt Eden resolves real department IDs but scrape_department()
returns 0 products for all of them — dump the raw first-page response for
the beer department to see what's actually happening. Delete after use."""
import sys, requests
sys.path.insert(0, ".")
import scrape_bottleo_products as bo

base = bo.base_url("mt-eden")
depts = bo.get_departments(base)
dept_id = depts.get("beer")
url = f"{base}/search?q%5B%5D=category%3A{dept_id}"
print("url:", url)
r = requests.get(url, headers=bo.HEADERS, timeout=20)
print("status:", r.status_code, "bytes:", len(r.text))
products = bo.parse_page(r.text, base)
print("parsed products:", len(products))

# Check for common failure signals in the raw HTML
html = r.text
for marker in ["talker__product-name", "No results", "no products", "empty", "Sorry"]:
    print(f"  contains {marker!r}: {marker in html}")

print("\nfirst 3000 chars of body:")
print(html[:3000])
