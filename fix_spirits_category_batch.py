"""
Cheapie — one-off: fix products mis-categorized as "spirits" that are
genuinely ready-to-drink (RTD) canned/bottled premixed cocktails.

Reported directly: clicking Spirits showed RTDs and beers, with the
observation that genuine spirits products don't usually come in packs —
they're sold by volume (mL/L). Investigated the actual data: most
"spirits" rows with pack-size naming ARE genuinely correct (real gift
sets/cases of full bottles — e.g. "Gordon's Gin 6x1 Litre", "Glenfiddich
Single Malt Collection 3x200ml"), so a blanket "any pack = wrong" rule
would have broken those. The real signal that held up: genuine spirits
bottles are essentially never sold as "Cans", and any pack at 700mL+ per
unit is always a bulk case of real bottles, never an RTD. Below that
threshold, an explicit "Cans" mention, a known RTD/premix brand (Af,
Alba, Le Coq, Batched, Zonzo, Elta Ego), or cocktail-mixer language
(Margarita, Spritz, "& Tonic", "and Cola", ...) reliably identifies a
genuinely mis-tagged RTD — while gift-set language (Gift Pack/Box,
Collection, Discovery, Master's Selection) protects genuine spirits sets
that would otherwise false-positive on some of those same keywords.

81 rows matched this confident ruleset — see reclassify_final.json
(generated locally, not committed) for the exact list this was built
from. ~19 more remained genuinely ambiguous and were deliberately left
untouched rather than guessed at.

Delete this file after running once — it's a one-time data fix, not a
recurring job.

HOW TO RUN:
    export SUPABASE_URL="https://your-project-ref.supabase.co"
    export SUPABASE_KEY="your-service-role-or-secret-key"
    python3 fix_spirits_category_batch.py
"""
import os
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY environment variables first.")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# Exact row ids to reclassify, captured at audit time.
ROW_IDS = [1075406, 29913, 29914, 2383382, 2383405, 2383441, 2383400, 2383449, 1086119, 1088007, 1088008, 2001059, 1100110, 1100111, 1100112, 1100113, 1107509, 87240, 29812, 1124153, 44855, 24399, 24402, 24486, 44987, 89015, 89016, 89563, 95012, 563181, 1531378, 91149, 92578, 560543, 560616, 2383425, 2383446, 2383447, 2383468, 563180, 563229, 87241, 87890, 87891, 89958, 89959, 91150, 92535, 93932, 95013, 95775, 96002, 96003, 3540393, 3540394, 2029257, 3248602, 93931, 2383403, 2383401, 2383402, 2383466, 1044364, 560544, 563890, 563891, 3540939, 2606, 2607, 29915, 29917, 2383398, 2383404, 2383465, 2383467, 2383470, 3539747, 1059194, 29916, 2383431, 1088061]


def main():
    fixed = 0
    failed = 0
    for row_id in ROW_IDS:
        resp = requests.patch(
            f"{SUPABASE_URL}/rest/v1/products?id=eq.{row_id}",
            headers={**HEADERS, "Prefer": "return=minimal"},
            json={"category": "rtd"},
            timeout=15,
        )
        if resp.status_code in (200, 204):
            fixed += 1
        else:
            failed += 1
            print(f"  FAILED id={row_id}: {resp.status_code} {resp.text}")

    print(f"\nDone. Fixed {fixed} rows, {failed} failed, out of {len(ROW_IDS)} total.")


if __name__ == "__main__":
    main()
