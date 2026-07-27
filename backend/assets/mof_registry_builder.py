"""
Offline, one-time (or run-when-MOF_data.csv-changes) builder script —
not imported by the Django app at runtime. Reads the raw MOF_data.csv
formula list, classifies each dot-separated component of every formula
as a metal, an organic linker, or an ignorable guest species (solvent/
counter-ion), and restricts the output to mono-metal + mono-linker
MOFs only (multi-metal or multi-linker rows are skipped, since the
frontend dropdowns model a MOF as one metal + one linker choice).
Looks up each unique linker's common name via PubChem, then writes two
CSVs — registry_by_linkers.csv and registry_by_metals.csv — which
mof_index.py loads at Django startup to answer "what linkers are valid
for this metal" (and vice versa) without hitting PubChem or re-parsing
MOF_data.csv on every request.
"""
import csv
import os
import re
import time
import pubchempy as pcp

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

SOURCE_CSV = os.path.join(CURRENT_DIR, "MOF_data.csv")
OUTPUT_LINKERS = os.path.join(CURRENT_DIR, "registry_by_linkers.csv")
OUTPUT_METALS = os.path.join(CURRENT_DIR, "registry_by_metals.csv")

# Bracket-atom elements that belong to a linker's own SMILES (e.g. [O-], [CH], [NH2])
# rather than representing a metal center.
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


def get_pubchem_common_name(smiles):
    """
    Looks up a linker's common/trivial name via PubChem by SMILES,
    preferring the first synonym (typically the most recognizable name)
    and falling back to the IUPAC name if no synonym is listed. Returns
    "" (not None) on any lookup failure or missing name, so callers can
    always write a string into the output CSV without a None check.
    """
    if not smiles or not smiles.strip():
        return ""
    try:
        compounds = pcp.get_compounds(smiles, namespace="smiles")
        if compounds:
            if compounds[0].synonyms:
                return compounds[0].synonyms[0]
            elif compounds[0].iupac_name:
                return compounds[0].iupac_name
    except Exception as e:
        print(f"  -> Warning: Could not fetch name for {smiles} ({e})")
    return ""


def build_registries():
    """
    Main pipeline, in three steps (see the print statements below for
    where each starts): parse MOF_data.csv into per-linker and
    per-metal registries (mono-metal/mono-linker rows only), fetch each
    unique linker's common name from PubChem once and cache it, then
    write both registry CSVs.
    """
    if not os.path.exists(SOURCE_CSV):
        print(f"Missing {SOURCE_CSV}")
        return

    # linker_smiles -> {"metals": set(), "mof_ids": set()}
    linker_registry = {}
    # metal -> {"linkers": set(), "mof_ids": set()}
    metal_registry = {}
    unique_linkers = set()

    print("Step 1: Parsing MOF data, classifying fragments, scoping to mono-metal/mono-linker rows...")
    with open(SOURCE_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # header

        for row in reader:
            if not row or not row[0].strip():
                continue

            formula = row[0]  # this IS the mof_id
            metal_elements = set()
            organic_fragments = []

            for component in formula.split("."):
                kind, value = classify_fragment(component)
                if kind == "metal":
                    metal_elements.update(value)
                elif kind == "organic":
                    organic_fragments.append(value)
                # "guest" fragments (solvents, counter-ions) are ignored

            # Scope: mono-metal AND mono-linker MOFs only.
            if len(metal_elements) != 1 or len(organic_fragments) != 1:
                continue

            metal = next(iter(metal_elements))
            linker = organic_fragments[0]
            unique_linkers.add(linker)

            linker_registry.setdefault(linker, {"metals": set(), "mof_ids": set()})
            linker_registry[linker]["metals"].add(metal)
            linker_registry[linker]["mof_ids"].add(formula)

            metal_registry.setdefault(metal, {"linkers": set(), "mof_ids": set()})
            metal_registry[metal]["linkers"].add(linker)
            metal_registry[metal]["mof_ids"].add(formula)

    print(f"Found {len(unique_linkers)} unique mono-linker linkers across mono-metal MOFs.")
    print("Step 2: Fetching common names from PubChem (this may take a moment)...")

    common_names_cache = {}
    for i, linker in enumerate(sorted(unique_linkers), 1):
        print(f"  [{i}/{len(unique_linkers)}] Querying: {linker}")
        common_names_cache[linker] = get_pubchem_common_name(linker)
        time.sleep(0.2)

    print("Step 3: Writing output files...")
    with open(OUTPUT_LINKERS, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["linker_smiles", "common_name", "compatible_metals", "mof_ids"])
        for linker, info in sorted(linker_registry.items()):
            writer.writerow([
                linker,
                common_names_cache.get(linker, ""),
                ", ".join(sorted(info["metals"])),
                "; ".join(sorted(info["mof_ids"])),
            ])

    with open(OUTPUT_METALS, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metal", "compatible_linkers", "common_names", "mof_ids"])
        for metal, info in sorted(metal_registry.items()):
            linkers = sorted(info["linkers"])
            names = [common_names_cache.get(l, "") for l in linkers]
            writer.writerow([
                metal,
                ", ".join(linkers),
                ", ".join(names),
                "; ".join(sorted(info["mof_ids"])),
            ])

    print(f"Created {OUTPUT_LINKERS}")
    print(f"Created {OUTPUT_METALS}")


if __name__ == "__main__":
    build_registries()