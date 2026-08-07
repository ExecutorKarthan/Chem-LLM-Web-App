"""
clean_mof_data.py

Filters MOF_data.csv down to rows that contain exactly ONE distinct
metal element AND exactly ONE distinct organic linker -- i.e. true
mono-metal, mono-linker MOFs. This is intentionally stricter than (and
independent of) the mono-metal/mono-linker scoping already inside
mof_registry_builder.py: that script's `len(organic_fragments) != 1`
check counts raw fragment occurrences, so a formula with two COPIES of
the identical linker (e.g. two crystallographically independent
instances of the same molecule in the asymmetric unit -- common and
chemically fine) gets excluded there just like a formula with two
DIFFERENT linkers would. This script instead dedupes fragments by
distinct value before counting, so duplicate copies of the same
linker/metal are allowed through, and only genuinely mixed-linker or
mixed-metal MOFs are removed.

Classification logic (classify_fragment) is copied verbatim from
mof_registry_builder.py so a fragment is judged "metal" / "organic" /
"guest" identically to how the rest of your pipeline already treats it.

Usage:
    python clean_mof_data.py

Reads:  MOF_data.csv          (source, untouched)
Writes: MOF_data_clean.csv    (filtered copy -- same header row,
                                same column order, mojibake header
                                text preserved as-is)

After running, review the summary counts printed below, then:
  1. Sanity-check MOF_data_clean.csv looks right.
  2. Replace MOF_data.csv with it (or point mof_registry_builder.py /
     mof_index.py / the app's MOF_DATA_CSV_PATH at the new file).
  3. Re-run mof_registry_builder.py to regenerate registry_by_linkers.csv
     and registry_by_metals.csv from the cleaned data -- those are stale
     until you do.
"""
import csv
import os
import re

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_CSV = os.path.join(CURRENT_DIR, "RAW_MOF_data.csv")
OUTPUT_CSV = os.path.join(CURRENT_DIR, "MOF_data.csv")

# ── Copied verbatim from mof_registry_builder.py so classification
# behaves identically to the rest of the pipeline. ──────────────────────
NON_METAL_BRACKET_ELEMENTS = {
    "H", "C", "N", "O", "S", "P", "F", "Cl", "Br", "I", "Se", "Si", "B", "As", "Te"
}

_BRACKET_RE = re.compile(r"\[[^\]]*\]")
_BRACKET_ATOM_RE = re.compile(r"\[([A-Z][a-z]?)")


def classify_fragment(fragment: str):
    """
    Classifies one dot-separated formula fragment as:
      ("metal", [elements])  - a metal atom or metal-oxo cluster
      ("organic", fragment)  - a real linker (has a carbon skeleton)
      ("guest", fragment)    - solvent / counter-ion / other non-linker species
    """
    fragment = fragment.strip()
    if not fragment:
        return ("guest", fragment)

    stripped = _BRACKET_RE.sub("", fragment)
    residual_letters = re.sub(r"[^A-Za-z]", "", stripped)

    if "C" in residual_letters or "c" in residual_letters:
        return ("organic", fragment)

    if not residual_letters:
        atoms = _BRACKET_ATOM_RE.findall(fragment)
        metal_atoms = [a for a in atoms if a not in NON_METAL_BRACKET_ELEMENTS]
        if metal_atoms:
            return ("metal", metal_atoms)
        return ("guest", fragment)

    return ("guest", fragment)


def clean_mof_data():
    if not os.path.exists(SOURCE_CSV):
        print(f"Missing {SOURCE_CSV}")
        return

    total_rows = 0
    kept_rows = []
    removed_multi_metal = []
    removed_multi_linker = []
    removed_both = []

    print("Reading and classifying MOF_data.csv...")
    with open(SOURCE_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)

        for row in reader:
            if not row or not row[0].strip():
                continue
            total_rows += 1

            formula = row[0]
            metal_elements = set()
            organic_fragments = set()  # deduped by distinct value, unlike the builder script

            for component in formula.split("."):
                kind, value = classify_fragment(component)
                if kind == "metal":
                    metal_elements.update(value)
                elif kind == "organic":
                    organic_fragments.add(value)
                # "guest" fragments (solvents, counter-ions) are ignored,
                # same as in mof_registry_builder.py

            is_multi_metal = len(metal_elements) > 1
            is_multi_linker = len(organic_fragments) > 1

            if is_multi_metal and is_multi_linker:
                removed_both.append(formula)
            elif is_multi_metal:
                removed_multi_metal.append(formula)
            elif is_multi_linker:
                removed_multi_linker.append(formula)
            else:
                kept_rows.append(row)

    print("Writing MOF_data_clean.csv...")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(kept_rows)

    removed_total = len(removed_multi_metal) + len(removed_multi_linker) + len(removed_both)

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total rows read:              {total_rows}")
    print(f"Kept (mono-metal, mono-linker): {len(kept_rows)}")
    print(f"Removed (multiple metals only):  {len(removed_multi_metal)}")
    print(f"Removed (multiple linkers only): {len(removed_multi_linker)}")
    print(f"Removed (both):                  {len(removed_both)}")
    print(f"Total removed:                    {removed_total}")
    print()
    print(f"Wrote {len(kept_rows)} rows to {OUTPUT_CSV}")

    # Show a handful of examples so you can sanity-check the filtering decisions
    def preview(label, formulas, n=5):
        if not formulas:
            return
        print(f"\nExample formulas removed ({label}):")
        for formula in formulas[:n]:
            print(f"  {formula}")
        if len(formulas) > n:
            print(f"  ... and {len(formulas) - n} more")

    preview("multiple metals", removed_multi_metal)
    preview("multiple linkers", removed_multi_linker)
    preview("both", removed_both)


if __name__ == "__main__":
    clean_mof_data()
