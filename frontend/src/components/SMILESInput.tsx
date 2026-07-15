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

  const handleSubmitSmiles = async (smilesList: string[], substructure: string) => {
    setSubmittedSmiles(smilesList);
    setSubmittedSubstructure(substructure);

    // Automatically fetch name for the first molecule
    if (smilesList.length > 0) {
      try {
        // Encode SMILES for URL safety
        const encodedSmiles = encodeURIComponent(smilesList[0]);
        
        // 1. Get CID
        const cidRes = await axios.get(`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/${encodedSmiles}/cids/JSON`);
        const cid = cidRes.data.IdentifierList.CID[0];

        // 2. Get Name
        const synRes = await axios.get(`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/${cid}/synonyms/JSON`);
        const name = synRes.data.InformationList.Information[0].Synonym[0];
        
        // Update the name used by MoleculeViewer
        setLinkerCommonName(name); 
      } catch (e) {
        console.warn("Could not resolve name via PubChem, using SMILES as label.");
        setLinkerCommonName(""); // Fallback: MoleculeViewer will just show "Molecule 1"
      }
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