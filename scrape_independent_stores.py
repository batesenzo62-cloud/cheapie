"""
Cheapie — independent store scraper (no Firecrawl needed)

Covers four website platforms found across NZ independent liquor retailers:
- WooCommerce (Vino Fino) — paginates via /page/N/ path segments
- Shopify (Thirsty Liquor) — paginates via ?page=N, max page read from
  aria-label="Page N" links (no "Next" text link in the default theme)
- Hotcakes/DotNetNuke (Black Bull Liquor) — paginates via ?page=N,
  following the pager's next-page link until it disappears (the 2026-07-24
  audit only checked the four original broad categories, which happen to
  all fit under one page — several narrower categories added since do
  paginate, e.g. "whisky" runs 52+40+2 = 94 products across 3 pages;
  fixed 2026-07-25)
- nopCommerce (Super Liquor, Big Barrel) — paginates via ?pagenumber=N,
  following the pager's "Next" link until it disappears rather than
  parsing a "Last" link, since Big Barrel's pager doesn't always render one

A 2026-07-24 coverage audit (comparing scraped counts against each site's
own displayed pagination) found real catalogues running up to 198 pages
deep, while MAX_PAGES_PER_TARGET was capped at 10 — most stores were only
being scraped to a small fraction of their real range. See
MAX_PAGES_PER_TARGET below for the fix, and the TARGETS list for Big
Barrel's separately-catalogued sub-categories (confirmed non-overlapping
with its top-level pages, not just filtered views of the same list).

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
from urllib.parse import urljoin, urlparse
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
    #
    # 2026-07-24 100%-coverage pass: the three URLs above are themselves
    # mid-level categories, and their own product listing may or may not
    # include everything filed under a more specific child category (the
    # site's WooCommerce theme doesn't make this verifiable from outside,
    # and a spot check of one specific product came back inconclusive —
    # its page only showed the site's full nav widget, not real per-product
    # breadcrumbs). Rather than gamble on parent-page aggregation, every
    # leaf category in the site's nav is targeted explicitly below —
    # duplicate rows from any real parent/child overlap are harmless, since
    # load_data_to_supabase.py upserts on (store_name, product_name) and
    # de-dupes in-memory before ever sending the request.
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/beer-cider/cider/", "beer", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/non-alcoholic/", "beer", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/spirits/brandy/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/spirits/eau-de-vie/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/spirits/gin/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/spirits/grappa/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/spirits/pisco/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/spirits/rum/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/spirits/sake-umeshu/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/spirits/tequila-mezcal/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/spirits/vermouth-aperitifs/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/spirits/vodka/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/spirits/whisky/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/liqueurs/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/liqueurs/bitters/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/liqueurs/coffee-liqueur/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/liqueurs/cream-liqueur/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/liqueurs/fruit-liqueur/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/liqueurs/herbal-liqueur/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/liqueurs/nut-based-liqueur/", "spirits", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/liqueurs/whisky-based-liqueur/", "spirits", "woocommerce"),
    # Port/sherry/madeira/muscat/ginger wine are fortified WINES on this
    # site's own nav (under beers-spirits/fortified), not spirits.
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/fortified/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/fortified/ginger-wine/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/fortified/liqueur-muscat-topaque/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/fortified/madeira-marsala/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/fortified/port/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/beers-spirits/fortified/sherry/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/cabernet-franc/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/cabernet-merlot/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/cabernet-sauvignon/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/cabernet-shiraz/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/gamay/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/grenache-blend-gsm/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/grenache-garnacha/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/malbec/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/merlot/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/nebbiolo/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/other-reds/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/pinot-noir/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/primitivo-zinfandel/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/red-blends/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/sangiovese/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/syrah-shiraz/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/reds/tempranillo/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/whites/albarino/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/whites/chardonnay/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/whites/chenin-blanc/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/whites/gewurztraminer/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/whites/gruner-veltliner/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/whites/other-whites/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/whites/pinot-blanc/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/whites/pinot-gris/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/whites/rhone-blend-white/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/whites/riesling/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/whites/sauvignon-blanc/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/whites/semillon/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/whites/viognier/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/whites/white-blends/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/sparkling/cava/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/sparkling/champagne/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/sparkling/methode-traditionnelle/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/sparkling/pet-nat-ancestral-method/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/sparkling/prosecco/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/sparkling/sparkling-red/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/sparkling/sparkling-rose/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/style/chillable-reds/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/style/dessert/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/style/fortified-style/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/style/orange-style/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/style/organic-biodynamic-style/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/style/rose/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/region-wine/california/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/region-wine/rhone/", "wine", "woocommerce"),
    ("Vino Fino", "https://vinofino.co.nz/product-category/wine/country/usa/", "wine", "woocommerce"),
    ("Thirsty Liquor", "https://thirstyliquor.co.nz/collections/beer", "beer", "shopify"),
    ("Thirsty Liquor", "https://thirstyliquor.co.nz/collections/rtds", "rtd", "shopify"),
    ("Thirsty Liquor", "https://thirstyliquor.co.nz/collections/wine", "wine", "shopify"),
    ("Thirsty Liquor", "https://thirstyliquor.co.nz/collections/spirits", "spirits", "shopify"),
    # 2026-07-24: "cider"/"liqueurs"/"shots" are separate collections from
    # the four above, not filtered views of them (confirmed via the site's
    # own nav, distinct from "beer-cider"/"all-products"/"mixers", which
    # were left out as redundant with what's already targeted, or genuinely
    # non-alcoholic).
    ("Thirsty Liquor", "https://thirstyliquor.co.nz/collections/cider", "beer", "shopify"),
    ("Thirsty Liquor", "https://thirstyliquor.co.nz/collections/liqueurs", "spirits", "shopify"),
    ("Thirsty Liquor", "https://thirstyliquor.co.nz/collections/shots", "spirits", "shopify"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/beer-cider", "beer", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/rtd", "rtd", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/wine", "wine", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/spirits", "spirits", "hotcakes"),
    # 2026-07-24: the four categories above turned out to be genuinely
    # complete in themselves (single-page, ~100% match against the site's
    # own totals) — the real gap here was entirely missing categories, not
    # pagination. The site's nav has a specific page per spirit type and
    # wine colour that was never targeted at all (e.g. "spirits" alone
    # doesn't surface anything filed only under "whisky" or "gin").
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/red-wine", "wine", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/white", "wine", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/bourbon", "spirits", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/brandy", "spirits", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/gin", "spirits", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/irish", "spirits", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/irish-cream", "spirits", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/liqueurs", "spirits", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/rum", "spirits", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/tequila", "spirits", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/vodka", "spirits", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/whisky", "spirits", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/classic", "spirits", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/bourbon-rtd", "rtd", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/gin-rtd", "rtd", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/rum-rtd", "rtd", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/vodka-rtd", "rtd", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/whisky-rtd", "rtd", "hotcakes"),
    ("Black Bull Liquor", "https://blackbullliquorhawera.co.nz/Shop-Online/rtd-2", "rtd", "hotcakes"),
    ("Super Liquor", "https://www.superliquor.co.nz/beer", "beer", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/premix", "rtd", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/wine", "wine", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/spirits", "spirits", "nopcommerce"),
    # 2026-07-24: same pattern as Big Barrel below — dozens of granular
    # category pages exist on this site beyond the four broad ones above.
    ("Super Liquor", "https://www.superliquor.co.nz/beer-cider", "beer", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/beer-cider-2", "beer", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/craft-beer", "beer", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/flavoured-beer", "beer", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/international-beer", "beer", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/low-carb-beer", "beer", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/low-or-no-beer", "beer", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/new-zealand-beer", "beer", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/value-beer", "beer", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/fortified-wine", "wine", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/other-wine", "wine", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/red-wine-", "wine", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/rose-2", "wine", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/sparkling-wine", "wine", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/white-wine", "wine", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/wine-bubbles", "wine", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/wine-bubbles-2", "wine", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/bourbon", "spirits", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/brandy", "spirits", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/gin", "spirits", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/other-spirits-2", "spirits", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/rum", "spirits", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/spirits-2", "spirits", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/spirits-3", "spirits", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/tequila", "spirits", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/vodka", "spirits", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/whisky", "spirits", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/bourbon-rtd", "rtd", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/gin-rtd", "rtd", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/other-rtd", "rtd", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/rtds-2", "rtd", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/rum-rtd", "rtd", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/vodka-rtd", "rtd", "nopcommerce"),
    ("Super Liquor", "https://www.superliquor.co.nz/whisky-rtd", "rtd", "nopcommerce"),
    # Big Barrel also runs nopCommerce, and unlike Black Bull (Hawera, South
    # Taranaki) it has genuine Hawke's Bay stores (Karamu Rd Hastings,
    # Stortford Lodge, Clive, Havelock North, plus several Napier suburbs) —
    # a much better regional fit for this app.
    ("Big Barrel", "https://bigbarrel.co.nz/en/beers", "beer", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/premixed-spirit-drinks", "rtd", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/wines", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/spirits", "spirits", "nopcommerce"),
    # Big Barrel's nav has 118 distinct category pages. An earlier pass
    # covered a "substantial but not exhaustive" subset to avoid exploding
    # past what seemed scrapeable in one run — as of 2026-07-24 that
    # tradeoff is no longer the goal (100% coverage explicitly requested
    # over politeness/runtime), so the remaining categories are added below
    # too. Confirmed via spot check that at least "NZ Classic Beers" has
    # zero product overlap with the top-level /en/beers page, i.e. these
    # are genuinely separate, additive catalogues rather than filtered
    # views of the same list. Several nav labels are mismatched to their
    # own hrefs on Big Barrel's own site (e.g. "Cask Wine Range" links to
    # /en/nz-chardonnay-white-wines) — so these URLs were chosen by
    # trusting the slug itself over the on-page label text. Individual
    # store-branch pages, non-alcohol categories (tobacco, snacks, mixers,
    # glassware) and single-product detail pages that showed up in the nav
    # crawl are deliberately excluded — out of scope for a booze price
    # finder regardless of how exhaustive the rest of this list is.
    ("Big Barrel", "https://bigbarrel.co.nz/en/nz-classic-beers", "beer", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/craft-beers-2", "beer", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/lagers-of-the-world", "beer", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/australian-beer-range-2", "beer", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/other-imported-beer-range", "beer", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/flavoured-beers", "beer", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/light-beers", "beer", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/red-wines-2", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/white-wines", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/sparkling-wine-range", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/australian-red-wines", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/australian-white-wines", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/imported-red-wines", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/imported-white-wines", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/imported-sparkling-wines", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/champagnes", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/fortified-wines", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/dessert-wines", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/nz-sauvignon-blanc-white-wines", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/nz-other-white-wine-vareitals", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/whiskies", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/single-malt-whiskies", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/blended-whiskies", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/bourbons-usa-whiskey", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/canadian-whisky-range", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/irish-whiskey-range", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/gin-range", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/vodka-range", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/rum-range", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/tequila-range", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/brandies", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/cognacs", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/liqueur-range", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/vermouth-range", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/other-spirits-", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/bourbon-premixed-range", "rtd", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/gin-premixed-range", "rtd", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/rum-premixed-range", "rtd", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/tequila-premixed-range", "rtd", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/vodka-premixed-range", "rtd", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/whisky-others-premixed-range", "rtd", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/australian-beer-range", "beer", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/other-new-zealand-beer-range", "beer", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/lion-tall-bottles", "beer", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/cask-wine-range", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/new-zealand-red-wines-", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/new-zealand-sparkling-wines", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/non-alcholic-wines", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/australian-sparkling-wines", "wine", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/armagnac", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/australian-whiskies", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/calvados-region-france", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/chinese-baijiu", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/dark-rum-range", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/fortified-australian-range", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/fortified-imported-range", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/gold-rum-range", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/grappa-spirits", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/indian-whiskies", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/japanese-whiskies", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/non-alcoholic-spirits", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/schnapps", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/silver-or-white-rum-range", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/spiced-rum-range", "spirits", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/shot-premixed-range", "rtd", "nopcommerce"),
    ("Big Barrel", "https://bigbarrel.co.nz/en/non-alcoholic-premixed-range", "rtd", "nopcommerce"),
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

# Coverage audit (2026-07-24) found real catalogues up to 198 pages deep
# (Big Barrel spirits) — a cap of 10 was silently cutting most stores off
# at a fraction of their real range. 250 comfortably covers everything
# found so far while still being a real ceiling, not "no limit" (a pager
# bug that never reports "no next page" would otherwise loop forever).
# Smaller catalogues still stop naturally at their own real last page, so
# this doesn't cause any extra requests for stores that don't need them.
MAX_PAGES_PER_TARGET = 250

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


def get_max_page_woocommerce(soup):
    pager = soup.select_one(".woocommerce-pagination")
    if not pager:
        return 1
    pages = []
    for el in pager.select("a.page-numbers, span.page-numbers"):
        text = el.get_text(strip=True)
        if text.isdigit():
            pages.append(int(text))
    return max(pages) if pages else 1


def scrape_woocommerce(url):
    all_products = []
    base = url if url.endswith("/") else url + "/"
    page = 1
    while True:
        # WooCommerce paginates via a path segment (.../page/N/), not a
        # query param — confirmed against Vino Fino's actual pager links.
        page_url = base if page == 1 else f"{base}page/{page}/"
        response = requests.get(page_url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        all_products += parse_woocommerce(soup)

        max_page = get_max_page_woocommerce(soup)
        if page >= MAX_PAGES_PER_TARGET or page >= max_page:
            break
        page += 1
        time.sleep(1)

    print(f"  ({page} of {max_page} page(s) scraped)")
    return all_products


def parse_shopify(soup, base_url="https://thirstyliquor.co.nz"):
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
            link = base_url + link
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
    base_url = "{0.scheme}://{0.netloc}".format(urlparse(url))
    all_products = []
    page = 1
    while True:
        page_url = url if page == 1 else f"{url}?page={page}"
        response = requests.get(page_url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        all_products += parse_shopify(soup, base_url)

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


# Debugged 2026-07-25: Black Bull's platform genuinely has no pager at all
# on its four broad original categories (beer-cider/rtd/wine/spirits — all
# under the ~52-per-page ceiling), which is what "confirmed single-page"
# was based on — but several of the narrower categories added in the
# coverage-fix pass (e.g. "whisky": 52+40+2 = 94 real products across 3
# pages) genuinely paginate via ?page=N, and nothing here ever followed it.
# Same "follow next until it disappears" approach as nopCommerce, since the
# pager here doesn't reliably list every page number up front either (page
# 2's own pager only shows [1, 2] even though a page 3 exists).
def has_next_page_hotcakes(soup, current_page):
    for a in soup.select("a[href]"):
        m = re.search(r"[?&]page=(\d+)", a["href"])
        if m and int(m.group(1)) == current_page + 1:
            return True
    return False


def scrape_hotcakes(url):
    all_products = []
    page = 1
    while True:
        page_url = url if page == 1 else f"{url}?page={page}"
        response = requests.get(page_url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        all_products += parse_hotcakes(soup)

        if page >= MAX_PAGES_PER_TARGET or not has_next_page_hotcakes(soup, page):
            break
        page += 1
        time.sleep(1)

    print(f"  ({page} page(s) scraped)")
    return all_products


PARSERS = {
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
    elif platform == "woocommerce":
        raw_products = scrape_woocommerce(url)
    elif platform == "hotcakes":
        raw_products = scrape_hotcakes(url)
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


# Fixed field list (rather than deriving fieldnames from the first result)
# so the CSV header can be written immediately, before any target has even
# run — needed for the incremental writing below.
PRODUCT_FIELDNAMES = ["store", "category", "product_name", "price", "was_price", "in_stock", "url", "fetched_at"]


def main():
    # Written incrementally (one target's rows at a time, flushed to disk
    # immediately) rather than accumulated in memory and written once at the
    # end — a 221-target run across 6 sites can take hours, and something
    # killing the process partway through (this happened for real: the
    # machine went to sleep mid-run) used to mean every target scraped
    # before the crash was silently lost, not just the ones after it.
    total_written = 0
    with open("independent_store_prices.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PRODUCT_FIELDNAMES)
        writer.writeheader()
        for store_name, url, category, platform in TARGETS:
            print(f"Scraping {store_name} ({category}, {platform})...")
            try:
                products = scrape_one(store_name, url, category, platform)
                print(f"  Found {len(products)} products.")
                writer.writerows(products)
                f.flush()
                total_written += len(products)
            except Exception as exc:
                print(f"  Could not scrape {store_name} ({category}): {exc}")
            time.sleep(2)

    if total_written == 0:
        # Every one of 7+ independent targets failing at once means something
        # is fundamentally broken (network, IP block, etc.), not just one
        # site's markup changing — exit non-zero so this can't pass silently.
        raise SystemExit("No products found across any target. Check the sites manually.")

    print(f"Done. Wrote {total_written} products to independent_store_prices.csv")


if __name__ == "__main__":
    main()
