"""
Cheapie — pack size / unit volume parser

Extracts (unit_count, unit_volume_ml) from a scraped product name, so price
comparisons can be done per-litre instead of per-listing. There's no
structured field for this in any of the scraped data — it only ever shows
up embedded in the product name text, in a handful of different formats.

Returns (unit_count, unit_volume_ml) — unit_count defaults to 1 and
unit_volume_ml is None when nothing reliable can be extracted, rather than
guessing. Callers should treat unit_volume_ml is None as "can't compute a
per-litre price for this one", not as "assume 0".
"""

import re

# 2026-08-14: this file used to also export MIN_PLAUSIBLE_PRICE_PER_UNIT
# and load_data_to_supabase.py/backfill_pack_sizes.py used it to null out
# price_per_litre below $1.50/unit, on the theory that no real listing
# goes that low. Reported directly, and checked live against the actual
# retailer site: a flagged row ("Steinlager Classic Bottles 24 x 330mL" at
# $15.99, Bottle-O Kingsland) turned out to be a genuine live duplicate
# listing, not corruption — a real deal that suppression was hiding.
# Another flagged row at a similar price ("Desperados Teq Beer 6x330b" at
# $4.50) checked out genuinely stale/wrong (live price is $24.99, no
# duplicate). Price alone can't tell these apart, so hard suppression here
# was too blunt. cheapie-prototype.html now shows an honest "unusually
# cheap" caveat on the card instead, without hiding the number or its
# ranking, so a real find like the Steinlager one can still surface as
# the actual cheapest option.

_ML_UNIT = r"(?:ml|mL|ML|Ml)"
_L_UNIT = r"(?:litres?|Litres?|LITRES?|ltrs?|Ltrs?|LTRS?|l|L)\b"

# Some sources abbreviate the unit to a single trailing letter naming the
# container instead of the volume unit — "330c" (330mL can), "500b" (500mL
# bottle). Confirmed against 60 real sampled examples with zero false
# positives (always immediately after the number, always a real can/bottle
# size) — safe to treat as already-mL, same as _ML_UNIT.
_BC_UNIT = r"(?:c|C|b|B)\b"

# A handful of listings truncate "750ml" to "750m" (missing the final "l").
# Restricted to the very end of the string — mid-name a lone "m" is usually
# part of the product name itself (e.g. "Speights 5M Old Dark 12pk Btls",
# where "5M" is a style code, not a size) rather than a truncated unit.
_M_TRUNC = r"m(?=\s*$)"

# Capturing (not non-capturing) — every call site immediately reads the
# matched unit text back via _to_ml(), so it needs its own group number.
_VOLUME_UNIT = "(" + _ML_UNIT + "|" + _BC_UNIT + "|" + _M_TRUNC + "|" + _L_UNIT + ")"


def _to_ml(value, unit):
    unit = unit.lower()
    if unit.startswith("l"):
        return value * 1000
    return value


# 330mL is the standard single-serve beer/cider/RTD bottle size in NZ —
# safe to assume for a beer/rtd product that says "bottle(s)"/"btl(s)" but
# never states a size, the same reasoning as wine's 750mL default (a
# named container type with one dominant real-world size, rather than a
# guess with no basis). Not applied to wine/spirits, where "bottle" covers
# a much wider real range (375mL-1L+) and there's no single safe default.
_BOTTLE_WORD = re.compile(r"\bbtls?\b|\bbottles?\b", re.IGNORECASE)


def _bottle_default(name, category):
    if category not in ("beer", "rtd"):
        return None
    return 330 if _BOTTLE_WORD.search(name) else None


def _fix_if_total_not_per_unit(count, volume):
    # Some listings state the pack's TOTAL volume rather than the size of
    # each can/bottle — e.g. "18 pack 5940mL" (5940 = 18 x 330, the real
    # per-can size), which otherwise reads identically to a legitimate
    # "12 Pack Bottles 330ml" (already-per-unit) pattern. No commercial
    # single can/bottle exceeds ~2L, so if the parsed "per-unit" volume is
    # bigger than that AND dividing it by the pack count lands in a
    # plausible single-serve/bottle range, treat it as a total instead.
    if count > 1 and volume and volume > 2000:
        per_unit_if_total = volume / count
        if 100 <= per_unit_if_total <= 2000:
            return per_unit_if_total
    return volume


def parse_pack_size(name, category=None):
    if not name:
        return 1, None

    # Typo fix: "33oml" instead of "330ml" — the middle "0" got mistyped
    # as the visually similar letter "o" (e.g. "Steinlager Pure 24x33oml
    # Bottles"). Restores the dropped zero before any of the real parsing
    # rules run, rather than adding a whole extra unit variant for it.
    name = re.sub(r"(\d{2})o(ml)\b", r"\g<1>0\g<2>", name, flags=re.IGNORECASE)

    # 1. "6x330ml", "12 x 330ml", "6x1 Litre", "10x250ml", "6x 330ml"
    m = re.search(
        r"(\d+)\s*[xX]\s*(\d+(?:\.\d+)?)\s*" + _VOLUME_UNIT,
        name,
    )
    if m:
        count = int(m.group(1))
        volume = _to_ml(float(m.group(2)), m.group(3))
        return count, _fix_if_total_not_per_unit(count, volume)

    # 2. "24pk Cans 330ml", "6 Pack Cans 330ml", "18 Pack Can 250ml",
    #    "24pack 330mL", "12PK CANS 250ML" — pack count, then optional
    #    "cans"/"bottles" words, then the volume, in that order.
    m = re.search(
        r"(\d+)\s*(?:pk|pack|PK|PACK|Pack)\b[^\d]{0,20}?(\d+(?:\.\d+)?)\s*"
        + _VOLUME_UNIT,
        name,
        re.IGNORECASE,
    )
    if m:
        count = int(m.group(1))
        volume = _to_ml(float(m.group(2)), m.group(3))
        return count, _fix_if_total_not_per_unit(count, volume)

    # 2b. Reverse order — "330ml 6 pack", "250ml 12pk" — volume stated
    # before the pack count instead of after.
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*" + _VOLUME_UNIT + r"[^\d]{0,20}?(\d+)\s*(?:pk|pack|PK|PACK|Pack)\b",
        name,
        re.IGNORECASE,
    )
    if m:
        volume = _to_ml(float(m.group(1)), m.group(2))
        count = int(m.group(3))
        return count, _fix_if_total_not_per_unit(count, volume)

    # 3. "10 can pack" style — count before "can pack", no volume given.
    m = re.search(r"(\d+)\s*can\s*pack\b", name, re.IGNORECASE)
    if m:
        return int(m.group(1)), _bottle_default(name, category)

    # 4. Pack count with no volume anywhere nearby — e.g. "6pk cans",
    #    "12pk Btls".
    m = re.search(r"(\d+)\s*(?:pk|pack)\b", name, re.IGNORECASE)
    if m:
        return int(m.group(1)), _bottle_default(name, category)

    # 5. Single volume, no pack count — e.g. "Martell VSOP 700ml",
    #    "Country Red 3l" (single cask/bottle item).
    m = re.search(r"(\d+(?:\.\d+)?)\s*" + _VOLUME_UNIT, name)
    if m:
        volume = _to_ml(float(m.group(1)), m.group(2))
        return 1, volume

    # 6. Nothing parseable (e.g. "Fat Bird Chardonnay", "KONRAD GRÜNER
    #    VELTLINER 2022"). Wine is the one category sold almost exclusively
    #    in a single standard size — defaulting a nameless wine bottle to
    #    750mL is safe in a way that guessing a beer/RTD/spirits size isn't
    #    (those genuinely vary: 330/440/500mL cans, 700mL/1L spirits, etc).
    #    Confirmed this covers ~9,900 real unparsed wine rows, all plain
    #    varietal names with literally no digit anywhere.
    if category == "wine":
        return 1, 750
    return 1, _bottle_default(name, category)


if __name__ == "__main__":
    import csv

    samples = []
    for fname in ["independent_store_prices.csv", "chain_store_prices.csv"]:
        try:
            with open(fname, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    samples.append((row["product_name"], row.get("category")))
        except FileNotFoundError:
            pass

    parsed = 0
    unparsed = 0
    for name, category in samples:
        count, volume = parse_pack_size(name, category)
        if volume is not None:
            parsed += 1
        else:
            unparsed += 1

    print(f"Total products: {len(samples)}")
    print(f"Volume successfully parsed: {parsed} ({parsed/len(samples)*100:.1f}%)")
    print(f"Volume unparseable (fallback used): {unparsed} ({unparsed/len(samples)*100:.1f}%)")
