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

The actual scraping engine (shared with scrape_thirsty_doordash.py) is
in doordash_scraper_lib.py — this file is just the branch list.

HOW TO RUN:
    pip install playwright
    playwright install --with-deps chromium
    python3 scrape_blackbull_doordash.py
"""
import asyncio

from doordash_scraper_lib import scrape_branches, write_rows

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

STORE_PREFIX = "Black Bull Liquor"


async def main():
    new_rows = await scrape_branches(BRANCHES, STORE_PREFIX)
    scraped_store_names = {f"{STORE_PREFIX} {label}" for label, _, _ in BRANCHES}
    write_rows(new_rows, scraped_store_names)


if __name__ == "__main__":
    asyncio.run(main())
