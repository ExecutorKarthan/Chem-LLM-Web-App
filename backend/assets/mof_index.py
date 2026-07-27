"""
Runtime MOF lookup index, built once when Django starts (module-level
code below runs at import time, not per-request).

Two separate sets of dicts exist here for two different jobs:
  - METAL_TO_LINKERS / LINKER_TO_METALS / LINKER_TO_NAME: which
    metal/linker combinations are valid at all, used to populate and
    filter the frontend's dropdowns (see views.get_mof_meta and
    views.filter_mofs_dropdown).
  - METAL_TO_MOF_IDS / LINKER_TO_MOF_IDS / MOF_METRICS: given a
    specific validated metal+linker pair, which exact MOF entry (by
    formula/mof_id) it corresponds to, via set intersection in
    `find_mof`, and that entry's pore metrics.
Both are sourced from the same underlying registry CSVs, just indexed
differently for these two different query patterns.
"""
import csv
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REGISTRY_LINKERS_PATH = CURRENT_DIR / "registry_by_linkers.csv"
REGISTRY_METALS_PATH = CURRENT_DIR / "registry_by_metals.csv"
MOF_DATA_CSV_PATH = CURRENT_DIR / "MOF_data.csv"

# Global dictionaries
METAL_TO_LINKERS = {}
LINKER_TO_METALS = {}
LINKER_TO_NAME = {}

def load_registries():
    """
    Populates METAL_TO_LINKERS, LINKER_TO_METALS, and LINKER_TO_NAME
    from the two registry CSVs — used for dropdown population/filtering,
    as opposed to _load_id_registry below which builds the separate
    mof_id lookup dicts used by find_mof.
    """
    global METAL_TO_LINKERS, LINKER_TO_METALS, LINKER_TO_NAME
    
    # 1. Process registry_by_metals.csv
    with open(REGISTRY_METALS_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            metal = row["metal"].strip()
            linkers = [l.strip() for l in row["compatible_linkers"].split(",")]
            METAL_TO_LINKERS[metal] = set(linkers)

    # 2. Process registry_by_linkers.csv
    with open(REGISTRY_LINKERS_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            linker = row["linker_smiles"].strip()
            name = row.get("common_name", "").strip() # Extract common name
            
            # Map linker to name
            if name:
                LINKER_TO_NAME[linker] = name
                
            # Map metals
            metals = [m.strip() for m in row["compatible_metals"].split(",")]
            LINKER_TO_METALS[linker] = set(metals)

# Call this once at startup
load_registries()

def _load_id_registry(path, key_column, ids_column):
    """Loads a registry CSV into {key: set(mof_ids)}."""
    registry = {}
    if not path.is_file():
        return registry

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = row.get(key_column, "").strip()
            ids_raw = row.get(ids_column, "").strip()
            if not key:
                continue
            mof_ids = {mid.strip() for mid in ids_raw.split(";") if mid.strip()}
            registry[key] = mof_ids
    return registry


def _load_mof_metrics():
    """
    Loads MOF_data.csv into {formula (mof_id): {"lcd": float, "pld": float}}.

    Reads by column position (row[0]/row[1]/row[2]) rather than
    DictReader + header name lookups like the other loaders in this
    file use, because MOF_data.csv's headers contain mojibake
    (encoding-corrupted) text that doesn't match cleanly by name — the
    columns' meaning and order (identifier, LCD, PLD, ...) is stable
    even though the header text itself isn't reliable.
    """
    metrics = {}
    if not MOF_DATA_CSV_PATH.is_file():
        return metrics

    with open(MOF_DATA_CSV_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if not row or not row[0].strip():
                continue
            formula = row[0]
            try:
                lcd = float(row[1]) if row[1].strip() else None
                pld = float(row[2]) if row[2].strip() else None
            except (ValueError, IndexError):
                lcd = pld = None
            metrics[formula] = {"lcd": lcd, "pld": pld}
    return metrics


# Built once at Django process startup.
METAL_TO_MOF_IDS = _load_id_registry(REGISTRY_METALS_PATH, "metal", "mof_ids")
LINKER_TO_MOF_IDS = _load_id_registry(REGISTRY_LINKERS_PATH, "linker_smiles", "mof_ids")
MOF_METRICS = _load_mof_metrics()


def find_mof(metal: str, linker: str):
    """
    Cross-references the metal's and linker's candidate mof_id lists.
    Returns the shared mof_id (the formula string) or None if no overlap exists.
    """
    metal = (metal or "").strip()
    linker = (linker or "").strip()
    if not metal or not linker:
        return None

    candidates = METAL_TO_MOF_IDS.get(metal, set()) & LINKER_TO_MOF_IDS.get(linker, set())
    return next(iter(candidates), None)


def get_metrics(mof_id: str):
    """Returns {"lcd": ..., "pld": ...} for a given mof_id (formula), or None."""
    return MOF_METRICS.get(mof_id)