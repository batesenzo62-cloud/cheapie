"""One-off: "No results" for Mt Eden's beer department — check if this is
a genuinely empty/new store, or an ID-mismatch bug, by checking the
homepage itself and a couple other departments. Delete after use."""
import sys, requests, re
sys.path.insert(0, ".")
import scrape_bottleo_products as bo

base = bo.base_url("mt-eden")
r = requests.get(base + "/", headers=bo.HEADERS, timeout=20)
print("homepage status:", r.status_code, "bytes:", len(r.text))
print("homepage contains 'talker__product-name':", "talker__product-name" in r.text)
print("homepage contains 'No results':", "No results" in r.text)

# Check if this store even has a sidebar JSON with real department IDs matching what /search expects
m = re.search(r'(dtgxwmigmg3gc\.cloudfront\.net/sidebar/[a-zA-Z0-9/_.-]+\.json[^"\']*)', r.text)
print("sidebar url found:", bool(m))
if m:
    sidebar_url = "https://" + m.group(1).replace("&amp;", "&")
    print("sidebar url:", sidebar_url)
    r2 = requests.get(sidebar_url, headers=bo.HEADERS, timeout=20)
    print("sidebar status:", r2.status_code)
    data = r2.json()
    print("departments in sidebar:", [(d.get("slug"), d.get("id"), d.get("count")) for d in data.get("departments", [])])
