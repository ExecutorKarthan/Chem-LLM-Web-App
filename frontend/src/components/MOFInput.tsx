// MOFInput.tsx
import React, { useState, useEffect } from "react";
import { Select, Button, Switch, Alert, Radio, Form } from "antd";
import axios from "axios";
import { BACKEND_URL } from "../config.js";

export interface ReadoutLine {
  text: string;
  color: string;
}

interface MOFInputProps {
  onCodeReady: (code: string) => void;
  // Pore-fit readout for the current selection, computed server-side in
  // generate_mof_code — feeds MofReadoutPanel.tsx. Optional so existing
  // callers that only care about the Skulpt code keep working unchanged.
  onReadout?: (lines: ReadoutLine[]) => void;
}

interface MofResult {
  identifier: string,
  mof_id: string;
  metal: string;
  lcd: number;
  pld: number;
}

export const MOFInput: React.FC<MOFInputProps> = ({ onCodeReady, onReadout }) => {
  // Metadata options from server
  const [guestIons, setGuestIons] = useState<string[]>([]);
  const [allMetals, setAllMetals] = useState<string[]>([]);
  const [allLinkers, setAllLinkers] = useState<string[]>([]);
  
  // Selection states
  const [searchMode, setSearchMode] = useState<"metalFirst" | "linkerFirst">("metalFirst");
  const [selectedMetal, setSelectedMetal] = useState<string | undefined>(undefined);
  const [selectedLinker, setSelectedLinker] = useState<string | undefined>(undefined);
  const [guestIon, setGuestIon] = useState<string>("Li+");
  
  // Toggles
  const [showGuest, setShowGuest] = useState<boolean>(true);
  const [simpleMode, setSimpleMode] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filtered dropdown possibilities
  const [filteredLinkers, setFilteredLinkers] = useState<string[]>([]);
  const [filteredMetals, setFilteredMetals] = useState<string[]>([]);

  // 1. Bootstrapping initial lists
  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/mof-meta/`)
      .then((res) => {
        setGuestIons(res.data.guest_ions || []);
        setAllMetals(res.data.metals || []);
        setAllLinkers(res.data.linkers || []);
        setFilteredLinkers(res.data.linkers || []);
        setFilteredMetals(res.data.metals || []);
      })
      .catch((err) => {
        setError("Failed to fetch MOF asset catalog from server.");
      });
  }, []);

  // 2. Fetch cascading options when selection changes
  useEffect(() => {
    if (searchMode === "metalFirst" && selectedMetal) {
      axios.post(`${BACKEND_URL}/api/mof-filter/`, { metal: selectedMetal })
        .then((res) => {
          const validLinkers = res.data.results.map((r: MofResult) => r.identifier || r.mof_id);
          setFilteredLinkers(validLinkers);
          // Auto-clear or adjust second field if current choice is invalid
          if (selectedLinker && !validLinkers.includes(selectedLinker)) {
            setSelectedLinker(undefined);
          }
        });
    } else if (searchMode === "linkerFirst" && selectedLinker) {
      axios.post(`${BACKEND_URL}/api/mof-filter/`, { linker: selectedLinker })
        .then((res) => {
          // Collect structural metals from results
          const validMetals = new Set<string>();
          res.data.results.forEach((r: MofResult) => {
            r.metal.split(",").forEach(m => validMetals.add(m.trim()));
          });
          const metalArray = Array.from(validMetals);
          setFilteredMetals(metalArray);
          if (selectedMetal && !metalArray.includes(selectedMetal)) {
            setSelectedMetal(undefined);
          }
        });
    }
  }, [selectedMetal, selectedLinker, searchMode]);

  const handleReset = () => {
    setSelectedMetal(undefined);
    setSelectedLinker(undefined);
    setFilteredLinkers(allLinkers);
    setFilteredMetals(allMetals);
  };

  const handleGenerate = async () => {
      if (!selectedMetal || !selectedLinker) return;
      setLoading(true);
      // Use undefined here to match the component's state type declaration
      setError(undefined); 

      try {
        const response = await axios.post(`${BACKEND_URL}/api/mof-generate/`, {
          metal: selectedMetal,
          mof_id: selectedLinker, // The full identifier string from column 1
          guest_ion: showGuest ? guestIon : null,
          simple_mode: simpleMode,
        });
        
        if (response.data.code) {
          onCodeReady(response.data.code);
        } else {
          setError("Server response did not include execution code.");
        }
        
        if (onReadout) {
          onReadout(response.data.readout || []);
        }
      } catch (err: any) {
        console.error("Visualization error:", err);
        setError(err.response?.data?.error || "Error executing visualization engine script.");
      } finally {
        setLoading(false);
      }
    };

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16, maxWidth: 400 }}>
      <h3>MOF Configuration Engine</h3>
      {error && <Alert message={error} type="error" showIcon closable />}

      <Form layout="vertical">
        {/* Toggle Filtering Strategy */}
        <Form.Item label="Search Workflow Constraints">
          <Radio.Group 
            value={searchMode} 
            onChange={(e) => {
              setSearchMode(e.target.value);
              handleReset();
            }}
          >
            <Radio.Button value="metalFirst">Filter by Metal first</Radio.Button>
            <Radio.Button value="linkerFirst">Filter by Linker first</Radio.Button>
          </Radio.Group>
        </Form.Item>

        {/* Dropdown 1: Metal Node Selection */}
        <Form.Item label="Metal Secondary Building Unit (SBU)">
          <Select
            showSearch
            placeholder="Select coordinated center element"
            value={selectedMetal}
            onChange={setSelectedMetal}
            options={(searchMode === "metalFirst" ? allMetals : filteredMetals).map((m) => ({ value: m, label: m }))}
            disabled={searchMode === "linkerFirst" && !selectedLinker}
          />
        </Form.Item>

        {/* Dropdown 2: Linker Molecule Selection */}
        <Form.Item label="Organic Structural Linker (SMILES)">
          <Select
            showSearch
            placeholder="Select coordinated linker scaffold"
            value={selectedLinker}
            onChange={setSelectedLinker}
            options={(searchMode === "linkerFirst" ? allLinkers : filteredLinkers).map((l) => ({ value: l, label: l }))}
            disabled={searchMode === "metalFirst" && !selectedMetal}
          />
        </Form.Item>

        {/* Guest Ion Configuration */}
        <div style={{ margin: "8px 0 16px 0", borderTop: "1px solid #eee", paddingTop: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 500 }}>Simulate Interstitial Guest Ion</span>
            <Switch checked={showGuest} onChange={setShowGuest} size="small" />
          </div>
          {showGuest && (
            <Select
              showSearch
              value={guestIon}
              onChange={setGuestIon}
              style={{ width: "100%" }}
              options={guestIons.map((ion) => ({ value: ion, label: ion }))}
              placeholder="Select structural guest ion archetype"
            />
          )}
        </div>

        {/* Presentation Rendering Option */}
        <div style={{ borderTop: "1px solid #eee", paddingTop: 12, display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <span style={{ fontSize: 12, fontWeight: 500 }}>Simple geometric path rendering</span>
          <Switch checked={simpleMode} onChange={setSimpleMode} size="small" />
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <Button
            type="primary"
            onClick={handleGenerate}
            loading={loading}
            disabled={!selectedMetal || !selectedLinker}
          >
            Compute Structure
          </Button>
          <Button onClick={handleReset}>Reset Filters</Button>
        </div>
      </Form>
    </div>
  );
};

// Export component for use
export default MOFInput;