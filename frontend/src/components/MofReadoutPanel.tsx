// MofReadoutPanel.tsx
//
// Renders the pore-fit readout (LCD/PLD, ion radii, fit verdict) as
// normal HTML below the Skulpt canvas. This used to be drawn as tiny
// turtle-graphics text inside the diagram itself — including an arc-text
// "Hydration Shell" label — both of which were illegible at the sizes
// the canvas allows. The verdict math is unchanged; it's just computed
// server-side now (see api/views.py::_compute_pore_readout) and shipped
// as data instead of pixels.

import React from "react";
import type { ReadoutLine } from "./MOFInput";

interface MofReadoutPanelProps {
  lines: ReadoutLine[];
}

export const MofReadoutPanel: React.FC<MofReadoutPanelProps> = ({ lines }) => {
  if (!lines || lines.length === 0) return null;

  return (
    <div
      style={{
        marginTop: 12,
        padding: "10px 14px",
        border: "1px solid #ddd",
        borderRadius: 4,
        backgroundColor: "#fafafa",
        fontSize: 13,
        lineHeight: 1.6,
      }}
    >
      <div style={{ fontSize: 11, fontWeight: 600, color: "#888", marginBottom: 4 }}>
        Pore fit readout
      </div>
      <div style={{ fontSize: 11, color: "#999", marginBottom: 8, lineHeight: 1.5 }}>
        <strong>LCD</strong> = Largest Cavity Diameter, the biggest sphere that fits inside the pore.{" "}
      </div>
      <div style={{ fontSize: 11, color: "#999", marginBottom: 8, lineHeight: 1.5 }}>
        <strong>PLD</strong> = Pore Limiting Diameter, the narrowest bottleneck a guest ion must pass through.
      </div>
      {lines.map((line, i) => (
        <div key={i} style={{ color: line.color, fontWeight: i === lines.length - 2 ? 700 : 400 }}>
          {line.text}
        </div>
      ))}
    </div>
  );
};

export default MofReadoutPanel;