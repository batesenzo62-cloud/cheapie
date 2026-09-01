"""
Cheapie — Big Barrel per-branch product scraper.

Reported directly: the Big Barrel Havelock North pin showed generic
national-catalogue prices, even though havelock.bigbarrel.co.nz is a real,
live, branch-specific site. Confirmed Big Barrel runs the exact same
subdomain-per-branch shape as Bottle-O (same nopCommerce platform already
handled by scrape_nopcommerce()/parse_nopcommerce_page() in
scrape_independent_stores.py — no new parser needed), just never wired up
per-branch: scrape_independent_stores.py's TARGETS only ever scraped the
single national bigbarrel.co.nz catalogue, so every one of Big Barrel's 34
DB-listed stores was on generic fallback with zero branches confirmed.

Subdomain candidates found by testing every branch listed on
bigbarrel.co.nz/en/all-Shops against several naming patterns (first slug
word, joined words, common abbreviations), then confirmed for real via
each candidate's own <title> matching the expected branch name — same
discipline as scrape_thirsty_branches.py's Dunedin fix, since a wrong
guess can silently resolve to a different real branch. The full,
authoritative subdomain list was then cross-checked against the "select
your store" Click & Collect dropdown embedded in every branch page's own
JS (loads from an internal /Common/StoreList endpoint, blocked here by
antiforgery-token auth — but the dropdown's own already-rendered <option>
source in a branch homepage's HTML lists every other branch's subdomain
in plaintext, no auth needed).

Of Big Barrel's ~53 listed branches: 47 have a confirmed live subdomain
shop (below). Titahi Bay's subdomain resolves but its own page says
"Store closed" — deliberately excluded, scraping a closed store's stale
prices would be actively misleading, not just incomplete. Ferrymead and
Mangere are real branches (both already in the `stores` table) but their
subdomains gave a genuine DNS resolution failure, not a guessing miss —
left on generic fallback like Bottle-O's ~70 no-online-shop branches.
Ahuriri, Kelburn, Papakura, Parnell and Thorndon are listed on the
corporate site with no subdomain found by any pattern tried and no
`stores` row either — nothing to scrape or attribute, so not included.

16 of the 47 confirmed branches had no `stores` row at all (not merely an
unmatched store_id — the branch didn't exist in the table, so nothing was
even showing a pin) — see add_bigbarrel_stores.py, which must be run once
(via its GitHub Actions workflow) before this script's store_ids resolve
to real rows.

Uses the same category URL list as the generic "Big Barrel" TARGETS
entries in scrape_independent_stores.py (every branch subdomain serves
the exact same slugs, confirmed directly for /en/beers on both Havelock
North and Richmond) — imported directly rather than duplicated, so any
future addition to that list covers per-branch scraping too.

Designed to be safe to re-run on a schedule: replaces this run's
branches' rows in independent_store_prices.csv rather than appending
duplicates on top of the previous run's.

2026-08-28: a first full run hit GitHub Actions' hard 6h execution
ceiling and was force-cancelled. Confirmed directly (not a bug) — 70
categories per branch really does add up; see CHUNK_INDEX/CHUNK_COUNT
below, same fix already used for Super Liquor's 147 branches.

2026-09-01: the first chunk count (4) was sized off a single category's
timing (Beers, 45s) — confirmed directly that badly undersold the real
cost (Wine and Spirits are each several times bigger). A real full-branch
timing run (all 70 categories, Havelock North) came to 1777s (~29.6 min)
— resized to 12 chunks for real headroom (~2h/chunk instead of ~5.9h,
which is why the 4-chunk run got cancelled right at the 6h mark instead
of finishing).

HOW TO RUN:
    python3 scrape_bigbarrel_branches.py
    # or, chunked (see scrape-branches.yml's big-barrel matrix job):
    CHUNK_INDEX=0 CHUNK_COUNT=12 python3 scrape_bigbarrel_branches.py
"""
import csv, time, os
import scrape_independent_stores as s

# 2026-08-28 fix: the first full run of this script hit GitHub Actions'
# hard 6h execution ceiling and was force-cancelled, same failure mode
# already documented for Super Liquor's 147-branch scrape. Confirmed
# directly (not a bug/runaway pagination) — a single real category (Beers
# at Havelock North) genuinely took 45s across 20 real pages, and with 70
# categories x 47 branches that adds up to something in the same ballpark
# as the 6h ceiling. Same fix as Super Liquor: CHUNK_INDEX/CHUNK_COUNT env
# vars split BRANCHES into N parallel jobs via [start::step] slicing (not
# contiguous blocks), so no single chunk is skewed if catalogue depth
# varies branch to branch. Defaults to "no chunking" for a plain
# manual/local run.
CHUNK_INDEX = int(os.environ.get("CHUNK_INDEX", "0"))
CHUNK_COUNT = int(os.environ.get("CHUNK_COUNT", "1"))

BRANCHES = {
    "Albert, Palmerston North": ("https://albert.bigbarrel.co.nz", "0c9461d6-1f7d-4a00-b1e4-11b34a86cca1"),
    "Andersons Bay, Dunedin": ("https://andersonsbay.bigbarrel.co.nz", "38044360-1c92-45bc-b792-53fea66d22cd"),
    "Carlyle, Napier": ("https://carlyle.bigbarrel.co.nz", "c8b6d206-09cc-42a3-a8ab-826c7c571d9a"),
    "Clive, Hastings": ("https://clive.bigbarrel.co.nz", "6903f530-d967-43b8-a611-ef387bfdc47d"),
    "Dannevirke": ("https://dannevirke.bigbarrel.co.nz", "acef4f52-dc80-4a48-b56c-7a9012b91884"),
    "Havelock North, Hastings": ("https://havelock.bigbarrel.co.nz", "20881c78-d58a-43bd-9daf-3531556098b3"),
    "Hawera": ("https://hawera.bigbarrel.co.nz", "efa146dd-6572-40c7-8646-44cdc42d4157"),
    "Inglewood": ("https://inglewood.bigbarrel.co.nz", "e85f0c6d-d52f-4ff7-ae84-49832cd49a78"),
    "Karamu, Hastings": ("https://karamu.bigbarrel.co.nz", "e635c5ab-84db-4dbc-a2b3-ead2710c55b4"),
    "Kimbolton, Feilding": ("https://kimbolton.bigbarrel.co.nz", "d4a3df54-ec1a-491b-9efd-36d540501e9f"),
    "Lower Hutt": ("https://lowerhutt.bigbarrel.co.nz", "5efa6564-02d3-4e40-b385-d469e7ee29f2"),
    "Marewa, Napier": ("https://marewa.bigbarrel.co.nz", "91b3afec-ab0e-46e7-9504-d24bc40ee3d1"),
    "Miramar": ("https://miramar.bigbarrel.co.nz", "29534acc-c3e6-47c9-ab78-bb27868e734f"),
    "Mosgiel, Dunedin": ("https://mosgiel.bigbarrel.co.nz", "5f643f19-d4b9-498a-a766-1f76c212f4ce"),
    "Mt Eden, Auckland": ("https://mteden.bigbarrel.co.nz", "58009328-c1f7-4ba2-ace3-9572265c4083"),
    # 2026-08-26: two Nelson-area stores in the DB (Nelson city, and
    # Richmond a suburb over) both matched a plain "Nelson" name substring
    # — same collision class as Dunedin's earlier fix. Assigned by
    # elimination: "richmond" already resolved to its own distinct
    # subdomain/title, so "nelson" is unambiguously the other one.
    "Nelson": ("https://nelson.bigbarrel.co.nz", "51b50d75-e47a-46a9-845f-665914ef0f00"),
    "Newtown, Wellington": ("https://newtown.bigbarrel.co.nz", "88347350-e8e6-4a07-89d6-8a8cde8e4f23"),
    "Otahuhu, Auckland": ("https://otahuhu.bigbarrel.co.nz", "302fb729-50bf-4a6d-a450-b087ab5df335"),
    "Pahiatua": ("https://pahiatua.bigbarrel.co.nz", "e9ffb635-72f5-44e5-989e-8fcbdf985fe1"),
    "Picton": ("https://picton.bigbarrel.co.nz", "17b77686-bdbe-4760-9e7e-8f1bf4697f68"),
    "Princess, Palmerston North": ("https://princess.bigbarrel.co.nz", "9748017f-9664-43dc-97d4-1cb9e1691809"),
    "Richmond, Nelson": ("https://richmond.bigbarrel.co.nz", "b76a42a7-5432-4076-bf3a-b1efa63586d2"),
    "Stratford": ("https://stratford.bigbarrel.co.nz", "3e04649a-3607-4914-981b-91f0a6ad67a6"),
    "Tamatea, Napier": ("https://tamatea.bigbarrel.co.nz", "fdfbc798-9278-4734-ae86-fed41ec59430"),
    "Taradale, Napier": ("https://taradale.bigbarrel.co.nz", "934f9ae1-c97d-4819-a247-bf9e5e816296"),
    "Te Awamutu": ("https://teawamutu.bigbarrel.co.nz", "2487daa3-029e-4943-900c-95ae0adcd655"),
    "Victoria Ave, Whanganui": ("https://victoria.bigbarrel.co.nz", "4133be07-6476-4ab5-a606-41816d18662d"),
    "Waipukurau": ("https://waipukurau.bigbarrel.co.nz", "390a095a-6a27-4484-9e7c-0cb58d2913e5"),
    "Wigram, Christchurch": ("https://wigram.bigbarrel.co.nz", "c8c6cec2-7c70-4420-b160-b03898b5dcab"),
    # Same elimination logic as Nelson/Richmond above: "Big Barrel
    # Feilding" and "Big Barrel Kimbolton, Feilding" both matched a plain
    # "Feilding" substring; Kimbolton already resolved to its own
    # subdomain, so this is unambiguously the other one.
    "Feilding": ("https://feilding.bigbarrel.co.nz", "14dadf92-7e46-404b-aa59-4bc702027ad5"),
    # Same again for Whanganui: "Big Barrel Whanganui (Gonville)" and
    # "Big Barrel Victoria Ave, Whanganui" both matched; Victoria Ave
    # already resolved separately, so plain "whanganui" is Gonville.
    "Whanganui (Gonville)": ("https://whanganui.bigbarrel.co.nz", "2aa7ff37-89b7-4468-9bbe-9559735d2cd2"),
    # Branches below had no `stores` row at all until add_bigbarrel_stores.py
    # ran — see that script's docstring for how each was geocoded.
    "Taita, Lower Hutt": ("https://centralhutt.bigbarrel.co.nz", "9c26ede4-d3c2-4662-b6fe-49e3cb2e0cb8"),
    "Cloverlea, Palmerston North": ("https://cloverlea.bigbarrel.co.nz", "fcc1cea0-6110-4700-82b8-7be6e96a8b3a"),
    "Concord, Dunedin": ("https://concord.bigbarrel.co.nz", "6740436a-c4ae-4491-9994-3fd1c4905d37"),
    "Highbury, Palmerston North": ("https://highbury.bigbarrel.co.nz", "d6d8c984-0203-4422-a206-1cd334e971d4"),
    "Masterton, Wairarapa": ("https://masterton.bigbarrel.co.nz", "2bcd7c8c-387a-4dd1-b4ff-802abbae3ac3"),
    "New Plymouth": ("https://newplymouth.bigbarrel.co.nz", "e4dedae6-6944-45c6-8525-a7f92573e252"),
    "Otaki, Kapiti Coast": ("https://otaki.bigbarrel.co.nz", "70067443-a832-48a7-a454-446ec9382a92"),
    "Remarkables, Queenstown": ("https://remarkables.bigbarrel.co.nz", "1c98b096-207d-43f3-a4aa-eba2b629c3f3"),
    "Riverside, Whanganui": ("https://riverside.bigbarrel.co.nz", "cd677122-1822-4854-9f7c-4676ac5f8149"),
    "Stortford Lodge, Hastings": ("https://stortford.bigbarrel.co.nz", "2e63543b-d2d3-43b2-8c13-edf86a30e443"),
    "Tremaine, Palmerston North": ("https://tremaine.bigbarrel.co.nz", "21bba0f0-1e79-4cd9-9cb2-29a08675e608"),
    "Waitangirua, Porirua": ("https://waitangirua.bigbarrel.co.nz", "a63237b3-0e92-445a-8fff-7d3c1346f74b"),
    "Whanganui East": ("https://whanganuieast.bigbarrel.co.nz", "bac0d412-3327-41f2-ba9e-ae5b94a472bc"),
    "Devon Rd, New Plymouth": ("https://devonrd.bigbarrel.co.nz", "9a85bb56-c227-4363-9aa0-69f41244ba4f"),
    "Kent Terrace, Wellington": ("https://kenttce.bigbarrel.co.nz", "4c670fc2-0ee9-431d-9db6-d72a2ab39624"),
    "Kaikorai Valley, Dunedin": ("https://kaikorai.bigbarrel.co.nz", "37bfc8e1-16f0-4525-a4fc-f7036e0300ff"),
}

# Every category path already proven against the national bigbarrel.co.nz
# catalogue in scrape_independent_stores.py's TARGETS — reused rather than
# duplicated so this list only ever needs updating in one place. Confirmed
# directly that branch subdomains serve the identical slugs (same
# /en/beers etc. path works on both havelock.bigbarrel.co.nz and
# richmond.bigbarrel.co.nz).
NATIONAL_BASE = "https://bigbarrel.co.nz"
CATEGORY_PATHS = [
    (url[len(NATIONAL_BASE):], category)
    for (store, url, category, platform) in s.TARGETS
    if store == "Big Barrel"
]


def main():
    branch_items = list(BRANCHES.items())[CHUNK_INDEX::CHUNK_COUNT]
    print(f"Chunk {CHUNK_INDEX + 1}/{CHUNK_COUNT}: {len(branch_items)} of {len(BRANCHES)} Big Barrel branches this run, {len(CATEGORY_PATHS)} category pages each")
    new_rows = []
    for label, (base, store_id) in branch_items:
        store_name = f"Big Barrel {label}"
        print(f"Scraping {store_name} ({base})...")
        branch_products = 0
        for path, category in CATEGORY_PATHS:
            try:
                products = s.scrape_nopcommerce(f"{base}{path}")
                for p in products:
                    new_rows.append({
                        "store": store_name,
                        "store_id": store_id,
                        "category": category,
                        "product_name": p["name"],
                        "price": p["price"],
                        "was_price": p.get("was_price") or "",
                        "in_stock": p.get("in_stock", True),
                        "url": p.get("url") or "",
                        "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
                    })
                branch_products += len(products)
            except Exception as e:
                print(f"  {category} ({path}) error: {e}")
            time.sleep(0.5)
        print(f"  {branch_products} products")

    print(f"\nTotal new branch-specific rows: {len(new_rows)}")

    # 2026-08-26: same fix already applied to every other per-branch
    # scraper in this project (see scrape_thirsty_branches.py) — this file
    # is gitignored (regenerated data, not source), so a plain open() here
    # would crash every fresh GitHub Actions checkout. This run's own
    # fresh rows still get written either way.
    scraped_store_names = {f"Big Barrel {label}" for label, _ in branch_items}
    if os.path.exists("independent_store_prices.csv"):
        with open("independent_store_prices.csv") as f:
            existing = list(csv.DictReader(f))
    else:
        existing = []

    # PRODUCT_FIELDNAMES already ends in "store_id" — appending it again
    # here (the way scrape_thirsty_branches.py does) would just give the
    # CSV a harmless duplicate header column, so it's left out.
    fieldnames = list(s.PRODUCT_FIELDNAMES)
    for row in existing:
        row.setdefault("store_id", "")

    # Drop this run's branches' old rows before appending fresh ones — a
    # scheduled re-run must replace, not pile duplicates on top of, the
    # previous run's data for the same branches. The generic "Big Barrel"
    # national-catalogue rows (still used as fallback for Ferrymead,
    # Mangere and every other branch not listed above) are untouched.
    kept = [row for row in existing if row["store"] not in scraped_store_names]
    all_rows = kept + new_rows
    with open("independent_store_prices.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Wrote {len(all_rows)} total rows ({len(new_rows)} fresh branch-specific Big Barrel rows)")


if __name__ == "__main__":
    main()
