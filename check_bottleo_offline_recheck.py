"""One-off re-audit: it's been ~10 days since the last check of Bottle-O
branches marked offline in bottleo_stores.json (which found 10 real ones).
Branches can go online since then (confirmed directly: Mt Eden already has
a real subdomain despite being a near-empty new store) — re-testing all
currently offline-marked branches for a real, populated online catalog.
Delete after use.
"""
import json, re, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {"User-Agent": "Mozilla/5.0"}

def slugify_candidates(name):
    n = name.lower().strip()
    no_punct = re.sub(r"[^a-z0-9\s-]", "", n)
    words = no_punct.split()
    candidates = set()
    candidates.add("-".join(words))
    candidates.add("".join(words))
    candidates.add("".join(words).replace("-", ""))
    if len(words) > 1:
        candidates.add("-".join(words[:2]))
    return [c for c in candidates if c]

def check_candidate(name, slug):
    base = f"https://{slug}.shop.thebottleo.co.nz"
    try:
        r = requests.get(base + "/", headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        if "talker__product-name" not in r.text and "sidebar" not in r.text.lower():
            # still check for the sidebar json link, since homepage itself might not show products directly
            pass
        m = re.search(r'(dtgxwmigmg3gc\.cloudfront\.net/sidebar/[a-zA-Z0-9/_.-]+\.json[^"\']*)', r.text)
        if not m:
            return None
        return {"slug": slug, "base": base}
    except Exception:
        return None

with open("bottleo_stores.json") as f:
    stores = json.load(f)

offline = [s for s in stores if not s.get("online")]
print(f"Testing {len(offline)} offline-marked branches...")

found = []
with ThreadPoolExecutor(max_workers=15) as ex:
    futs = {}
    for s in offline:
        for slug in slugify_candidates(s["name"]):
            futs[ex.submit(check_candidate, s["name"], slug)] = (s, slug)
    for fut in as_completed(futs):
        s, slug = futs[fut]
        result = fut.result()
        if result:
            found.append((s["name"], result["slug"]))
            print(f"  FOUND: {s['name']} -> {result['slug']}")

print(f"\nTotal newly-found online branches: {len(set(n for n,_ in found))}")
for name, slug in sorted(set(found)):
    print(f"  {name}: {slug}")
