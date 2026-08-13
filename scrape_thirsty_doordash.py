"""
Cheapie — Thirsty Liquor DoorDash scraper.

Covers Thirsty Liquor branches that have no independent online shop of
their own but DO have a real DoorDash listing with real prices — same
approach as scrape_blackbull_doordash.py (see doordash_scraper_lib.py
for the shared scraping engine and why DoorDash specifically).

Thirsty Liquor has 138 known branches; only ~11 have their own real
Shopify site (scrape_thirsty_branches.py's hardcoded list). Of the
remaining ~127, only these 7 were confirmed live with an unambiguous
name/address match — many DoorDash listings exist under generic names
like "Thirsty Liquor" or "Thirsty Liquor Auckland" shared by several
different physical branches in the stores table, and those were
deliberately left out rather than guess which one a listing actually
belongs to (same reasoning as Black Bull's DoorDash scraper). One
listing found (Thirsty Liquor Linwood, matching "Thirsty Liquor
Christchurch" in the stores table) turned out to be confirmed inactive
on DoorDash itself ("not available on DoorDash right now") and was
excluded for that reason too.

Note: "Thirsty Liquor Papanui" exists twice in the stores table under
two different store_ids at the same address (495 Papanui Road/Rd,
Christchurch) — a real duplicate, same pattern as Black Bull Liquor
Hawera/High St found and merged earlier. This scraper attaches to only
one of the two ids (13825b74-2c9b-4564-9c79-f812767c90dc); the other
(2edc9558-fb60-4b9c-8707-4b38b7b211bb) should be merged/removed the same
way, but wasn't done yet — flagging here rather than silently leaving it
inconsistent.

HOW TO RUN:
    pip install playwright
    playwright install --with-deps chromium
    python3 scrape_thirsty_doordash.py
"""
import asyncio

from doordash_scraper_lib import scrape_branches, write_rows

BRANCHES = [
    ("Sliverdale", "d1e06bd3-0d37-4e39-b259-1e5e5d190428", "https://www.doordash.com/store/thirsty-liquor-silverdale-31062164/"),
    ("Napier", "4a4142b5-d85a-4d66-a998-1b90e0ec3ab0", "https://www.doordash.com/store/thirsty-liquor-30894047/"),
    ("Takapuna", "b260a41d-c4ed-4d72-9744-3d7cebc7382d", "https://www.doordash.com/en/store/thirsty-liquor-takapuna-25069953/"),
    ("Wordsworth", "c4be313b-c117-426f-bc95-85548827492f", "https://www.doordash.com/en/store/manurewa:-thirsty-liquor-auckland-27568313/"),
    ("Victoria Street", "7865d1ab-e34f-4b6d-90e7-b82daf203b34", "https://www.doordash.com/en-NZ/store/thirsty-liquor-(victoria-street)-christchurch-24077735/"),
    ("Papanui", "13825b74-2c9b-4564-9c79-f812767c90dc", "https://www.doordash.com/store/thirsty-liquor-christchurch-24687391/"),
    ("Remuera", "5acc442a-6b52-46ec-b0e5-a43809b2bc84", "https://www.doordash.com/store/thirsty-liquor-auckland-26192048/"),
]

STORE_PREFIX = "Thirsty Liquor"


async def main():
    new_rows = await scrape_branches(BRANCHES, STORE_PREFIX)
    scraped_store_names = {f"{STORE_PREFIX} {label}" for label, _, _ in BRANCHES}
    write_rows(new_rows, scraped_store_names)


if __name__ == "__main__":
    asyncio.run(main())
