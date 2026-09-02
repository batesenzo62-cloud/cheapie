"""One-off: confirm the new Liquorland multibuy extraction produces real
rows with multibuy_quantity/multibuy_total_price set, against the live
site. Not a permanent scraper."""
import scrape_liquorland_full as sl

sl.init_session()
rows = sl.scrape_category("wine", "https://www.liquorland.co.nz/wine", "wine")
multibuy_rows = [r for r in rows if r.get("multibuy_quantity")]
print(f"{len(rows)} total rows, {len(multibuy_rows)} with multibuy_quantity set")
for r in multibuy_rows[:10]:
    print(f"  {r['product_name']!r}: {r['multibuy_quantity']} for ${r['multibuy_total_price']} (price=${r['price']})")
