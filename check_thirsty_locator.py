"""One-off: fetch the official Thirsty Liquor store locator page directly
and inspect its raw structure — looking for an embedded JSON store list
(same platform/template pattern as thirstyliquor.co.nz's own /collections
pages, which are real Shopify) that would give real branch names/domains
in one shot instead of guessing. Delete after use."""
import re, json
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}
url = "https://thirstyliquor.co.nz/pages/store-locator"
r = requests.get(url, headers=HEADERS, timeout=30)
print("status:", r.status_code, "bytes:", len(r.text))

# Look for embedded JSON blobs (Shopify apps often embed store-locator
# data as a JSON script tag or inline variable)
json_scripts = re.findall(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', r.text, re.S)
print(f"found {len(json_scripts)} application/json script blocks")
for i, blob in enumerate(json_scripts):
    print(f"\n--- json block {i}, length {len(blob)} ---")
    print(blob[:500])

# Look for common store-locator app patterns (many Shopify stores use a
# specific locator app with a known data attribute or API endpoint)
api_hints = re.findall(r'(https?://[a-zA-Z0-9.\-]*(?:locator|storemapper|storerocket|storepoint)[a-zA-Z0-9./_\-]*)', r.text, re.I)
print("\nlocator-app API hints:", set(api_hints))

# Dump raw text sample too, in case it's just plain HTML with addresses
soup_text_sample = r.text[:3000]
print("\nraw HTML sample (first 3000 chars):")
print(soup_text_sample)
