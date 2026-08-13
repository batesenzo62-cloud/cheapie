"""
Cheapie — one-off: check whether any Bottle-O branch marked "online: false"
in bottleo_stores.json actually has a real, working online shop now.

Reported directly: Bottle-O Mangatera is marked offline in this file, but
genuinely has its own real site (mangatera.shop.thebottleo.co.nz resolves
to a live myfoodlink-hosted store) — the original one-time discovery scrape
either missed it or it's gone stale since. Checks every "online: false"
branch's most likely subdomain slug (a few real variations seen among
already-confirmed-online branches: plain lowercase-no-spaces, hyphenated,
and no-apostrophe) against the same shop.thebottleo.co.nz pattern the real
per-branch scraper uses, and reports which ones resolve to a real store
with actual products — not just a 200 response, since a wrong/expired
subdomain can still resolve to a generic MyFoodLink landing page.

Delete this file after running once — it's a one-time audit, not a
recurring job.

HOW TO RUN:
    python3 check_bottleo_offline_branches.py
"""
import json
import re
import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}


def candidate_slugs(name):
    base = name.lower().strip()
    base = base.replace("'", "").replace("’", "")
    no_space = re.sub(r"[^a-z0-9]", "", base)
    hyphenated = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    candidates = [no_space, hyphenated]
    # de-dupe, keep order
    seen = set()
    out = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def check_subdomain(slug):
    url = f"https://{slug}.shop.thebottleo.co.nz"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except Exception as e:
        return None, str(e)
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"
    text = resp.text
    # A real, live store page has real product/department links; a dead or
    # unclaimed subdomain typically 200s with a generic "store not found"
    # style page instead. Heuristic: real stores link to /search?q[]=category
    # (the same department-listing pattern scrape_bottleo_products.py uses).
    if "category:" in text or "/search?q" in text:
        return url, "looks like a real live store"
    return None, "resolved but doesn't look like a real store page"


def main():
    with open("bottleo_stores.json") as f:
        stores = json.load(f)

    offline = [s for s in stores if not s.get("online")]
    print(f"Checking {len(offline)} branches currently marked offline...\n")

    found = []
    for s in offline:
        matched_url = None
        reason = None
        for slug in candidate_slugs(s["name"]):
            matched_url, reason = check_subdomain(slug)
            if matched_url:
                break
            time.sleep(0.3)
        if matched_url:
            print(f"  FOUND: {s['name']} -> {matched_url}")
            found.append({"name": s["name"], "store_id": s["store_id"], "url": matched_url})
        time.sleep(0.5)

    print(f"\nDone. {len(found)} of {len(offline)} branches marked offline actually have a real working store.")
    with open("bottleo_offline_check_results.json", "w") as f:
        json.dump(found, f, indent=2)


if __name__ == "__main__":
    main()
