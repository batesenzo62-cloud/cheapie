"""
Cheapie — independent store scraper (no Firecrawl needed)

Covers four website platforms found across NZ independent liquor retailers:
- WooCommerce (Vino Fino)
- Shopify (Thirsty Liquor)
- Hotcakes/DotNetNuke (Black Bull Liquor)
- nopCommerce (Super Liquor, Big Barrel) — the only platform here with real
  pagination; the others are scraped one page deep only. Pagination works by
  following the pager's "Next" link until it disappears (or MAX_PAGES_PER_TARGET
  is hit) rather than parsing a "Last" link, because Big Barrel's pager doesn't
  always render one.

Each platform uses different HTML structure, so each has its own parser
below. If a store returns 0 products, that store's website likely uses
slightly different class names than expected — that's normal, share the
output with Claude and it can be adjusted.

HOW TO RUN:
    pip install -r requirements.txt
    python3 scrape_independent_stores.py

Output: independent_store_prices.csv (now includes a "category" column)
"""

import csv
import re
import time
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup

# Each target: (store_name, url, category, platform)
# Wine/spirits URLs added 2026-07-23 — verified to return HTTP 200 (these
# sites are plain server-rendered HTML, so a 200 here is a much stronger
# signal than it was for the JS-rendered chain stores).
# Super Liquor (nopCommerce) added 2026-07-23, using the "full range" URLs
# rather than the "specials" ones for broader catalogue coverage.
# Drinkland removed 2026-07-23 — it's an online-only retailer (their own
# site brands it "NZ online liquor store") with no physical shop customers
# can walk into, which doesn't fit this app's physical-store scope. Vino
# Fino, by contrast, has a real Christchurch storefront (188 Durham St
# South) so it stays.
TARGETS = [
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/beer-cider/craft-beer/", "beer", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/spirits/", "spirits", "woocommerce"),
    # No RTD entry: checked their beers-spirits subcategories directly
    # (beer-cider, cider, craft-beer, liqueurs, non-alcoholic, spirits) —
    # there's no RTD/premix range on this site at all. Real absence, not a
    # missed URL.
    ("Thirsty Liquor", "https://thirstyliquor.co.nz/collections/beer", "beer", "shopify"),
    ("Thirsty Liquor", "https://thirstyliquor.co.nz/collections/rtds", "rtd", "shopify"),
    ("Thirsty Liquor", "https://thirstyliquor.co.nz/collections/wine", "wine", "shopify"),
    ("Thirsty Liquor", "https://thirstyliquor.co.nz/collections/spirits", "spirits", "shopify"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/beer-cider", "beer", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/rtd", "rtd", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/wine", "wine", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/spirits", "spirits", "hotcakes"),
    ("Super Liquor", "https://www.superliquor.co.nz/beer", "beer", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/premix", "rtd", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/wine", "wine", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/spirits", "spirits", "nopcommerce"),
    # Big Barrel also runs nopCommerce, and unlike Black Bull (Hawera, South
    # Taranaki) it has genuine Hawke's Bay stores (Karamu Rd Hastings,
    # Stortford Lodge, Clive, Havelock North, plus several Napier suburbs) —
    # a much better regional fit for this app.
    ("Big Barrel", "https://bigbarrel.co.nz/en/beers", "beer", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/premixed-spirit-drinks", "rtd", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/wines", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/spirits", "spirits", "nopcommerce"),
    # Glengarry is a custom JSP platform with no clean category-browse URLs
    # (the plain category pages are 4-item landing pages) — but its /search
    # endpoint takes a GET param and returns every matching product on one
    # unpaginated page, so it's used as a de facto category browse instead.
    # "spirits" itself matches nothing (it's not a word in product names),
    # hence the specific spirit-type terms below.
    ("Glengarry", "https://www.glengarrywines.co.nz/search?criteria=beer", "beer", "glengarry"),
    ("Glengarry", "https://www.glengarrywines.co.nz/search?criteria=rtd", "rtd", "glengarry"),
    ("Glengarry", "https://www.glengarrywines.co.nz/search?criteria=wine", "wine", "glengarry"),
    ("Glengarry", "https://www.glengarrywines.co.nz/search?criteria=whisky", "spirits", "glengarry"),
    ("Glengarry", "https://www.glengarrywines.co.nz/search?criteria=vodka", "spirits", "glengarry"),
    ("Glengarry", "https://www.glengarrywines.co.nz/search?criteria=gin", "spirits", "glengarry"),
]

# Super Liquor's ranges run 20-40 pages deep per category (12 products/page).
# Scraping all of them on every run would be ~2,600 requests total across 4
# categories and isn't polite to their server, so each category is capped
# here. Raise this if deeper coverage is worth the extra load/runtime.
MAX_PAGES_PER_TARGET = 10

HEADERS = {
    "User-Agent": "CheapiePriceBot/0.1 (+contact: youremail@example.com)"
}


def parse_woocommerce(soup):
    products = []
    for item in soup.select("li.product, div.product"):
        name_el = item.select_one(".woocommerce-loop-product__title, h2, h3")
        name = name_el.get_text(strip=True) if name_el else None
        price_el = item.select_one("span.price")
        sale_price, was_price = None, None
        if price_el:
            ins = price_el.select_one("ins .woocommerce-Price-amount, ins")
            del_ = price_el.select_one("del .woocommerce-Price-amount, del")
            if ins and del_:
                sale_price, was_price = ins.get_text(strip=True), del_.get_text(strip=True)
            else:
                amount = price_el.select_one(".woocommerce-Price-amount")
                sale_price = amount.get_text(strip=True) if amount else price_el.get_text(strip=True)
        link_el = item.select_one("a")
        link = link_el["href"] if link_el and link_el.has_attr("href") else None
        out_of_stock = bool(item.select_one(".outofstock, .out-of-stock"))
        if name:
            products.append({"name": name, "price": sale_price, "was_price": was_price,
                              "in_stock": not out_of_stock, "url": link})
    return products


def parse_shopify(soup):
    products = []
    # li.grid__item is the outer product wrapper and always contains a nested
    # [class*='product-card'] div — selecting both matched every product
    # twice. Prefer the outer wrapper; only fall back to the inner card
    # class if a theme doesn't use grid__item at all.
    candidates = soup.select("li.grid__item") or soup.select("[class*='product-card']")
    for item in candidates:
        name_el = item.select_one("[class*='card__heading'], h3, h2")
        name = name_el.get_text(strip=True) if name_el else None
        if not name:
            continue
        # The theme always renders both a "regular" and a "sale" price block
        # per item, even when nothing is discounted — so a substring match on
        # 'price__sale' was picking up hidden accessibility label text
        # ("Regular priceSale price...") concatenated with the real number,
        # which corrupts anything parsed out of it downstream. The actual
        # charged price is reliably in .price__regular .price-item--regular;
        # the pre-discount price only has real text in the crossed-out
        # <s class="price-item--regular"> inside .price__sale when an item
        # is genuinely on sale (that element exists-but-empty otherwise).
        price_container = item.select_one(".price")
        sale_price, was_price = None, None
        if price_container:
            regular_span = price_container.select_one(".price__regular .price-item--regular")
            sale_price = regular_span.get_text(strip=True) if regular_span else None
            crossed_out = price_container.select_one(".price__sale s.price-item--regular")
            if crossed_out and crossed_out.get_text(strip=True):
                was_price = crossed_out.get_text(strip=True)
        if not sale_price:
            # Non-product promo tiles ("Select Your Region", "Order Online",
            # etc.) share this same grid class but never have a price — this
            # filters those out too.
            continue
        link_el = item.select_one("a")
        link = link_el["href"] if link_el and link_el.has_attr("href") else None
        if link and link.startswith("/"):
            link = "https://thirstyliquor.co.nz" + link
        products.append({"name": name, "price": sale_price, "was_price": was_price,
                          "in_stock": True, "url": link})
    return products


def get_max_page_shopify(soup):
    # Shopify's default pagination only renders numbered page links (no
    # "Next" text link to follow), so the max page number has to be read
    # directly out of the aria-label="Page N" links instead.
    pager = soup.select_one(".pagination")
    if not pager:
        return 1
    pages = []
    for a in pager.select("a[aria-label]"):
        match = re.match(r"Page (\d+)", a.get("aria-label", ""))
        if match:
            pages.append(int(match.group(1)))
    return max(pages) if pages else 1


def scrape_shopify(url):
    all_products = []
    page = 1
    while True:
        page_url = url if page == 1 else f"{url}?page={page}"
        response = requests.get(page_url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        all_products += parse_shopify(soup)

        max_page = get_max_page_shopify(soup)
        if page >= MAX_PAGES_PER_TARGET or page >= max_page:
            break
        page += 1
        time.sleep(1)

    print(f"  ({page} of {max_page} page(s) scraped)")
    return all_products


def parse_hotcakes(soup):
    products = []
    for name_el in soup.select("h2"):
        name = name_el.get_text(strip=True)
        if not name or len(name) < 3:
            continue
        price_text = None
        sib = name_el.find_next(string=lambda s: s and "$" in s)
        if sib:
            price_text = sib.strip()
        out_of_stock = False
        prev_text = name_el.find_previous(string=lambda s: s and "OUT OF STOCK" in s.upper())
        if prev_text and name_el.find_previous("h2") is None:
            out_of_stock = True
        link_el = name_el.find_previous("a")
        link = link_el["href"] if link_el and link_el.has_attr("href") else None
        if price_text or out_of_stock:
            products.append({"name": name, "price": price_text, "was_price": None,
                              "in_stock": not out_of_stock, "url": link})
    return products


def parse_glengarry(soup):
    # Each card shows brand + title separately, and the price block toggles
    # between a plain "$X.XX" (no discount) and "WAS $X.XX" / "NOW $X.XX"
    # (on sale) — both live in the same two div slots either way.
    products = []
    for slot in soup.select(".productDisplaySlot"):
        brand_el = slot.select_one(".fontProductHead a")
        title_el = slot.select_one(".fontProductHeadSub a")
        brand = brand_el.get_text(strip=True) if brand_el else ""
        title = title_el.get_text(" ", strip=True) if title_el else ""
        name = f"{brand} {title}".strip()
        if not name:
            continue

        price_el = slot.select_one(".fontProductPrice")
        price_text = price_el.get_text(strip=True).replace("NOW", "").strip() if price_el else None

        was_el = slot.select_one(".bold.fontProductPriceSub")
        was_text = was_el.get_text(strip=True).replace("WAS", "").strip() if was_el else None
        was_text = was_text or None

        link_el = title_el or slot.select_one("a[href*='/items/']")
        link = link_el["href"] if link_el and link_el.has_attr("href") else None
        if link and link.startswith("/"):
            link = "https://www.glengarrywines.co.nz" + link

        if price_text:
            products.append({"name": name, "price": price_text, "was_price": was_text,
                              "in_stock": True, "url": link})
    return products


PARSERS = {
    "woocommerce": parse_woocommerce,
    "hotcakes": parse_hotcakes,
    "glengarry": parse_glengarry,
}


def parse_nopcommerce_page(soup, page_url):
    # Two nopCommerce stores, two different price-rendering behaviours:
    # - Big Barrel prints the real price directly in static HTML
    #   (div.price.actual-price).
    # - Super Liquor renders that same element empty and fills it in
    #   client-side — but the real price is always present server-side
    #   inside each item's GA4 dataLayer <script> tag, so we fall back to
    #   reading it from there when the visible element is empty.
    products = []
    for item in soup.select("div.item-box"):
        name_el = item.select_one(".product-title a, h2.product-title")
        price_el = item.select_one(".prices .actual-price, .price.actual-price")
        price_text = price_el.get_text(strip=True) if price_el else ""

        if price_text:
            name = name_el.get_text(strip=True) if name_el else None
            price = price_text
        else:
            script = item.find("script")
            script_text = script.get_text() if script else ""
            match = re.search(r'item_name:"([^"]+)".*?price:([\d.]+)', script_text)
            name, price = match.groups() if match else (None, None)

        if not name or not price:
            continue

        was_el = item.select_one(".prices .old-price, .old-price")
        was_price = was_el.get_text(strip=True) if was_el else None

        link_el = item.select_one(".product-title a, .picture a")
        link = urljoin(page_url, link_el["href"]) if link_el and link_el.has_attr("href") else None

        products.append({"name": name, "price": price, "was_price": was_price,
                          "in_stock": True, "url": link})
    return products


def has_next_page(soup):
    pager = soup.select_one(".pager")
    if not pager:
        return False
    return any(a.get_text(strip=True).lower() == "next" for a in pager.select("a"))


def scrape_nopcommerce(url):
    all_products = []
    page = 1
    while True:
        page_url = url if page == 1 else f"{url}?pagenumber={page}"
        response = requests.get(page_url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        all_products += parse_nopcommerce_page(soup, page_url)

        if page >= MAX_PAGES_PER_TARGET or not has_next_page(soup):
            break
        page += 1
        time.sleep(1)

    print(f"  ({page} page(s) scraped)")
    return all_products


def scrape_one(store_name, url, category, platform):
    if platform == "nopcommerce":
        raw_products = scrape_nopcommerce(url)
    elif platform == "shopify":
        raw_products = scrape_shopify(url)
    else:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        parser = PARSERS[platform]
        raw_products = parser(soup)

    results = []
    for p in raw_products:
        results.append({
            "store": store_name,
            "category": category,
            "product_name": p["name"],
            "price": p["price"],
            "was_price": p["was_price"],
            "in_stock": p["in_stock"],
            "url": p["url"],
            "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
        })
    return results


def main():
    all_products = []
    for store_name, url, category, platform in TARGETS:
        print(f"Scraping {store_name} ({category}, {platform})...")
        try:
            products = scrape_one(store_name, url, category, platform)
            print(f"  Found {len(products)} products.")
            all_products.extend(products)
        except Exception as exc:
            print(f"  Could not scrape {store_name} ({category}): {exc}")
        time.sleep(2)

    if not all_products:
        # Every one of 7+ independent targets failing at once means something
        # is fundamentally broken (network, IP block, etc.), not just one
        # site's markup changing — exit non-zero so this can't pass silently.
        raise SystemExit("No products found across any target. Check the sites manually.")

    with open("independent_store_prices.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_products[0].keys())
        writer.writeheader()
        writer.writerows(all_products)

    print(f"Done. Wrote {len(all_products)} products to independent_store_prices.csv")


if __name__ == "__main__":
    main()
