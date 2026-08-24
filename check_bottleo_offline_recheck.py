"""One-off re-audit, broadened: previous attempt using only the branch
name for subdomain guesses found 0 matches, suspiciously clean given the
last real audit found 10 using name-based guesses too — broadened to also
generate candidates from the store's address (suburb, street), same
approach already proven for Thirsty Liquor's branch discovery. Delete
after use.
"""
import json, re, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {"User-Agent": "Mozilla/5.0"}

def clean_words(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    return [w for w in text.split() if w and w not in ("road", "rd", "street", "st", "drive", "dr", "avenue", "ave", "auckland", "wellington", "christchurch", "hamilton", "tauranga", "dunedin", "unit", "shop")]

def slugify_candidates(name, address):
    candidates = set()
    name_words = clean_words(name)
    addr_words = clean_words(address or "")

    def add_variants(words):
        if not words:
            return
        candidates.add("-".join(words))
        candidates.add("".join(words))
        if len(words) > 1:
            candidates.add("-".join(words[:2]))
            candidates.add("".join(words[:2]))
        candidates.add(words[0])
        if len(words) > 1:
            candidates.add(words[-1])

    add_variants(name_words)
    add_variants(addr_words[:4])  # first few address words often include suburb
    # try each individual address word too (suburb often isolated)
    for w in addr_words:
        if len(w) > 3:
            candidates.add(w)

    return [c for c in candidates if c and len(c) > 2]

def check_candidate(slug):
    base = f"https://{slug}.shop.thebottleo.co.nz"
    try:
        r = requests.get(base + "/", headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return None
        m = re.search(r'(dtgxwmigmg3gc\.cloudfront\.net/sidebar/[a-zA-Z0-9/_.-]+\.json[^"\']*)', r.text)
        if not m:
            return None
        return base
    except Exception:
        return None

with open("bottleo_stores.json") as f:
    stores = json.load(f)

offline = [s for s in stores if not s.get("online")]
print(f"Testing {len(offline)} offline-marked branches with broadened candidates...")

found = []
with ThreadPoolExecutor(max_workers=25) as ex:
    futs = {}
    total_candidates = 0
    for s in offline:
        for slug in slugify_candidates(s["name"], s.get("address", "")):
            futs[ex.submit(check_candidate, slug)] = (s, slug)
            total_candidates += 1
    print(f"total candidate URLs to test: {total_candidates}")
    for fut in as_completed(futs):
        s, slug = futs[fut]
        result = fut.result()
        if result:
            found.append((s["name"], slug, result))
            print(f"  FOUND: {s['name']} -> {slug} ({result})")

uniq = {}
for name, slug, base in found:
    uniq.setdefault(name, []).append(slug)
print(f"\nTotal branches with a real match: {len(uniq)}")
for name, slugs in sorted(uniq.items()):
    print(f"  {name}: {slugs}")
