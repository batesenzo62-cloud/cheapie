"""One-off: inspect the fallback.categories-<uuid> data found embedded in
a New World store page — this looks like Next.js SWR fallback data,
possibly pre-loaded, unprotected product/pricing data. Delete after use."""
import re, json
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}
url = "https://www.newworld.co.nz/upper-north-island/auckland/albany"

r = requests.get(url, headers=HEADERS, timeout=20)
m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.S)
data = json.loads(m.group(1))

fallback = data.get("props", {}).get("pageProps", {}).get("fallback", {})
print("all fallback keys:", list(fallback.keys()))

for key in fallback:
    if key.startswith("categories-"):
        val = fallback[key]
        print(f"\n=== {key} ===")
        print(json.dumps(val, indent=2)[:3000])
