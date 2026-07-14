import csv
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REGISTRY_LINKERS_PATH = CURRENT_DIR / "registry_by_linkers.csv"
REGISTRY_METALS_PATH = CURRENT_DIR / "registry_by_metals.csv"
MOF_DATA_CSV_PATH = CURRENT_DIR / "MOF_data.csv"


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
    """Loads MOF_data.csv into {formula (mof_id): {"lcd": float, "pld": float}}."""
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