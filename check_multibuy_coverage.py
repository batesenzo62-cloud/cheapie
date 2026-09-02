"""
One-off investigation: check each chain's real specials/deals page
directly for multi-buy wording ("2 for $X", "any 3 for $X") and for
poster/banner-image-based deals (no plain text) with or without usable
alt text. Not a permanent scraper — just gathering evidence.
"""
import re
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

MULTIBUY_RE = re.compile(r"\b(?:any\s+)?(?:\d{1,2}|two|three|four|five|six|seven|eight|twelve)\s+for\s+\$\s?\d", re.I)


def check(label, url):
    print(f"=== {label} ({url}) ===")
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"  status: {r.status_code}, len: {len(r.text)}")
        if r.status_code != 200:
            print(f"  body sample: {r.text[:200]}")
            return
        text_matches = MULTIBUY_RE.findall(r.text)
        print(f"  text multi-buy matches: {len(text_matches)}")
        for m in list(set(re.findall(r'.{0,30}' + MULTIBUY_RE.pattern + r'.{0,10}', r.text, re.I)))[:5]:
            print(f"    -> {m!r}")
        # look for promo/banner/poster images
        img_tags = re.findall(r'<img[^>]+>', r.text, re.I)
        promo_imgs = [t for t in img_tags if re.search(r'promo|banner|poster|deal|special|offer', t, re.I)]
        print(f"  total <img> tags: {len(img_tags)}, promo-like: {len(promo_imgs)}")
        for t in promo_imgs[:5]:
            alt = re.search(r'alt="([^"]*)"', t, re.I)
            src = re.search(r'src="([^"]*)"', t, re.I)
            print(f"    img src={src.group(1)[:80] if src else None} alt={alt.group(1)[:100] if alt else '(none)'}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
    print()


check("Liquorland - beer category", "https://www.liquorland.co.nz/beer")
check("Liquorland - homepage", "https://www.liquorland.co.nz/")
check("Big Barrel - Havelock North homepage", "https://havelock.bigbarrel.co.nz/")
check("Big Barrel - Havelock beers", "https://havelock.bigbarrel.co.nz/en/beers")
check("Big Barrel - corporate homepage", "https://bigbarrel.co.nz/")
check("Super Liquor homepage", "https://www.superliquor.co.nz/")
check("Super Liquor - beer", "https://www.superliquor.co.nz/beer")
check("Bottle-O national homepage", "https://www.thebottleo.co.nz/")
check("Black Bull Hawera homepage", "https://blackbullliquorhawera.co.nz/")
check("Black Bull Hawera - beer/cider", "https://blackbullliquorhawera.co.nz/Shop-Online/beer-cider")
