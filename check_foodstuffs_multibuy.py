"""One-off: check whether New World/PAK'nSAVE currently have any real
active multiProducts promotions (threshold>1), or whether the multibuy
extraction logic in scrape_foodstuffs_products.py is just correctly
finding zero because none happen to be running right now. Not a
permanent scraper."""
import scrape_foodstuffs_products as fs

print("BRAND:", fs.BRAND)
token = fs.get_token()
stores = fs.get_real_stores(token)
store = stores["stores"][0]
print("store:", store.get("name"), store.get("id"))

for cat_name, app_cat in fs.CATEGORIES:
    data = fs.fetch_category_page(token, store["id"], cat_name, 1)
    products = data.get("products", [])
    promo_products = 0
    multibuy_products = 0
    sample_promos = []
    for p in products:
        promos = p.get("promotions") or []
        if promos:
            promo_products += 1
        for promo in promos:
            if len(sample_promos) < 5:
                sample_promos.append({k: promo.get(k) for k in ("multiProducts", "threshold", "rewardValue", "type", "reward")})
            if promo.get("multiProducts") and (promo.get("threshold") or 1) > 1:
                multibuy_products += 1
    print(f"  {cat_name}: {len(products)} products, {promo_products} with any promo, {multibuy_products} qualifying as multibuy")
    if sample_promos:
        print(f"    sample promo objects: {sample_promos}")
