"""One-off: list every real collection on Thirsty Liquor Havelock North's
site, and directly search their site search for "black heart" to see if a
4-pack exists somewhere outside the rtds/spirits collections we scrape.
Delete after use."""
import re, json
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}
base = "https://thirstyliquorhavelocknorth.co.nz"

# Shopify sites expose a collections.json endpoint
r = requests.get(f"{base}/collections.json?limit=250", headers=HEADERS, timeout=20)
print("collections.json status:", r.status_code)
if r.status_code == 200:
    data = r.json()
    for c in data.get("collections", []):
        print(f"  {c.get('handle')} — {c.get('title')}")

print("\n=== site search for 'black heart' ===")
r2 = requests.get(f"{base}/search", headers=HEADERS, params={"q": "black heart", "type": "product"}, timeout=20)
print("status:", r2.status_code)
text = r2.text
# crude: find product card blocks mentioning black heart
import re
matches = re.findall(r'talker__product-name">([^<]*[Bb]lack [Hh]eart[^<]*)</span>\s*(?:<span class="weak size talker__name__size">([^<]*)</span>)?', text)
for name, size in matches:
    print(f"  {name} | size={size}")
