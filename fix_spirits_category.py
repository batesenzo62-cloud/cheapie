"""
One-off: fix the Spirits category — reported directly, most of what
appears there is mixed drinks (premixed cocktails, canned RTD-style
products) rather than straight spirits, and a small number of listed
"spirits" are actually non-alcoholic mixers with no alcohol content at
all. Both were identified by classifying every distinct product name
currently under category=spirits (keyword/pattern match against RTD
signals like "and cola", "ready to serve", "spritz", "cocktail", known
canned-cocktail brands, etc.), then manually reviewing every match to
drop false positives (e.g. "Rhubarb & Ginger Gin" is a flavour, not a
mixer — kept as spirits; "Cocktail Glass Gift Pack" is a bottle + glassware
bundle, not a premixed drink — kept as spirits).

Reclassifies 109 distinct product names (all their rows, across every
store) from spirits -> rtd, and deletes 17 distinct product names
that are genuinely non-alcoholic mixers (Schweppes/Fever-Tree ginger ale
etc.) — those don't belong under any alcohol category.

HOW TO RUN (via GitHub Actions workflow_dispatch, service key required):
    python3 fix_spirits_category.py
"""
import os, requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gkkchssgamqfavomcnoq.supabase.co")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

RTD_NAMES = [
    "3 Wise Men Spritz &amp; Roll 750mL",
    "Af Apero Spritz 4x250c",
    "Bacardi Mojito 700mL",
    "Bacardi Mojito 700ml",
    "Bar 307 Italian Spritz 750mL",
    "Batched Espresso Martini Cocktail Kit Gift Pack 725ml",
    "Besos Margarita Clasica Ready To Serve Cocktail 700ml",
    "Besos Margarita Clasica Ready to Serve Cocktail 700ml",
    "Besos Margarita Espresso Ready to Serve Cocktail 700ml",
    "Besos Margarita Habanero Ready to Serve Cocktail 700ml",
    "Besos Margarita Ready to Serve Pasion 700ml",
    "Bombay Sapphire Gin And Tonic (4 Pack)",
    "BuzzBallz Chili Mango 200ml",
    "BuzzBallz Cocktails Chili Mango 200mL",
    "BuzzBallz Cocktails Choc Tease 200mL",
    "BuzzBallz Cocktails Cocktails Tequila &#39;Rita 200mL",
    "BuzzBallz Cocktails Cran Blaster 200mL",
    "BuzzBallz Cocktails Espresso Martini 200mL",
    "BuzzBallz Cocktails Forbidden Apple 200mL",
    "BuzzBallz Cocktails Lotta Colada 200mL",
    "BuzzBallz Cocktails Passionfruit Martini 200mL",
    "BuzzBallz Cocktails Pineapple Jalapeno 200mL",
    "BuzzBallz Cocktails Pink Lemonsqueezy 200mL",
    "BuzzBallz Cocktails Tequila &#39;Rita 200mL",
    "BuzzBallz Cocktails Watermelon Smash 200mL",
    "BuzzBallz Lotta Colada 200ml",
    "BuzzBallz Passionfruit Martini 200mL",
    "BuzzBallz Passionfruit Martini 200ml",
    "BuzzBallz Strawberry Margarita 200ml",
    "BuzzBallz Tequila Rita 200ml",
    "Buzzballz Berry Cherry 1.75L",
    "Buzzballz Berry Cherry 200mL",
    "Buzzballz Chilli Mango 15% 200ml",
    "Buzzballz Chilli Mango 200mL",
    "Buzzballz Cocktails Berry Cherry Limeade 200mL",
    "Buzzballz Cocktails Biggies Chocolate Tease 1.75L",
    "Buzzballz Cocktails Biggies Tequila &#39;Rita 1.75L",
    "Buzzballz Cocktails Fireball Horchata 200mL",
    "Buzzballz Cocktails Hazelnut Latte 200mL",
    "Buzzballz Cocktails Peachballz 200mL",
    "Buzzballz Cocktails Strawberry &#39;Rita 200mL",
    "Buzzballz Cocktails Strawberry Rita 200ML 15%",
    "Buzzballz Grapes Gone 1.5L",
    "Buzzballz Lemon Tea 187mL",
    "Buzzballz Lotto Colada 200mL",
    "Buzzballz Passionf Marti 200mL",
    "Buzzballz Peppermint Snow 1.5L",
    "Buzzballz Pumpkin 1.5L",
    "Buzzballz Strawbrry Marg 200mL",
    "Clean Co Italian Spritz 750mL",
    "DE Kuyper Pina Colada Liqueur 700ml",
    "De Bortoli Limone Limoncello Spritz 750mL",
    "De Kuyper Clover Club Cocktail 500ml",
    "De Kuyper Passionfruit Martini Cocktail 500ml",
    "De Kuyper Pina Colada 1L",
    "De Kuyper Pina Colada 700mL",
    "De Kuyper Pi\u00f1a Colada Cocktail 1 Litre",
    "De Kuyper Strawberry Daiquiri Cocktail 500ml",
    "De Kuyper Strawberry Mojito Cocktail 1 Litre",
    "Duchess H Italian Spritz Gin Cup 700ml",
    "Duchess H Ready to Pour Gincello Spritz 700mL",
    "Edinburgh Gin Rhubarb & Ginger Liqueur 50ml",
    "Jack Daniels Apple Soda 4x330ml Cans",
    "Jim Beam and Cola 4.8% 330ml 6pk cans",
    "Jim Beam and Cola Zero Sugar 18pk Cans",
    "Jim Beam and Cola Zero Sugar 330ml 18pk Cans",
    "LADY H Duchess H Italian Spritz Gin Cup 700mL",
    "Lady H Duchess Cocktails Gin a Colada 700ml",
    "Lady H Duchess Cocktails Gincello Spritz 700ml",
    "Lady H Duchess Cocktails Passionstar Martini 700ml",
    "Lady H Duchess Italian Spritz Gin Cup 700ml",
    "Lady H Duchess Italian Spritz Gin Cup Cup 700mL",
    "Lady H Gincello Spritz 700mL",
    "Le Coq Margarita Cocktail 6x4pk Bottles 330ml",
    "Le Coq Pina Colada 4pk Bottles 330ml",
    "Le Tribute Mini Gin And Tonic Gift Pack",
    "Le Tribute Mini Gin and Tonic Gift Pack 50ml",
    "Lemsecco Limoncello Spritz 750mL",
    "Malibu Watermelon 10x250ml Cans",
    "Pimms 12x250ml Cans",
    "Roro Aperitivo Spritz 750ml",
    "Scapegrace Gin And Tonic With Lemon (10 Pack)",
    "Starward Coffee Old Fashioned Whisky Cocktail 500mL",
    "Starward Negroni Whisky Cocktail 500mL",
    "Starward New Old Fashioned Bottled Whisky Cocktail 500mL",
    "Tanqueray Gin & Tonic 4x250mL",
    "Tanqueray Gin And Tonic Cans (4 Pack)",
    "Vok Cocktails Limoncello Punch 5% Cask 2 LT",
    "Vok Espresso Martini Cocktail 500ml",
    "Vok Ready to Serve Cocktail Blue Lagoon 2Lt",
    "Vok Ready to Serve Cocktail Lime Margarita 5% 2L",
    "Vok Ready to Serve Cocktail Lime Mojito 2Lt",
    "Vok Ready to Serve Cocktail Lime Mojito 5% 2L",
    "Vok Ready to Serve Cocktail Limoncello Punch 2L",
    "Vok Ready to Serve Cocktail Limoncello Punch 2Lt",
    "Vok Ready to Serve Cocktail Long Island 2Lt",
    "Vok Ready to Serve Cocktail Pina Colada 2Lt",
    "Vok Ready to Serve Cocktail Pina Colada 5% 2L",
    "Vok Ready to Serve Cocktail Pineapple Margarita 2Lt",
    "Vok Ready to Serve Pineapple Margarita 5% 2L",
    "Wild Turkey 101 7% 10x330ml Cans",
    "Wild Turkey Cola 4.8% 10x330ml Cans",
    "ZONZO ESTATE CICCHIO PISTACHIO SPRITZ",
    "ZONZO ESTATE ZONCELLO LIMONCELLO SPRITZ",
    "Zonzo Estate Bellina Spritz 4x200mL",
    "Zonzo Estate Bellina Spritz 750mL",
    "Zonzo Estate Cicchio Pistaccio Spritz 750mL",
    "Zonzo Estate Zoncello Limoncello Spritz 4x200mL",
    "Zonzo Estate Zoncello Limoncello Spritz 750mL"
]

MIXER_DELETE_NAMES = [
    "Elta Ego Cocktails Non Alcoholic Espresso Martini 4x250mL",
    "Elta Ego Cocktails Non Alcoholic Mojito 4x250mL",
    "Elta Ego Cocktails Non Alcoholic Negroni 4x250mL",
    "Elta Ego Cocktails Non Alcoholic Passionfruit Margarita 4x250mL",
    "Elta Ego Cocktails Non Alcoholic Raspberry & Yuzu GnT 4x250mL",
    "Fever-Tree Ginger Ale (4 Pack Bottles)",
    "Fever-Tree Ginger Ale (500ml)",
    "Fever-Tree Ginger Beer (4 Pack Bottles)",
    "Fever-Tree Ginger Beer (4 Pack Cans)",
    "Fever-Tree Ginger Beer (500ml)",
    "Freez Mix Mojito Strawb 275b",
    "Master of Mixes Mojito 1L",
    "Master of Mixes Mojito Mixer 1Lt",
    "Pentire Coastal Spritz N/A 700ml",
    "Schweppes Dry Ginger Ale (1500ml)",
    "Schweppes Ginger Ale Mini (6 Pack Cans)",
    "Schweppes Gingerbeer Mini (6 Pack Cans)"
]


def main():
    total_reclassified = 0
    for name in RTD_NAMES:
        resp = requests.patch(
            f"{SUPABASE_URL}/rest/v1/products",
            headers={**HEADERS, "Prefer": "return=representation,count=exact"},
            params={"category": "eq.spirits", "product_name": f"eq.{name}"},
            json={"category": "rtd"},
            timeout=30,
        )
        if resp.status_code not in (200, 204):
            print(f"  FAILED reclassify {name!r}: {resp.status_code} {resp.text[:200]}")
            continue
        count_range = resp.headers.get("content-range", "")
        n = int(count_range.split("/")[-1]) if "/" in count_range else "?"
        total_reclassified += n if isinstance(n, int) else 0
        print(f"  reclassified {n} rows: {name!r}")

    total_deleted = 0
    for name in MIXER_DELETE_NAMES:
        resp = requests.delete(
            f"{SUPABASE_URL}/rest/v1/products",
            headers={**HEADERS, "Prefer": "return=representation,count=exact"},
            params={"category": "eq.spirits", "product_name": f"eq.{name}"},
            timeout=30,
        )
        if resp.status_code not in (200, 204):
            print(f"  FAILED delete {name!r}: {resp.status_code} {resp.text[:200]}")
            continue
        count_range = resp.headers.get("content-range", "")
        n = int(count_range.split("/")[-1]) if "/" in count_range else "?"
        total_deleted += n if isinstance(n, int) else 0
        print(f"  deleted {n} rows: {name!r}")

    print(f"\nDone. Reclassified ~{total_reclassified} rows spirits->rtd across {len(RTD_NAMES)} names, deleted ~{total_deleted} rows across {len(MIXER_DELETE_NAMES)} non-alcoholic mixer names.")


if __name__ == "__main__":
    main()
