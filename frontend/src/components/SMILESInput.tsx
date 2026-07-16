import React, { useState } from "react";
import { Input, Button } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";

interface SmilesInputProps {
  onSubmitSmiles: (smilesList: string[], substructure: string, displayName: string) => void;
}

const MAX_MOLECULES = 4;

const SmilesInput: React.FC<SmilesInputProps> = ({ onSubmitSmiles }) => {
  const [rows, setRows] = useState<string[]>([""]);
  const [substructure, setSubstructure] = useState<string>("");
  const [displayName, setDisplayName] = useState<string>("");

  const handleChange = (index: number, value: string) => {
    setRows((prev) => prev.map((r, i) => (i === index ? value : r)));
  };  

  const handleAdd = () => {
    if (rows.length < MAX_MOLECULES) {
      setRows((prev) => [...prev, ""]);
    }
  };

  const handleRemove = (index: number) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleRender = () => {
    const filled = rows.map((r) => r.trim()).filter(Boolean);
    if (filled.length > 0) {
      onSubmitSmiles(filled, substructure.trim(), displayName);
    }
  };

  const filledCount = rows.filter((r) => r.trim()).length;

  return (
    <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: 12 }}>
      <h3 style={{ margin: "0 0 4px 0" }}>SMILES Input</h3>

      {/* ── Molecule rows ── */}
      {rows.map((value, index) => (
        <div key={index} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={{ fontSize: 12, color: "#888", fontWeight: 500 }}>
            Molecule {index + 1}
          </span>

          <Input.TextArea
            rows={3}
            value={value}
            placeholder="Enter SMILES string (e.g. CCO)"
            onChange={(e) => handleChange(index, e.target.value)}
            style={{ resize: "none", fontFamily: "monospace", fontSize: 13 }}
          />

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {index === rows.length - 1 && rows.length < MAX_MOLECULES && (
              <Button icon={<PlusOutlined />} onClick={handleAdd} size="small">
                Add molecule
              </Button>
            )}
            {rows.length > 1 && (
              <Button
                icon={<DeleteOutlined />}
                onClick={() => handleRemove(index)}
                size="small"
                danger
              >
                Remove
              </Button>
            )}
          </div>
        </div>
      ))}

      {/* ── Substructure search — always visible ── */}
      <div
        style={{
          borderTop: "1px solid #eee",
          paddingTop: 12,
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        <span style={{ fontSize: 12, fontWeight: 500, color: "#555" }}>
          Substructure search{" "}
          <span style={{ fontWeight: 400, color: "#aaa" }}>(optional — SMILES or SMARTS)</span>
        </span>
        <Input.TextArea
          rows={2}
          value={substructure}
          placeholder="e.g. c1ccccc1  or  [#6](=O)[#8]"
          onChange={(e) => setSubstructure(e.target.value)}
          style={{ resize: "none", fontFamily: "monospace", fontSize: 13 }}
        />
        <span style={{ fontSize: 11, color: "#bbb", lineHeight: 1.4 }}>
          Matching atoms and bonds will be highlighted in each molecule above.
        </span>
      </div>

      <Button
        type="primary"
        onClick={handleRender}
        disabled={filledCount === 0}
        style={{ alignSelf: "flex-start" }}
      >
        Render {filledCount > 1 ? "all molecules" : "molecule"}
      </Button>
    </div>
  );
};

export default SmilesInput;