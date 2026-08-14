"""
Cheapie — one-off: check whether any Thirsty Liquor branch with no
confirmed catalogue data actually has its own real website.

Reported directly (following the same fix for Bottle-O): scrape_thirsty_
branches.py's BRANCHES dict is a hardcoded 12-branch list, despite its own
docstring claiming coverage from "the site's store locator" — it's really
a one-time discovery, same staleness risk Bottle-O's bottleo_stores.json
had (confirmed there: 10 of 78 "offline" branches actually had real sites).
Thirsty Liquor's known branches all follow one real, predictable pattern —
thirstyliquor<slug>.co.nz — so the same guess-and-verify approach applies.

For branches with a distinctive name, tries the name itself. For generic
names ("Thirsty Liquor Auckland", shared by many different physical
stores), tries the suburb/street from the address instead, since this
chain's real domains are per-suburb, not per-city.

Delete this file after running once — it's a one-time audit, not a
recurring job.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-anon-or-service-key"
    python3 check_thirsty_missing_branches.py
"""
import json
import os
import re
import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gkkchssgamqfavomcnoq.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_0D5UFWvifa2lI9o5lPbK8Q_iOsnLW8b")

GENERIC_NAMES = {"thirsty liquor", "thirsty liquor auckland", "thirsty liquor christchurch",
                  "thirsty liquor wellington", "thirsty liquor waikato", "thirsty liquor sth canterbury",
                  "thirsty liquor opotiki", "thirsty liquor papanui", "thirsty liquor morningside",
                  "thirsty liquor whakatane", "thirsty liquor richard pearse (timaru)"}


def slugify(text):
    text = text.lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]", "", text)


def candidate_slugs(name, address):
    candidates = []
    key = name.lower().strip()
    is_generic = key in GENERIC_NAMES or "auckland" in key

    if not is_generic:
        # Strip the "Thirsty Liquor" prefix, keep the distinctive part
        distinctive = re.sub(r"(?i)^thirsty\s*liquor\s*", "", name).strip()
        distinctive = re.sub(r"(?i)^manurewa:-\s*", "", distinctive).strip()
        if distinctive:
            candidates.append(slugify(distinctive))

    # Also always try deriving from the address (suburb/street) — this
    # chain's domains are per-suburb, and even a distinctively-named branch
    # might actually be registered under its street/suburb instead.
    parts = [p.strip() for p in address.split(",")]
    for p in parts[:3]:
        p = re.sub(r"^\d+[a-zA-Z]?[/\-]?\d*\s*", "", p)  # strip leading street number
        slug = slugify(p)
        if slug and slug not in candidates and len(slug) > 3:
            candidates.append(slug)

    return candidates[:4]  # bound how many we try per branch


def check_domain(slug):
    url = f"https://thirstyliquor{slug}.co.nz"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except Exception:
        return None
    if resp.status_code not in (200, 301, 302):
        return None
    text = resp.text.lower()
    if "shopify" in text or "/collections/" in text or "cdn.shopify.com" in text:
        return url
    return None


def main():
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/stores?select=id,name,address&name=ilike.*Thirsty*&order=name.asc",
        headers=headers, timeout=30,
    )
    stores = r.json()

    confirmed_ids = set()
    offset = 0
    while True:
        r2 = requests.get(
            f"{SUPABASE_URL}/rest/v1/products?select=store_id&store_name=ilike.*Thirsty*&store_id=not.is.null",
            headers={**headers, "Range": f"{offset}-{offset+999}"}, timeout=30,
        )
        page = r2.json()
        if not isinstance(page, list):
            break
        for row in page:
            confirmed_ids.add(row["store_id"])
        if len(page) < 1000:
            break
        offset += 1000

    no_catalog = [s for s in stores if s["id"] not in confirmed_ids]
    print(f"Checking {len(no_catalog)} branches with no confirmed catalogue...\n")

    found = []
    for s in no_catalog:
        for slug in candidate_slugs(s["name"], s["address"] or ""):
            url = check_domain(slug)
            if url:
                print(f"  FOUND: {s['name']} ({s['address']}) -> {url}")
                found.append({"name": s["name"], "store_id": s["id"], "address": s["address"], "url": url})
                break
            time.sleep(0.3)
        time.sleep(0.3)

    print(f"\nDone. {len(found)} of {len(no_catalog)} branches with no catalogue actually have a real working site.")
    with open("thirsty_missing_check_results.json", "w") as f:
        json.dump(found, f, indent=2)


if __name__ == "__main__":
    main()
