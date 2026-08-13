"""
Cheapie — shared DoorDash scraping engine.

Extracted from scrape_blackbull_doordash.py once a second chain
(Thirsty Liquor) needed the exact same logic — see that file's original
docstring (still the fuller explanation, kept there since it was written
against the first real branch investigated) for why DoorDash specifically,
why a real browser is required, why the menu needs per-category anchor
scrolling rather than naive scrolling, and why the keyword classifier
takes priority over the anchor-based category.

Each chain-specific scraper (scrape_blackbull_doordash.py,
scrape_thirsty_doordash.py, ...) only needs its own BRANCHES list and
store name prefix — everything else here is chain-agnostic.

HOW TO RUN (from a chain-specific scraper):
    pip install playwright
    playwright install --with-deps chromium
"""
import asyncio
import csv
import os
import re
import time

from playwright.async_api import async_playwright

DEFAULT_FIELDNAMES = ["store", "store_id", "category", "product_name", "price", "was_price", "in_stock", "url", "fetched_at"]

# DoorDash's own category names -> this app's 4-category taxonomy. Same
# beer/wine/spirits/rtd convention every other scraper in this app uses
# (cider -> beer, premix -> rtd, etc.). Confirmed directly across two
# different chains: different branches structure their DoorDash menu
# completely differently — granular Beer/Wine/Spirits/RTD sections;
# per-spirit-type sections (Whisky, Vodka, Gin, ...) with no top-level
# "Spirits" at all; or one flat "Alcoholic Beverages" catch-all with no
# sections whatsoever (see CATCHALL_CATEGORY_NAMES below for that case).
CATEGORY_MAP = {
    "ciders": "beer",
    "cider": "beer",
    "beers": "beer",
    "beer": "beer",
    "pre mixed": "rtd",
    "rtd": "rtd",
    "rtds": "rtd",
    "premix": "rtd",
    "white wine": "wine",
    "red wine": "wine",
    "sparkling": "wine",
    "rose": "wine",
    "rosé": "wine",
    "fortified wine": "wine",
    "wine": "wine",
    "spirits": "spirits",
    "liqueurs": "spirits",
    "liqueur": "spirits",
    "whisky": "spirits",
    "whiskey": "spirits",
    "vodka": "spirits",
    "gin": "spirits",
    "rum": "spirits",
    "tequila": "spirits",
    "brandy/cognac": "spirits",
    "brandy": "spirits",
    "cognac": "spirits",
    "bourbon": "spirits",
    "scotch": "spirits",
}

# Duplicate-summary sections that repeat items already covered by the
# store's real categories — skipped rather than double-processed.
SKIP_CATEGORY_NAMES = {"most ordered", "popular items", "featured items", "trending products", "best sellers"}

CATCHALL_CATEGORY_NAMES = {"alcoholic beverages", "alcohol", "liquor", "drinks"}

WINE_KEYWORDS = (
    "wine", "sauv", "sauvignon", "pinot", "merlot", "chardonnay", "shiraz", "riesling", "rose", "rosé",
    "champagne", "prosecco", "cabernet", "moscato", "malbec", "villa maria", "brancott", "blanc",
    "oyster bay", "wither hills", "stoneleigh", "mission estate", "church road", "cloudy bay",
    "jacob's creek", "jacobs creek", "hardys", "mcguigan", "penfolds", "wolf blass", "yellow tail",
    "grant burge", "matua", "montana", "lindauer", "deutz",
)
BEER_KEYWORDS = (
    "beer", "lager", "ale", "pilsner", "pils", "stout", "cider", "ipa", "steinlager", "heineken",
    "export gold", "export 33", "tui", "monteith", "db draught", "db export", "krombacher",
    "corona", "peroni", "carlsberg", "amstel", "asahi", "somersby", "isaac's", "isaacs", "scrumpy",
    "old mout", "rekorderlig", "bulmers", "james boag", "speight",
)
SPIRITS_KEYWORDS = (
    "vodka", "gin", "whisky", "whiskey", "rum", "tequila", "brandy", "cognac", "liqueur", "bourbon",
    "scotch", "smirnoff", "absolut", "bacardi", "jim beam", "jameson", "jack daniel", "johnnie walker",
    "malibu", "baileys", "bailey's", "kahlua", "grey goose", "ballantine", "chivas", "canadian club",
    "southern comfort", "captain morgan", "havana club", "malfy", "bombay", "tanqueray", "beefeater",
    "hendrick", "glenfiddich", "glenmorangie", "dewar", "coruba", "42 below",
)
RTD_KEYWORDS = (
    "cruiser", "rtd", "smirnoff ice", "kgb", "woodstock", "cody", "seltzer", "premix", "vodka cross",
    "billy mav", "sub zero", "bacardi breezer", "long white", "vb gold", "boss lemon", "vodka guarana",
    "nitro", "mixed bag", "mystery box",
)


def map_category(doordash_name):
    key = (doordash_name or "").strip().lower()
    return CATEGORY_MAP.get(key)  # None (dropped) for snacks/accessories/soft drinks — not real liquor products this app compares


def classify_by_keywords(product_name):
    name = (product_name or "").lower()
    for kw in RTD_KEYWORDS:
        if kw in name:
            return "rtd"
    for kw in WINE_KEYWORDS:
        if kw in name:
            return "wine"
    for kw in BEER_KEYWORDS:
        if kw in name:
            return "beer"
    for kw in SPIRITS_KEYWORDS:
        if kw in name:
            return "spirits"
    return None  # genuinely can't tell — dropped rather than guessed wrong


async def dismiss_age_gate(page):
    for label in ("Yes, I am 18 years of age or older", "I'm 18 or older"):
        try:
            btn = page.locator(f'button:has-text("{label}")').first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await page.wait_for_timeout(1200)
                return
        except Exception:
            pass


async def scrape_store(page, url):
    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)
    await dismiss_age_gate(page)

    # Confirmed directly (Black Bull's first real CI run): a fixed wait
    # isn't reliable for window.__APOLLO_CLIENT__ to exist — failed for
    # 5 of 6 branches in GitHub Actions specifically, worked fine locally.
    # Poll for it instead of gambling on a flat delay being long enough.
    await page.wait_for_function(
        "() => window.__APOLLO_CLIENT__ && typeof window.__APOLLO_CLIENT__.extract === 'function'",
        timeout=20000,
    )

    cats = await page.evaluate(
        """
        () => {
            const cache = window.__APOLLO_CLIENT__.extract();
            return Object.values(cache)
                .filter(v => v && v.__typename === 'MenuBookCategory')
                .map(v => ({ name: v.name, numItems: v.numItems, anchor: v.next ? v.next.anchor : null }));
        }
        """
    )

    async def extract_rendered():
        return await page.evaluate(
            """
            () => {
                const cards = Array.from(document.querySelectorAll('[data-testid="MenuItem"]'));
                return cards.map(c => {
                    const priceEl = c.querySelector('[data-testid="StoreMenuItemPrice"]');
                    return { price_text: priceEl ? priceEl.innerText : null, full_text: (c.innerText || '').slice(0, 300) };
                });
            }
            """
        )

    seen_all = {}
    for cat in cats:
        anchor = cat.get("anchor")
        name_key = (cat["name"] or "").strip().lower()
        if name_key in SKIP_CATEGORY_NAMES:
            continue
        app_category = map_category(cat["name"])
        is_catchall = name_key in CATCHALL_CATEGORY_NAMES
        if not anchor or (not app_category and not is_catchall):
            continue

        try:
            await page.evaluate(
                f"""() => {{ const el = document.getElementById('{anchor}'); if (el) el.scrollIntoView({{block: 'start'}}); }}"""
            )
        except Exception:
            continue
        await page.wait_for_timeout(700)

        cat_seen = set()
        stable_rounds = 0
        for _ in range(25):
            for it in await extract_rendered():
                key = it["full_text"]
                if key not in cat_seen:
                    cat_seen.add(key)
                    if key not in seen_all:
                        seen_all[key] = {**it, "category": app_category}
            if len(cat_seen) >= cat["numItems"]:
                break
            prev = len(cat_seen)
            await page.mouse.wheel(0, 500)
            await page.wait_for_timeout(400)
            if len(cat_seen) == prev:
                stable_rounds += 1
                if stable_rounds >= 3:
                    break
            else:
                stable_rounds = 0

    return list(seen_all.values())


def parse_item(raw, category):
    lines = [l.strip() for l in raw["full_text"].split("\n") if l.strip()]
    if not lines:
        return None
    name = lines[0]
    price_text = raw.get("price_text") or (lines[-1] if lines else "")
    price_match = re.search(r"(\d+\.\d{2})", (price_text or "").replace(",", ""))
    if not price_match:
        return None
    # Confirmed directly (Black Bull Paraparaumu): category anchor
    # elements are lazily mounted, so scroll position isn't a fully
    # reliable signal for which category an item belongs to at a section
    # boundary ("Fat Bird Sauv Blanc" and "Long White Hazy Lemonade" both
    # came out tagged "beer" this way). The keyword classifier is immune
    # to this — it only looks at the product's own name — so it wins
    # whenever it has an opinion; the anchor-based category is only the
    # fallback, for the (majority) of items with no keyword match.
    resolved_category = classify_by_keywords(name) or category
    if not resolved_category:
        return None  # catch-all category, name gave no confident signal — dropped rather than guessed wrong
    return {
        "product_name": name,
        "price": price_match.group(1),
        "category": resolved_category,
    }


async def scrape_branches(branches, store_prefix):
    """branches: list of (label, store_id, doordash_url). Returns new_rows list."""
    new_rows = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for label, store_id, url in branches:
            store_name = f"{store_prefix} {label}"
            print(f"Scraping {store_name} (DoorDash)...")
            # A fresh page per store — confirmed directly reusing one page
            # across navigations sometimes left window.__APOLLO_CLIENT__
            # uninitialized on the next store's page.
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                viewport={"width": 1280, "height": 1200},
            )
            # A real, recurring transient — confirmed directly across both
            # a plain "0 items, no error" case and an outright exception
            # (Apollo Client not ready — failed for 5 of 6 branches in one
            # real GitHub Actions run, not just a one-off). One retry
            # after a real pause, on a fresh page.
            raw_items = []
            for attempt in (1, 2):
                try:
                    raw_items = await scrape_store(page, url)
                    if raw_items:
                        break
                    print(f"  0 items (attempt {attempt})")
                except Exception as e:
                    print(f"  Attempt {attempt} failed: {e}")
                if attempt == 1:
                    await page.close()
                    await asyncio.sleep(8)
                    page = await browser.new_page(
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                        viewport={"width": 1280, "height": 1200},
                    )

            fetched_at = time.strftime("%Y-%m-%d %H:%M")
            count = 0
            for raw in raw_items:
                parsed = parse_item(raw, raw["category"])
                if not parsed:
                    continue
                new_rows.append({
                    "store": store_name,
                    "store_id": store_id,
                    "category": parsed["category"],
                    "product_name": parsed["product_name"],
                    "price": parsed["price"],
                    "was_price": "",
                    "in_stock": "True",
                    "url": url,  # DoorDash doesn't expose a per-product URL, the store page is the closest real link
                    "fetched_at": fetched_at,
                })
                count += 1
            print(f"  Found {count} products.")
            await page.close()
            await asyncio.sleep(4)  # polite delay between stores
        await browser.close()
    return new_rows


def write_rows(new_rows, scraped_store_names):
    print(f"\nTotal fresh DoorDash rows: {len(new_rows)}")

    if os.path.exists("independent_store_prices.csv"):
        with open("independent_store_prices.csv") as f:
            fieldnames = next(csv.reader(f))
        existing = list(csv.DictReader(open("independent_store_prices.csv")))
    else:
        fieldnames = DEFAULT_FIELDNAMES
        existing = []
    kept = [row for row in existing if row["store"] not in scraped_store_names]

    all_rows = kept + new_rows
    with open("independent_store_prices.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    if not new_rows:
        raise SystemExit("No products found across any DoorDash branch — check the branches manually.")

    print(f"Wrote {len(all_rows)} total rows ({len(new_rows)} fresh DoorDash rows)")
