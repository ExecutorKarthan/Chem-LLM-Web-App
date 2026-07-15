import React, {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import initRDKitModule from "@rdkit/rdkit";

interface MoleculeViewerProps {
  smiles: string[];
  substructure: string;
  linkerName?: string;    // Kept for backward compatibility with MOF Explorer
  linkerNames?: string[]; // ADDED: Prop for the common names array
}

// ─── RDKit singleton ──────────────────────────────────────────────────────────
let rdkitPromise: Promise<any> | null = null;

const getRDKit = () => {
  if (!rdkitPromise) {
    rdkitPromise = initRDKitModule({
      locateFile: (file: string) => `/${file}`,
    });
  }
  return rdkitPromise;
};

// ─── Single molecule panel ────────────────────────────────────────────────────
interface MoleculePanelProps {
  smiles: string;
  label: string;
  substructure: string;
}

const MoleculePanel: React.FC<MoleculePanelProps> = ({ smiles, label, substructure }) => {
  const outerRef = useRef<HTMLDivElement>(null);
  const svgContainerRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);

  const [error, setError] = useState("");
  const [matchNote, setMatchNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [width, setWidth] = useState(0);

  // Observe width only — height is derived so it can never feed back
  useLayoutEffect(() => {
    if (!outerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const w = Math.floor(entries[0].contentRect.width);
      setWidth((prev) => (Math.abs(prev - w) < 2 ? prev : w));
    });
    observer.observe(outerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!svgContainerRef.current) return;
    if (width < 10) return;

    const height = Math.round(width * 0.3);

    const renderMolecule = async (): Promise<void> => {
      if (!svgContainerRef.current) return;

      if (!smiles.trim()) {
        svgContainerRef.current.innerHTML = "";
        setError("");
        setMatchNote("");
        setLoading(false);
        return;
      }

      setLoading(true);
      setError("");
      setMatchNote("");

      try {
        const RDKit = await getRDKit();
        if (rafRef.current) cancelAnimationFrame(rafRef.current);

        rafRef.current = requestAnimationFrame(() => {
          let mol: any = null;
          let qmol: any = null;

          try {
            mol = RDKit.get_mol(smiles);

            if (!mol || !mol.is_valid()) {
              svgContainerRef.current!.innerHTML = "";
              setError("Invalid SMILES string — please check your input.");
              return;
            }

            let mdetails: Record<string, any> = { width, height };

            if (substructure.trim()) {
              try {
                qmol = RDKit.get_qmol(substructure.trim());
                if (qmol && qmol.is_valid()) {
                  const matchJson = mol.get_substruct_match(qmol);
                  const match = JSON.parse(matchJson);
                  const hasMatch = match.atoms && match.atoms.length > 0;

                  if (hasMatch) {
                    mdetails = { ...match, width, height };
                    setMatchNote("✓ Substructure match found");
                  } else {
                    setMatchNote("No substructure match");
                  }
                } else {
                  setMatchNote("Invalid substructure query");
                }
              } catch (subErr) {
                console.warn("Substructure search error:", subErr);
                setMatchNote("Substructure search failed");
              }
            }

            const svg = mol.get_svg_with_highlights(JSON.stringify(mdetails));
            const patched = svg
              .replace(/width="\d+"/, `width="100%"`)
              .replace(/height="\d+"/, `height="${height}"`);

            svgContainerRef.current!.innerHTML = patched;
            setError("");
          } catch (err) {
            console.error("RDKit rendering error:", err);
            svgContainerRef.current!.innerHTML = "";
            setError("Failed to render molecule.");
          } finally {
            mol?.delete?.();
            qmol?.delete?.();
            setLoading(false);
          }
        });
      } catch (err) {
        console.error("Failed to initialize RDKit:", err);
        if (svgContainerRef.current) svgContainerRef.current.innerHTML = "";
        setError(
          "Failed to initialize the chemistry renderer. " +
          "Please ensure RDKit_minimal.wasm is present in dist/."
        );
        setLoading(false);
      }
    };

    void renderMolecule();
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [smiles, substructure, width]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        border: "1px solid #eee",
        borderRadius: 4,
        padding: 8,
        boxSizing: "border-box",
        minWidth: 0,
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 2 }}>
        {label}
      </div>
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 10,
          color: "#aaa",
          marginBottom: 4,
          wordBreak: "break-all",
          lineHeight: 1.3,
        }}
      >
        {smiles}
      </div>
      {loading && <div style={{ color: "#555", fontSize: 12 }}>Rendering...</div>}
      {error && <div style={{ color: "red", fontSize: 12 }}>{error}</div>}
      {matchNote && (
        <div
          style={{
            fontSize: 11,
            marginBottom: 4,
            color: matchNote.startsWith("✓")
              ? "#389e0d"
              : matchNote === "No substructure match"
              ? "#888"
              : "#d46b08",
          }}
        >
          {matchNote}
        </div>
      )}
      <div ref={outerRef} style={{ width: "100%", overflow: "hidden" }}>
        <div ref={svgContainerRef} style={{ width: "100%", lineHeight: 0 }} />
      </div>
    </div>
  );
};

// ─── Main viewer ──────────────────────────────────────────────────────────────
const MoleculeViewer: React.FC<MoleculeViewerProps> = ({ smiles, substructure, linkerName, linkerNames }) => {
  if (!smiles || smiles.length === 0) {
    return (
      <div style={{ width: "100%" }}>
        <h3 style={{ margin: "0 0 8px 0" }}>Molecule Viewer</h3>
        <div style={{ color: "#666", fontSize: 13 }}>
          Enter a SMILES string and click Render.
        </div>
      </div>
    );
  }

  return (
    <div style={{ width: "100%" }}>
      <h3 style={{ margin: "0 0 12px 0" }}>Molecule Viewer</h3>
      
      {/* Show single linker name if provided (MOF Explorer mode) */}
      {linkerName && (
        <div style={{ 
          textAlign: "center", 
          marginBottom: 16, 
          fontWeight: 700, 
          color: "#333",
          fontSize: 14 
        }}>
          {linkerName}
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: smiles.length === 1 ? "1fr" : "repeat(2, minmax(0, 1fr))",
          gap: 12,
        }}
      >
      {smiles.map((s, i) => (
        <MoleculePanel
          key={`${i}-${s}`}
          smiles={s}
          // Prioritize linkerNames array, fallback to single linkerName, then default label
          label={linkerNames?.[i] || linkerName || `Molecule ${i + 1}`} 
          substructure={substructure}
        />
      ))}
      </div>
    </div>
  );
};

export default MoleculeViewer;