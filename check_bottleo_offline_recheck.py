"""One-off: verify the 2 candidate matches (Hamilton Central -> "central",
Leamington -> "cambridge") actually belong to the expected branch, not a
different city's branch that happens to share a short/generic slug.
Delete after use."""
import re, requests

HEADERS = {"User-Agent": "Mozilla/5.0"}

for label, slug, expected_address in [
    ("Hamilton Central", "central", None),
    ("Leamington", "cambridge", None),
]:
    base = f"https://{slug}.shop.thebottleo.co.nz"
    r = requests.get(base + "/", headers=HEADERS, timeout=15)
    print(f"=== {label} -> {slug} ===")
    text = r.text
    # crude: find any address-like text (look near "contact" or footer, or a phone/street pattern)
    title_match = re.search(r"<title>([^<]*)</title>", text)
    print("  page title:", title_match.group(1) if title_match else None)
    # look for common footer/contact address patterns
    addr_candidates = re.findall(r'([0-9]+[A-Za-z]?\s+[A-Za-z][A-Za-z\s]{3,40}(?:Road|Street|Drive|Avenue|Highway|Rd|St|Dr|Ave)[^<]{0,60})', text)
    print("  address-like strings found:", addr_candidates[:5])
