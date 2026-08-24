"""One-off: Mt Eden is marked online=true with subdomain "mt-eden" in
bottleo_stores.json and has a real store_id, but has zero confirmed
product rows. Test its actual scrape directly to find out why. Also
check whether thebottleo.co.nz (the parent brand site) has any real
national product catalog we might be missing, since the current fallback
design assumes it doesn't. Delete after use."""
import sys, requests
sys.path.insert(0, ".")
import scrape_bottleo_products as bo

print("=== Testing Mt Eden's own scrape ===")
base = bo.base_url("mt-eden")
print("base url:", base)
depts = bo.get_departments(base)
print("departments:", depts)
if depts:
    rows = bo.scrape_store({"name": "Mt Eden", "subdomain": "mt-eden", "store_id": "test"})
    print(f"scraped {len(rows)} rows")
    for r in rows[:5]:
        print(" ", r["product_name"], r["price"])

print("\n=== Checking thebottleo.co.nz for a real national catalog ===")
for url in ["https://www.thebottleo.co.nz", "https://thebottleo.co.nz", "https://www.thebottleo.co.nz/shop", "https://www.thebottleo.co.nz/products"]:
    try:
        r = requests.get(url, headers=bo.HEADERS, timeout=15)
        print(f"{url} -> status {r.status_code}, bytes {len(r.content)}")
    except Exception as e:
        print(f"{url} -> error: {e}")
