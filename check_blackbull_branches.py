"""One-off: verify the 3 candidate matches aren't false positives from
address-text collision (e.g. "Manaia Hawera" containing the substring
"hawera", matching the ALREADY-confirmed Hawera site instead of a real
Manaia site; "64 Thames St, Morrinsville" containing "thames", matching
a real but different town of Thames). Check each site's own stated
address. Delete after use."""
import re
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}

for label, url in [
    ("Glover Rd (claimed Hawera)", "https://blackbullliquorhawera.co.nz"),
    ("Manaia (claimed Hawera)", "https://blackbullliquorhawera.co.nz"),
    ("Morrinsville (claimed Thames)", "https://blackbullliquorthames.co.nz"),
]:
    r = requests.get(url, headers=HEADERS, timeout=20)
    text = r.text
    # crude: find address-like text near "address" or footer/contact info
    addr_matches = re.findall(r'([0-9]+[A-Za-z]?\s+[A-Za-z][A-Za-z\s]{2,30}(?:Road|Street|Rd|St|Drive|Dr|Highway)[^<]{0,50})', text)
    title_match = re.search(r"<title>([^<]*)</title>", text)
    print(f"=== {label} -> {url} ===")
    print("  page title:", title_match.group(1) if title_match else None)
    print("  address-like strings found:", addr_matches[:5])
    print()
