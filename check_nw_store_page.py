"""One-off: re-verify whether New World's own per-branch store page (not
the /shop/category path) exposes any real pricing data or an unprotected
API endpoint we might have missed — checking this fresh rather than
trusting the earlier conclusion, since a similar "no free path" assumption
for Bottle-O turned out to be wrong. Delete after use."""
import re, json
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}
url = "https://www.newworld.co.nz/upper-north-island/auckland/albany"

r = requests.get(url, headers=HEADERS, timeout=20)
print("store page status:", r.status_code, "bytes:", len(r.text))

m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.S)
if m:
    data = json.loads(m.group(1))
    # dump top-level keys to look for anything pricing/product/shop related
    def find_keys(obj, path="", depth=0, out=None):
        if out is None: out = []
        if depth > 4: return out
        if isinstance(obj, dict):
            for k, v in obj.items():
                if any(word in k.lower() for word in ["shop", "product", "price", "categor", "api", "graphql", "endpoint"]):
                    out.append(f"{path}.{k}" if path else k)
                find_keys(v, f"{path}.{k}" if path else k, depth+1, out)
        elif isinstance(obj, list) and obj:
            find_keys(obj[0], path + "[0]", depth+1, out)
        return out
    hits = find_keys(data)
    print("interesting keys found:", hits[:30])
else:
    print("no __NEXT_DATA__ found on store page")

# Also check for any fetch/API calls referenced in inline scripts
api_hints = re.findall(r'(https?://[a-zA-Z0-9.-]*(?:api|graphql)[a-zA-Z0-9./_-]*)', r.text)
print("\nAPI-looking URLs referenced in page:", set(api_hints))
