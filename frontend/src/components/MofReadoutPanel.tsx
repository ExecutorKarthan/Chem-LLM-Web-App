// MofReadoutPanel.tsx
//
// Renders the pore-fit readout (LCD/PLD, ion radii, fit verdict) as
// normal HTML below the Skulpt canvas. This used to be drawn as tiny
// turtle-graphics text inside the diagram itself — including an arc-text
// "Hydration Shell" label — both of which were illegible at the sizes
// the canvas allows. The verdict math is unchanged; it's just computed
// server-side now (see api/views.py::_compute_pore_readout) and shipped
// as data instead of pixels.

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

export interface PoreReadout {
  lcd: number;
  pld: number;
  lcd_radius: number;
  pld_radius: number;
  guest_ion: string | null;
  guest_ion_known: boolean | null;
  guest_ionic_radius: number | null;
  guest_hydrated_radius: number | null;
  guest_ion_source: string | null;
}

interface MofReadoutPanelProps {
  readout: PoreReadout | null;
}

export const MofReadoutPanel: React.FC<MofReadoutPanelProps> = ({ readout }) => {
  if (!readout) return null;

  const { lcd, pld, lcd_radius, pld_radius, guest_ion, guest_ion_known, guest_ionic_radius, guest_hydrated_radius, guest_ion_source } = readout;

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
        <strong>LCD</strong> = Largest Cavity Diameter, the biggest sphere that fits inside the pore.
      </div>
      <div style={{ fontSize: 11, color: "#999", marginBottom: 8, lineHeight: 1.5 }}>
        <strong>PLD</strong> = Pore Limiting Diameter, the narrowest bottleneck a guest ion must pass through.
      </div>

      <div style={{ color: "blue" }}>
        {`Extracted metrics -> LCD: ${lcd.toFixed(5)} \u00c5 | PLD: ${pld.toFixed(5)} \u00c5.`}
      </div>
      <div style={{ color: "#D81B60" }}>
        {`Cavity radius (LCD / 2): ${lcd_radius.toFixed(2)} \u00c5`}
      </div>
      <div style={{ color: "#994F00" }}>
        {`Bottleneck radius (PLD / 2): ${pld_radius.toFixed(2)} \u00c5`}
      </div>

      {guest_ion_known === true && (
        <>
          <div style={{ color: "#4B0092" }}>
            {`Guest ion ionic radius: ${guest_ionic_radius!.toFixed(2)} \u00c5`}
          </div>
          {guest_hydrated_radius !== null && (
            <div style={{ color: "#56B4E9" }}>
              {`Guest ion hydrated radius: ${guest_hydrated_radius.toFixed(2)} \u00c5`}
            </div>
          )}
          {guest_ion_source !== null && (
            <div style={{ color: "#e818de" }}>
              {`Guest ion size is: ${guest_ion_source}`}
            </div>
          )}
        </>
      )}
      {guest_ion_known === false && (
        <div style={{ color: "#8B949E" }}>
          {`Ion '${guest_ion}' not in radii database`}
        </div>
      )}
    </div>
  );
};

export default MofReadoutPanel;