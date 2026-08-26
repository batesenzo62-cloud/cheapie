"""One-off: find real Thirsty Liquor branches among the 126 currently
uncovered — same domain pattern already confirmed for existing branches
(thirstyliquor<slug>.co.nz, one custom domain per branch, not a
subdomain). Candidates generated from both the branch name AND the
address/suburb text, since many uncovered branches are only labeled
"Thirsty Liquor Auckland" with the real distinguishing detail in the
address (same issue already fixed for a few branches previously).
Delete after use.
"""
import json, re, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {"User-Agent": "Mozilla/5.0"}

STOPWORDS = {"road", "rd", "street", "st", "drive", "dr", "avenue", "ave",
             "auckland", "wellington", "christchurch", "hamilton", "tauranga",
             "dunedin", "unit", "shop", "the", "hub", "complex", "shopping",
             "new", "zealand", "highway", "hwy", "place", "pl", "way",
             "parade", "pde", "north", "south", "east", "west"}

def clean_words(text):
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [w for w in text.split() if w and w not in STOPWORDS and not w.isdigit()]

def slug_candidates(name, address):
    name_words = clean_words(name.replace("Thirsty Liquor", ""))
    addr_words = clean_words(address)
    candidates = set()

    def add(words):
        if not words:
            return
        candidates.add("".join(words))
        candidates.add("-".join(words))
        if len(words) > 1:
            candidates.add("".join(words[:2]))
            candidates.add("".join(words[:1]))
        candidates.add(words[0])

    add(name_words)
    add(addr_words[:3])
    for w in addr_words:
        if len(w) > 3:
            candidates.add(w)

    return [c for c in candidates if c and len(c) > 2]

def check_candidate(slug):
    for base in [f"https://thirstyliquor{slug}.co.nz", f"https://www.thirstyliquor{slug}.co.nz"]:
        try:
            r = requests.get(base, headers=HEADERS, timeout=12)
            if r.status_code == 200 and ("thirsty" in r.text.lower() or "liquor" in r.text.lower()):
                return base
        except Exception:
            pass
    return None

with open("thirsty_uncovered_input.json") as f:
    stores = json.load(f)

print(f"Testing {len(stores)} uncovered branches...")
found = {}
with ThreadPoolExecutor(max_workers=20) as ex:
    futs = {}
    for s in stores:
        for slug in slug_candidates(s["name"], s.get("address", "")):
            futs[ex.submit(check_candidate, slug)] = (s, slug)
    print(f"total candidate URLs: {len(futs)}")
    for fut in as_completed(futs):
        s, slug = futs[fut]
        result = fut.result()
        if result:
            key = s["id"]
            found.setdefault(key, {"store": s, "matches": []})
            found[key]["matches"].append((slug, result))
            print(f"  FOUND: {s['name']} ({s.get('address')}) -> {result}")

print(f"\nTotal branches with at least one real match: {len(found)}")
with open("thirsty_found_candidates.json", "w") as f:
    json.dump({k: {"name": v["store"]["name"], "address": v["store"]["address"], "id": v["store"]["id"], "matches": v["matches"]} for k, v in found.items()}, f, indent=2)
