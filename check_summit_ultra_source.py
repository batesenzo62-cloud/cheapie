import requests

TARGETS = [
    ("beer-cider", "beer"),
    ("rtd", "rtd"),
    ("wine", "wine"),
    ("spirits", "spirits"),
    ("red-wine", "wine"),
    ("white", "wine"),
    ("bourbon", "spirits"),
    ("brandy", "spirits"),
    ("gin", "spirits"),
    ("irish", "spirits"),
    ("irish-cream", "spirits"),
    ("liqueurs", "spirits"),
    ("rum", "spirits"),
    ("tequila", "spirits"),
    ("vodka", "spirits"),
    ("whisky", "spirits"),
    ("classic", "spirits"),
    ("bourbon-rtd", "rtd"),
    ("gin-rtd", "rtd"),
    ("rum-rtd", "rtd"),
    ("vodka-rtd", "rtd"),
    ("whisky-rtd", "rtd"),
    ("rtd-2", "rtd"),
]

for slug, category in TARGETS:
    url = f"https://blackbullliquorhawera.co.nz/Shop-Online/{slug}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    except Exception as e:
        print(f"{slug} ({category}): ERROR {e}")
        continue
    count = resp.text.lower().count("summit ultra")
    print(f"{slug} ({category}): HTTP {resp.status_code}, 'summit ultra' appears {count} times")
