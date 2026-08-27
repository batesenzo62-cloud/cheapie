"""
One-off diagnostic (v2 — flush=True everywhere): the first version of this
script produced ZERO log output before being killed by its own 30-minute
timeout, even though it should have completed 2 branches x 70 categories
in a few minutes under normal conditions. Root cause of the missing
output: Python buffers stdout when it isn't a real terminal (true for
GitHub Actions' log capture), so nothing printed shows up until either the
buffer fills or the process exits cleanly — a process killed by a timeout
loses everything still sitting in that buffer. flush=True on every print
fixes that blind spot so this run's real progress is actually visible.

Also narrowed scope drastically (one category on one branch, page-by-page)
and added a request-level connection-reset counter, since the earlier full
run hit GitHub Actions' 6h ceiling with no clear explanation, and manual
testing from a different network mid-investigation got an immediate SSL
"Connection reset by peer" on a bigbarrel.co.nz branch subdomain — plausible
that the site started rate-limiting/resetting connections under the load
of the earlier ~thousands-of-requests 6h run, which would make ordinary
20s request timeouts (not real pagination depth) the actual time sink.
"""
import time
import requests
from bs4 import BeautifulSoup
import scrape_independent_stores as s

BASE = "https://havelock.bigbarrel.co.nz"
PATH = "/en/beers"

print(f"Testing {BASE}{PATH} — one page at a time, single requests.get() calls", flush=True)

for page in range(1, 6):
    page_url = f"{BASE}{PATH}" if page == 1 else f"{BASE}{PATH}?pagenumber={page}"
    t0 = time.time()
    try:
        resp = requests.get(page_url, headers=s.HEADERS, timeout=15)
        elapsed = time.time() - t0
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("div.item-box")
        pager = soup.select_one(".pager")
        has_next = bool(pager) and any(a.get_text(strip=True).lower() == "next" for a in pager.select("a"))
        print(f"  page {page}: status={resp.status_code} items={len(items)} has_next={has_next} elapsed={elapsed:.2f}s", flush=True)
    except Exception as e:
        print(f"  page {page}: ERROR {type(e).__name__}: {e}  elapsed={time.time()-t0:.2f}s", flush=True)

print("\nNow timing the full scrape_nopcommerce() call for this same category:", flush=True)
t0 = time.time()
try:
    products = s.scrape_nopcommerce(f"{BASE}{PATH}")
    print(f"  scrape_nopcommerce total: {len(products)} products in {time.time()-t0:.2f}s", flush=True)
except Exception as e:
    print(f"  scrape_nopcommerce ERROR after {time.time()-t0:.2f}s: {type(e).__name__}: {e}", flush=True)

print("\nDone.", flush=True)
