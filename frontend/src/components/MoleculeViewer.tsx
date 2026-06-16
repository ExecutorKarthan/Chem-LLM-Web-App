import React, {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import initRDKitModule from "@rdkit/rdkit";

interface MoleculeViewerProps {
  smiles: string[];
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
}

const MoleculePanel: React.FC<MoleculePanelProps> = ({ smiles, label }) => {
  const outerRef = useRef<HTMLDivElement>(null);
  const svgContainerRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  // Width-only: we let height be determined by the SVG aspect ratio
  const [width, setWidth] = useState(0);

  // Observe container width only — height is derived, never fed back in
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

    // Height is 60% of width — tall enough to hold any molecule,
    // never wider than the container, and scales with screen size.
    const height = Math.round(width * 0.2);

    const renderMolecule = async (): Promise<void> => {
      if (!svgContainerRef.current) return;

      if (!smiles.trim()) {
        svgContainerRef.current.innerHTML = "";
        setError("");
        setLoading(false);
        return;
      }

      setLoading(true);
      setError("");

      try {
        const RDKit = await getRDKit();

        if (rafRef.current) cancelAnimationFrame(rafRef.current);

        rafRef.current = requestAnimationFrame(() => {
          let mol: any = null;
          try {
            mol = RDKit.get_mol(smiles);

            if (!mol || !mol.is_valid()) {
              svgContainerRef.current!.innerHTML = "";
              setError("Invalid SMILES string — please check your input.");
              return;
            }

            const svg = mol.get_svg_with_highlights(
              JSON.stringify({ width, height })
            );

            // Make SVG fully fluid so it never overflows narrow screens
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
  }, [smiles, width]);

  return (
    <div
      style={{
        width: "100%",
        borderBottom: "1px solid #eee",
        paddingBottom: 12,
        marginBottom: 12,
      }}
    >
      {/* Label */}
      <div style={{ fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 4 }}>
        {label}
      </div>

      {/* SMILES string display */}
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 11,
          color: "#888",
          marginBottom: 6,
          wordBreak: "break-all",
        }}
      >
        {smiles}
      </div>

      {loading && <div style={{ color: "#555", fontSize: 13 }}>Rendering...</div>}
      {error && <div style={{ color: "red", fontSize: 13 }}>{error}</div>}

      {/* outerRef measures available width; svgContainer holds the SVG.
          No position:absolute needed here because height is explicitly
          set on the SVG itself — it cannot feed back into the observer. */}
      <div ref={outerRef} style={{ width: "100%", overflow: "hidden" }}>
        <div ref={svgContainerRef} style={{ width: "100%", lineHeight: 0 }} />
      </div>
    </div>
  );
};

// ─── Main viewer — renders one panel per SMILES entry ────────────────────────
const MoleculeViewer: React.FC<MoleculeViewerProps> = ({ smiles }) => {
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
      {smiles.map((s, i) => (
        <MoleculePanel
          key={`${i}-${s}`}
          smiles={s}
          label={`Molecule ${i + 1}`}
        />
      ))}
    </div>
  );
};

export default MoleculeViewer;