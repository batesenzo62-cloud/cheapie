"""
Cheapie — Black Bull Liquor DoorDash scraper.

Covers Black Bull branches that have no independent online shop of their
own but DO have a real DoorDash listing with real prices — confirmed
directly for these 6 branches (checked live, one by one, address/name
matched with confidence; several other candidate DoorDash listings were
found under ambiguous names like "Black Bull Liquor (Auckland)" or
"(Hamilton)" with no confirmable street address, and were deliberately
left out rather than risk attributing another branch's real prices to
the wrong store — see the confirmedBranch/nearest-neighbour work this
whole app already relies on for why that's worth being careful about).

Requires a real browser, not plain requests/BeautifulSoup like every
other scraper in this app — confirmed directly: DoorDash returns 403
(Cloudflare) to a plain HTTP GET, and Uber Eats (checked first) refuses
to return any product data at all without a validated delivery address
already set, which its own address-autocomplete UI proved too fragile to
automate reliably. DoorDash needs no address and no age-gate interaction
to show real prices, just a real browser to get past Cloudflare.

The menu is a virtualized list — only ~16 items are ever actually in the
DOM at once, even though a category can have 100+. Confirmed directly:
naive scrolling only ever captured the first ~16 items total, no matter
how much you scrolled, because scrolling past a category unmounts its
DOM nodes as new ones mount. Fixed by scrolling to each category's own
anchor (from the page's Apollo GraphQL cache, which lists every
category's real item count up front) and extracting+accumulating
whatever's rendered after each small scroll step within that category,
stopping once the running total for that category reaches its real
known item count (or plateaus for a few rounds, in case the true count
is off by one or two from what actually renders).

HOW TO RUN:
    pip install playwright
    playwright install --with-deps chromium
    python3 scrape_blackbull_doordash.py
"""
import asyncio
import csv
import os
import re
import time

from playwright.async_api import async_playwright

DEFAULT_FIELDNAMES = ["store", "store_id", "category", "product_name", "price", "was_price", "in_stock", "url", "fetched_at"]

# (branch label, real Supabase store_id, DoorDash store URL) — only
# branches confirmed live with an unambiguous name/address match. Do NOT
# add a branch here just because a DoorDash listing exists under a
# generic city name ("Black Bull Liquor (Auckland)") — confirm the exact
# street address matches first, or it silently becomes exactly the
# wrong-branch-price bug this app has spent a long time fixing.
BRANCHES = [
    ("Napier", "72722bbb-8ad9-4b0d-8f2a-d42841aea8ef", "https://www.doordash.com/en-NZ/store/black-bull-liquor-napier-31114651/"),
    ("Royal Oak", "b372a9db-560a-4143-a4e3-c67b1db65816", "https://www.doordash.com/store/black-bull-liquor-royal-oak-auckland-33474711/"),
    ("Paraparaumu", "4de95caa-3df8-48f8-bfc8-e9a40097c78e", "https://www.doordash.com/store/black-bull-liquor-paraparaumu-30652606/"),
    ("Whitby", "37b6c687-1c7d-4991-8c36-ec42762d26ac", "https://www.doordash.com/en-NZ/store/black-bull-whitby-porirua-23964654/"),
    ("Peachgrove Road", "00cbb9f6-4151-4768-8ff2-0e831bbfebef", "https://www.doordash.com/store/black-bull-liquor-peachgrove-road-28035785/"),
    ("Main Steet", "fb80a5e6-ed9f-4f7f-b5d7-5386f3b68298", "https://www.doordash.com/en/store/black-bull-liquor-palmerston-north-28839983/"),
]

# DoorDash's own category names -> this app's 4-category taxonomy. Same
# beer/wine/spirits/rtd convention every other scraper in this app uses
# (cider -> beer, premix -> rtd, etc.). Confirmed directly: different
# Black Bull branches structure their DoorDash menu completely
# differently — Napier splits Beer/Wine/Spirits/RTD into ~13 named
# sections, Palmerston North (spirits-only store) breaks spirits down
# into per-spirit-type sections (Whisky, Vodka, Gin, ...) with no single
# "Spirits" section at all, and Royal Oak has no sections whatsoever
# (one flat "Alcoholic Beverages" catch-all — see CATCHALL_CATEGORY_NAMES
# below for how that case is handled instead).
CATEGORY_MAP = {
    "ciders": "beer",
    "beers": "beer",
    "beer": "beer",
    "pre mixed": "rtd",
    "rtd": "rtd",
    "rtds": "rtd",
    "white wine": "wine",
    "red wine": "wine",
    "sparkling": "wine",
    "rose": "wine",
    "rosé": "wine",
    "fortified wine": "wine",
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
# store's real categories (or, for Most Ordered/Popular Items on a store
# with no other category breakdown at all, would need their own guess at
# a category anyway) — skipped rather than double-processed.
SKIP_CATEGORY_NAMES = {"most ordered", "popular items", "featured items", "trending products", "best sellers"}


def map_category(doordash_name):
    key = (doordash_name or "").strip().lower()
    return CATEGORY_MAP.get(key)  # None (dropped) for snacks/accessories/soft drinks — not real liquor products this app compares


# 2026-08-14: confirmed directly — not every branch's DoorDash page breaks
# its menu into Beer/Wine/Spirits/RTD sections the way Napier's does.
# Royal Oak's whole menu is one single "Alcoholic Beverages" bucket (60
# items) with no per-category split at all, so CATEGORY_MAP alone would
# drop every one of its products. Falls back to classifying each product
# by its own name instead, for exactly this catch-all case — checked in
# order below (wine/beer keywords first, since e.g. "cider" could
# otherwise false-match a "spirit" keyword substring in a longer name).
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
    # 2026-08-14 fix: reported directly — "Fat Bird Sauv Blanc" (wine) and
    # "Long White Hazy Lemonade" (RTD) both came out tagged "beer",
    # because DoorDash's category anchor elements are lazily mounted —
    # confirmed directly querying one right after page load returned
    # nothing at all — so the "which category was I scrolled to when this
    # rendered" signal isn't reliable at a section boundary; a couple of
    # the next section's cards render in the same viewport before the
    # count-based stop condition catches it. The keyword classifier is
    # immune to this (it only looks at the product's own name), so it
    # wins whenever it has an opinion; the anchor-based category is only
    # the fallback, for the (majority) of items with no keyword match.
    resolved_category = classify_by_keywords(name) or category
    if not resolved_category:
        return None  # catch-all category, name gave no confident signal — dropped rather than guessed wrong
    return {
        "product_name": name,
        "price": price_match.group(1),
        "category": resolved_category,
    }


async def main():
    new_rows = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for label, store_id, url in BRANCHES:
            store_name = f"Black Bull Liquor {label}"
            print(f"Scraping {store_name} (DoorDash)...")
            # A fresh page per store — confirmed directly reusing one page
            # across navigations sometimes left window.__APOLLO_CLIENT__
            # uninitialized on the next store's page (Royal Oak failed
            # with "Cannot read properties of undefined (reading
            # 'extract')" this way; a clean page per store didn't).
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                viewport={"width": 1280, "height": 1200},
            )
            try:
                # A real, occasional transient — confirmed directly a
                # store that scraped fine on one run came back with 0
                # items on the next, no error raised, just slow/incomplete
                # rendering that round. One retry after a real pause
                # clears it, same treatment already used elsewhere in
                # this app for this exact kind of flakiness.
                raw_items = await scrape_store(page, url)
                if not raw_items:
                    print("  0 items first try, retrying once...")
                    await asyncio.sleep(8)
                    raw_items = await scrape_store(page, url)
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
            except Exception as e:
                print(f"  Could not scrape {store_name}: {e}")
            await page.close()
            await asyncio.sleep(4)  # polite delay between stores
        await browser.close()

    print(f"\nTotal fresh DoorDash rows: {len(new_rows)}")

    scraped_store_names = {f"Black Bull Liquor {label}" for label, _, _ in BRANCHES}
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


if __name__ == "__main__":
    asyncio.run(main())
