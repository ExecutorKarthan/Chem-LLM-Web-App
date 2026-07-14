import csv
import os
import re

# --- PATH CONFIGURATIONS ---
# This finds the directory where mof_registry_builder.py actually lives
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

SOURCE_CSV_PATH = os.path.join(CURRENT_DIR, "MOF_data.csv")
OUTPUT_LINKER_CSV = os.path.join(CURRENT_DIR, "registry_by_linkers.csv")
OUTPUT_METAL_CSV = os.path.join(CURRENT_DIR, "registry_by_metals.csv")

def clean_and_split_metals(metal_str):
    if not metal_str:
        return []
    raw_splits = re.split(r'[\.,\-_]', str(metal_str))
    return [m.strip() for m in raw_splits if m.strip()]

def clean_and_split_linkers(mof_id_str):
    if not mof_id_str:
        return []
    return [l.strip() for l in str(mof_id_str).split('.') if l.strip() and not re.match(r'^\[[A-Za-z]{1,2}\]$', l)]

def build_split_registries():
    print(f"🔄 Processing raw entries from: {CURRENT_DIR}...")
    print(f"🔄 Processing raw entries from: {SOURCE_CSV_PATH}...")
    
    if not os.path.exists(SOURCE_CSV_PATH):
        print(f"❌ Error: Source file not found at {SOURCE_CSV_PATH}")
        return

    # Intermediate tracking sets to prevent duplicate relational pairs
    linker_to_metals_map = {}
    metal_to_linkers_map = {}

    with open(SOURCE_CSV_PATH, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mof_id = row.get("mof_id") or row.get("identifier") or ""
            metal_field = row.get("metal") or row.get("metal_type") or ""
            
            metals = clean_and_split_metals(metal_field)
            linkers = clean_and_split_linkers(mof_id)
            
            for l in linkers:
                if l not in linker_to_metals_map:
                    linker_to_metals_map[l] = set()
                for m in metals:
                    linker_to_metals_map[l].add(m)

            for m in metals:
                if m not in metal_to_linkers_map:
                    metal_to_linkers_map[m] = set()
                for l in linkers:
                    metal_to_linkers_map[m].add(l)

    os.makedirs("assets", exist_ok=True)

    # 1. WRITE SHEET 1: Linkers -> Common Names -> Interacting Metals
    with open(OUTPUT_LINKER_CSV, mode='w', encoding='utf-8', newline='') as f1:
        writer1 = csv.writer(f1)
        writer1.writerow(["linker_smiles", "linker_common_name", "compatible_metals"])
        
        for smiles in sorted(linker_to_metals_map.keys()):
            common_name = COMMON_NAME_REGISTRY.get(smiles, f"Linker ({smiles[:12]}...)")
            # Join metals into a clean comma-separated string for that linker's row
            metals_str = ", ".join(sorted(linker_to_metals_map[smiles]))
            writer1.writerow([smiles, common_name, metals_str])

    # 2. WRITE SHEET 2 (The Reverse Map): Metals -> Interacting Linkers -> Common Names
    with open(OUTPUT_METAL_CSV, mode='w', encoding='utf-8', newline='') as f2:
        writer2 = csv.writer(f2)
        writer2.writerow(["metal", "compatible_linkers_smiles", "compatible_linkers_common_names"])
        
        for metal in sorted(metal_to_linkers_map.keys()):
            linkers_list = sorted(metal_to_linkers_map[metal])
            common_names_list = [COMMON_NAME_REGISTRY.get(l, f"Linker ({l[:12]}...)") for l in linkers_list]
            
            writer2.writerow([
                metal, 
                ", ".join(linkers_list), 
                ", ".join(common_names_list)
            ])

    print(f"✅ Success! Created Linker Map: {OUTPUT_LINKER_CSV}")
    print(f"✅ Success! Created Reverse Metal Map: {OUTPUT_METAL_CSV}")

if __name__ == "__main__":
    build_split_registries()