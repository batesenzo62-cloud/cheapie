"""
Follow-up one-off investigation. Not a permanent scraper.
1. Pull wider context around the Liquorland homepage "2 for $110" JSON
   match found in the first pass, to see if it's a real structured
   promo feed worth scraping directly.
2. Check for dedicated specials/deals/promotions pages on chains that
   showed nothing on their homepage/category page.
3. Re-check Big Barrel/Super Liquor/Black Bull/Bottle-O with a couple
   more real category pages (spirits, wine) in case beer just doesn't
   run bundle deals but other categories do.
"""
import re
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

MULTIBUY_RE = re.compile(r"\b(?:any\s+)?(?:\d{1,2}|two|three|four|five|six|seven|eight|twelve)\s+for\s+\$\s?\d", re.I)


def check(label, url, context=60):
    print(f"=== {label} ({url}) ===")
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"  status: {r.status_code}, len: {len(r.text)}")
        if r.status_code != 200:
            print(f"  body sample: {r.text[:200]}")
            return None
        matches = list(re.finditer(MULTIBUY_RE.pattern, r.text, re.I))
        print(f"  text multi-buy matches: {len(matches)}")
        seen = set()
        for m in matches[:15]:
            ctx = r.text[max(0, m.start()-context):m.end()+context]
            if ctx not in seen:
                seen.add(ctx)
                print(f"    -> {ctx!r}")
        return r.text
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        return None
    finally:
        print()


# 1. Wider context on the Liquorland homepage promo JSON
html = check("Liquorland - homepage (wide context)", "https://www.liquorland.co.nz/", context=400)

# Look for the surrounding object/array structure specifically
if html:
    idx = html.lower().find("2 for $110".lower())
    if idx == -1:
        idx = html.find('2 for 110')
    if idx != -1:
        print("=== Liquorland promo JSON block (wide) ===")
        print(html[max(0, idx-1500):idx+500])
        print()

# 2. Dedicated specials/deals pages
for label, url in [
    ("Liquorland - specials", "https://www.liquorland.co.nz/specials"),
    ("Liquorland - promotions", "https://www.liquorland.co.nz/promotions"),
    ("Big Barrel - specials", "https://havelock.bigbarrel.co.nz/en/specials"),
    ("Big Barrel - deals", "https://havelock.bigbarrel.co.nz/en/deals"),
    ("Super Liquor - specials", "https://www.superliquor.co.nz/specials"),
    ("Super Liquor - deals", "https://www.superliquor.co.nz/deals"),
    ("Bottle-O - specials", "https://www.thebottleo.co.nz/specials"),
    ("Black Bull - specials", "https://blackbullliquorhawera.co.nz/Shop-Online/specials"),
]:
    check(label, url)

# 3. A couple more category pages per chain (spirits/wine) in case beer
# specifically just doesn't run bundles
for label, url in [
    ("Big Barrel - Havelock spirits", "https://havelock.bigbarrel.co.nz/en/spirits"),
    ("Big Barrel - Havelock wine", "https://havelock.bigbarrel.co.nz/en/wine"),
    ("Super Liquor - spirits", "https://www.superliquor.co.nz/spirits"),
    ("Super Liquor - wine", "https://www.superliquor.co.nz/wine"),
    ("Liquorland - spirits", "https://www.liquorland.co.nz/spirits"),
    ("Liquorland - wine", "https://www.liquorland.co.nz/wine"),
]:
    check(label, url)
