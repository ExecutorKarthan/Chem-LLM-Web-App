// MOFInput.tsx
//
// Left-panel input for the MOF pore-fit visualizer. Collects metal symbol,
// metal charge, linker SMILES, and (optionally) a guest ion, then builds
// the Python source string that SkulptDisplay executes via Skulpt/turtle.
//
// The generated code imports MOFRenderer from our backend-served
// mof_renderer.py (see SkulptDisplay's builtinRead / MOF_ENGINE_MODULES).

import React, { useState } from "react";
import { Input, InputNumber, Select, Button, Switch, Tooltip } from "antd";
import { QuestionCircleOutlined } from "@ant-design/icons";

interface MOFInputProps {
  onGenerateCode: (code: string) => void;
}

// Ions present in mof_renderer.py's ION_RADII table. Keeping this in sync
// lets the dropdown only offer ions the renderer can actually look up.
const GUEST_IONS = [
  "Li+", "Na+", "K+", "Rb+", "Cs+",
  "Be2+", "Mg2+", "Ca2+", "Sr2+", "Ba2+",
  "Cu+", "Cu2+", "Zn2+", "Ni2+", "Co2+", "Co3+",
  "Mn2+", "Mn3+", "Mn4+", "Mn7+",
  "Fe2+", "Fe3+", "Cr2+", "Cr3+", "Cr6+",
  "Ti2+", "Ti3+", "Ti4+", "V2+", "V3+", "V4+", "V5+",
  "Al3+", "Ga3+", "In3+", "Sn2+", "Sn4+", "Pb2+", "Pb4+",
  "Sc3+", "Y3+", "La3+", "Ce3+", "Ce4+", "Nd3+", "Gd3+", "Lu3+",
  "Ac3+", "Th4+", "Pa4+", "Pa5+", "U3+", "U4+", "U6+",
  "Np3+", "Np4+", "Pu3+", "Pu4+", "Am3+", "Am4+",
];

const COMMON_METALS = ["Zn", "Cu", "Fe", "Co", "Ni", "Mn", "Cd", "Al", "Cr", "Mg"];

const EXAMPLE_LINKERS: Record<string, string> = {
  "Terephthalate (BDC)": "[O-]C(=O)c1ccc(cc1)C(=O)[O-]",
  "Trimesate (BTC)": "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]",
  "Fumarate": "[O-]C(=O)C=CC(=O)[O-]",
};

const MOFInput: React.FC<MOFInputProps> = ({ onGenerateCode }) => {
  const [metal, setMetal] = useState<string>("Zn");
  const [charge, setCharge] = useState<number>(2);
  const [linker, setLinker] = useState<string>(EXAMPLE_LINKERS["Terephthalate (BDC)"]);
  const [guestIon, setGuestIon] = useState<string | undefined>("Na+");
  const [simpleMode, setSimpleMode] = useState<boolean>(false);
  const [showGuest, setShowGuest] = useState<boolean>(true);

  const buildPythonCode = (): string => {
    const safeLinker = linker.trim().replace(/"/g, '\\"');
    const guestArg = showGuest && guestIon ? `"${guestIon}"` : "None";

    const drawMethod = simpleMode
      ? (showGuest ? "draw_simple_with_guest" : "draw_simple_without_guest")
      : (showGuest ? "draw_with_guest" : "draw_without_guest");

    return [
      "import turtle",
      "from mof_renderer import MOFRenderer",
      "",
      "screen = turtle.Screen()",
      "screen.tracer(0)",
      "t = turtle.Turtle()",
      "t.speed(0)",
      "t.hideturtle()",
      "",
      `renderer = MOFRenderer(`,
      `    t,`,
      `    metal="${metal.trim()}",`,
      `    linker_smiles="${safeLinker}",`,
      `    cx=0, cy=0, scale=1.0,`,
      `    metal_charge=${charge},`,
      `    guest_ion=${guestArg},`,
      `)`,
      `renderer.${drawMethod}()`,
      "",
      "screen.update()",
    ].join("\n");
  };

  const handleDraw = () => {
    if (!metal.trim() || !linker.trim()) return;
    onGenerateCode(buildPythonCode());
  };

  return (
    <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: 14 }}>
      <h3 style={{ margin: "0 0 4px 0" }}>MOF Pore Explorer</h3>

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <span style={{ fontSize: 12, color: "#888", fontWeight: 500 }}>
          Metal symbol
        </span>
        <Select
          showSearch
          value={metal}
          onChange={setMetal}
          style={{ width: "100%" }}
          options={COMMON_METALS.map((m) => ({ value: m, label: m }))}
          placeholder="e.g. Zn"
        />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <span style={{ fontSize: 12, color: "#888", fontWeight: 500 }}>
          Metal charge
        </span>
        <InputNumber
          value={charge}
          onChange={(v) => setCharge(v ?? 2)}
          min={1}
          max={7}
          style={{ width: "100%" }}
        />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <span style={{ fontSize: 12, color: "#888", fontWeight: 500 }}>
          Linker SMILES{" "}
          <Tooltip title="Linkers should carry a carboxylate group ([O-]C(=O)...) at each end so the oxygens can coordinate to the metal corners, as in real MOFs.">
            <QuestionCircleOutlined style={{ color: "#bbb" }} />
          </Tooltip>
        </span>
        <Input.TextArea
          rows={2}
          value={linker}
          onChange={(e) => setLinker(e.target.value)}
          style={{ resize: "none", fontFamily: "monospace", fontSize: 13 }}
          placeholder="[O-]C(=O)c1ccc(cc1)C(=O)[O-]"
        />
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {Object.entries(EXAMPLE_LINKERS).map(([label, smiles]) => (
            <Button key={label} size="small" onClick={() => setLinker(smiles)}>
              {label}
            </Button>
          ))}
        </div>
      </div>

      <div
        style={{
          borderTop: "1px solid #eee",
          paddingTop: 12,
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 12, fontWeight: 500, color: "#555" }}>
            Show guest ion
          </span>
          <Switch checked={showGuest} onChange={setShowGuest} size="small" />
        </div>

        {showGuest && (
          <Select
            showSearch
            value={guestIon}
            onChange={setGuestIon}
            style={{ width: "100%" }}
            options={GUEST_IONS.map((ion) => ({ value: ion, label: ion }))}
            placeholder="Select a guest ion"
          />
        )}
        <span style={{ fontSize: 11, color: "#bbb", lineHeight: 1.4 }}>
          The hydration shell radius is compared against the MOF's real pore
          limiting diameter (from MOF_data.csv) to determine fit.
        </span>
      </div>

      <div
        style={{
          borderTop: "1px solid #eee",
          paddingTop: 12,
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <span style={{ fontSize: 12, fontWeight: 500, color: "#555" }}>
          Simple line view
        </span>
        <Switch checked={simpleMode} onChange={setSimpleMode} size="small" />
        <span style={{ fontSize: 11, color: "#bbb" }}>
          {simpleMode
            ? "Plain lines for linkers (faster, cleaner)"
            : "Full ball-and-stick linker structures"}
        </span>
      </div>

      <Button
        type="primary"
        onClick={handleDraw}
        disabled={!metal.trim() || !linker.trim()}
        style={{ alignSelf: "flex-start" }}
      >
        Generate MOF
      </Button>
    </div>
  );
};

export default MOFInput;
