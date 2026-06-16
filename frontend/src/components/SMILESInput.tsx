import React, { useState } from "react";
import { Input, Button, Space } from "antd";

interface SmilesInputProps {
  onSubmitSmiles: (smiles: string) => void;
}

const SmilesInput: React.FC<SmilesInputProps> = ({
  onSubmitSmiles,
}) => {
  const [smiles, setSmiles] = useState<string>("");

  const handleSubmit = (): void => {
    const trimmedSmiles = smiles.trim();

    if (!trimmedSmiles) {
      return;
    }

    onSubmitSmiles(trimmedSmiles);
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Input.TextArea
        rows={4}
        value={smiles}
        placeholder="Enter SMILES string (e.g. CCO)"
        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
          setSmiles(e.target.value)
        }
      />

      <Button type="primary" onClick={handleSubmit}>
        Render Molecule
      </Button>
    </Space>
  );
};

export default SmilesInput;