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

_ML_UNIT = r"(?:ml|mL|ML|Ml)"
_L_UNIT = r"(?:litres?|Litres?|LITRES?|ltrs?|Ltrs?|LTRS?|l|L)\b"


def _to_ml(value, unit):
    unit = unit.lower()
    if unit.startswith("l"):
        return value * 1000
    return value


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


def parse_pack_size(name):
    if not name:
        return 1, None

    # 1. "6x330ml", "12 x 330ml", "6x1 Litre", "10x250ml", "6x 330ml"
    m = re.search(
        r"(\d+)\s*[xX]\s*(\d+(?:\.\d+)?)\s*(" + _ML_UNIT + "|" + _L_UNIT + ")",
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
        r"(\d+)\s*(?:pk|pack|PK|PACK|Pack)\b[^\d]{0,20}?(\d+(?:\.\d+)?)\s*("
        + _ML_UNIT
        + "|"
        + _L_UNIT
        + ")",
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
        r"(\d+(?:\.\d+)?)\s*(" + _ML_UNIT + "|" + _L_UNIT + r")[^\d]{0,20}?(\d+)\s*(?:pk|pack|PK|PACK|Pack)\b",
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
        return int(m.group(1)), None

    # 4. Pack count with no volume anywhere nearby — e.g. "6pk cans".
    m = re.search(r"(\d+)\s*(?:pk|pack)\b", name, re.IGNORECASE)
    if m:
        return int(m.group(1)), None

    # 5. Single volume, no pack count — e.g. "Martell VSOP 700ml",
    #    "Country Red 3l" (single cask/bottle item).
    m = re.search(r"(\d+(?:\.\d+)?)\s*(" + _ML_UNIT + "|" + _L_UNIT + ")", name)
    if m:
        volume = _to_ml(float(m.group(1)), m.group(2))
        return 1, volume

    # 6. Nothing parseable (e.g. "Fat Bird Chardonnay", "KONRAD GRÜNER
    #    VELTLINER 2022") — treat as a single unit, unknown volume.
    return 1, None


if __name__ == "__main__":
    import csv

    samples = []
    for fname in ["independent_store_prices.csv", "chain_store_prices.csv"]:
        try:
            with open(fname, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    samples.append(row["product_name"])
        except FileNotFoundError:
            pass

    parsed = 0
    unparsed = 0
    for name in samples:
        count, volume = parse_pack_size(name)
        if volume is not None:
            parsed += 1
        else:
            unparsed += 1

    print(f"Total products: {len(samples)}")
    print(f"Volume successfully parsed: {parsed} ({parsed/len(samples)*100:.1f}%)")
    print(f"Volume unparseable (fallback used): {unparsed} ({unparsed/len(samples)*100:.1f}%)")
