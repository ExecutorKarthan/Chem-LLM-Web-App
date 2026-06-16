import React, { useState } from "react";
import { Input, Button } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";

interface SmilesInputProps {
  onSubmitSmiles: (smilesList: string[]) => void;
}

const MAX_MOLECULES = 4;

const SmilesInput: React.FC<SmilesInputProps> = ({ onSubmitSmiles }) => {
  const [rows, setRows] = useState<string[]>([""]);

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
      onSubmitSmiles(filled);
    }
  };

  return (
    <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: 12 }}>
      <h3 style={{ margin: "0 0 4px 0" }}>SMILES Input</h3>

      {rows.map((value, index) => (
        <div key={index} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {/* Label */}
          <span style={{ fontSize: 12, color: "#888", fontWeight: 500 }}>
            Molecule {index + 1}
          </span>

          {/* Textarea */}
          <Input.TextArea
            rows={3}
            value={value}
            placeholder={`Enter SMILES string (e.g. CCO)`}
            onChange={(e) => handleChange(index, e.target.value)}
            style={{ resize: "none", fontFamily: "monospace", fontSize: 13 }}
          />

          {/* Row controls */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {/* Add — only on last row and when under the limit */}
            {index === rows.length - 1 && rows.length < MAX_MOLECULES && (
              <Button
                icon={<PlusOutlined />}
                onClick={handleAdd}
                size="small"
              >
                Add molecule
              </Button>
            )}

            {/* Remove — only when more than one row exists */}
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

      {/* Single render button for all molecules */}
      <Button
        type="primary"
        onClick={handleRender}
        disabled={rows.every((r) => !r.trim())}
        style={{ alignSelf: "flex-start", marginTop: 4 }}
      >
        Render {rows.filter((r) => r.trim()).length > 1 ? "all molecules" : "molecule"}
      </Button>
    </div>
  );
};

export default SmilesInput;