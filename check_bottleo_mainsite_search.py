"""One-off: user found thebottleo.co.nz's own search for "steinlager"
returns real results — check what endpoint/mechanism that actually uses,
since earlier /shop and /products checks (static paths only) missed
this entirely. Delete after use."""
import re
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
base = "https://www.thebottleo.co.nz"

# Check the homepage for a search form/endpoint
r = requests.get(base + "/", headers=HEADERS, timeout=20)
print("homepage status:", r.status_code)
forms = re.findall(r'<form[^>]*action="([^"]*)"[^>]*>', r.text)
print("forms found:", forms)
search_hints = re.findall(r'(search[a-zA-Z_-]*\.php|/search[^"\'\s]*|api[^"\'\s]*search[^"\'\s]*)', r.text, re.I)
print("search-related URL hints:", set(search_hints))

# Try common search URL patterns directly
for path in ["/search?q=steinlager", "/search?query=steinlager", "/search/steinlager", "/?s=steinlager", "/products/search?q=steinlager"]:
    url = base + path
    try:
        r2 = requests.get(url, headers=HEADERS, timeout=15)
        print(f"\n{url} -> status {r2.status_code}, bytes {len(r2.content)}")
        if r2.status_code == 200 and "steinlager" in r2.text.lower():
            print("  CONTAINS 'steinlager' in response!")
    except Exception as e:
        print(f"\n{url} -> error: {e}")
