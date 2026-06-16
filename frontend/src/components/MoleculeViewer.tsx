import React, {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import initRDKitModule from "@rdkit/rdkit";
 
interface MoleculeViewerProps {
  smiles: string;
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
 
// ─── Component ────────────────────────────────────────────────────────────────
const MoleculeViewer: React.FC<MoleculeViewerProps> = ({ smiles }) => {
  // outerRef is the stable, fixed-size box we observe.
  // It uses position:relative + explicit height so the SVG inside
  // (which is position:absolute) can NEVER push it larger — breaking
  // the ResizeObserver → re-render → bigger SVG → ResizeObserver loop.
  const outerRef = useRef<HTMLDivElement>(null);
  const svgContainerRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);
 
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
 
  // ── Observe the OUTER wrapper only ────────────────────────────────────────
  // Because the SVG sits inside an absolutely-positioned child, it cannot
  // affect outerRef's size, so this observer never fires in a loop.
  useLayoutEffect(() => {
    if (!outerRef.current) return;
 
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      const w = Math.floor(width);
      const h = Math.floor(height);
 
      setDimensions((prev) => {
        if (Math.abs(prev.width - w) < 2 && Math.abs(prev.height - h) < 2) {
          return prev;
        }
        return { width: w, height: h };
      });
    });
 
    observer.observe(outerRef.current);
    return () => observer.disconnect();
  }, []);
 
  // ── Render molecule ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!svgContainerRef.current) return;
    if (dimensions.width < 10 || dimensions.height < 10) return;
 
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
              JSON.stringify({
                width: dimensions.width,
                height: dimensions.height,
              })
            );
 
            svgContainerRef.current!.innerHTML = svg;
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
          "Please ensure RDKit_minimal.wasm is present in the public/ folder."
        );
        setLoading(false);
      }
    };
 
    void renderMolecule();
 
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [smiles, dimensions.width, dimensions.height]);
 
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column" }}>
      <h3 style={{ margin: "0 0 8px 0" }}>Molecule Viewer</h3>
 
      {/* Status messages — outside the observed box so they don't affect its size */}
      {loading && (
        <div style={{ color: "#555", marginBottom: 8 }}>Loading molecule...</div>
      )}
      {error && (
        <div style={{ color: "red", marginBottom: 8 }}>{error}</div>
      )}
      {!smiles && !loading && !error && (
        <div style={{ color: "#666", marginBottom: 8 }}>
          Enter a SMILES string and click Render.
        </div>
      )}
 
      {/* Stable outer box — position:relative + maxHeight so the
          absolutely-positioned SVG child can never make it grow */}
      <div
        ref={outerRef}
        style={{
          position: "relative",
          flex: 1,
          width: "100%",
          minHeight: 300,
          maxHeight: 400,
          overflow: "hidden",
        }}
      >
        {/* SVG lives here — position:absolute means it fills the parent
            without contributing to its layout size */}
        <div
          ref={svgContainerRef}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
          }}
        />
      </div>
    </div>
  );
};
 
export default MoleculeViewer;
 