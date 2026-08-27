"""
One-off diagnostic: time how long a single Big Barrel branch takes to
scrape across every category path, and flag any category that pages
further than expected (a small independent branch catalogue should never
need more than a handful of pages per category) — checking whether the
47-branch x 70-category full run genuinely just needs chunking (like
Super Liquor did) or whether has_next_page() is producing false positives
on branch subdomains specifically.
"""
import time
import scrape_independent_stores as s

NATIONAL_BASE = "https://bigbarrel.co.nz"
CATEGORY_PATHS = [
    (url[len(NATIONAL_BASE):], category)
    for (store, url, category, platform) in s.TARGETS
    if store == "Big Barrel"
]

BRANCHES_TO_TEST = [
    ("Havelock North", "https://havelock.bigbarrel.co.nz"),
    ("Concord", "https://concord.bigbarrel.co.nz"),
]

for label, base in BRANCHES_TO_TEST:
    print(f"=== {label} ({base}) — {len(CATEGORY_PATHS)} categories ===")
    branch_start = time.time()
    for path, category in CATEGORY_PATHS:
        t0 = time.time()
        try:
            products = s.scrape_nopcommerce(f"{base}{path}")
            elapsed = time.time() - t0
            flag = " <<<< SLOW" if elapsed > 5 else ""
            print(f"  {path:45s} {category:8s} {len(products):4d} products  {elapsed:5.2f}s{flag}")
        except Exception as e:
            print(f"  {path:45s} {category:8s} ERROR: {e}  ({time.time()-t0:.2f}s)")
    print(f"  TOTAL for {label}: {time.time() - branch_start:.1f}s\n")
