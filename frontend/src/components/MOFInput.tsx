import React, { useState, useEffect } from "react";
import { Select, Button, Switch, Alert, Radio, Form } from "antd";
import axios from "axios";
import { BACKEND_URL } from "../config.js";
import type { PoreReadout } from "./MofReadoutPanel.js";

interface MetaOption {
  value: string;
  label: string;
}

interface MOFInputProps {
  onCodeReady: (code: string) => void;
  onReadout?: (readout: PoreReadout | null) => void;
  setShowSkulpt: (show: boolean) => void;
  onLinkerSelect?: (smiles: string) => void;
}

interface MofResult {
  identifier: string;
  mof_id: string;
  metals: string;
  lcd: number;
  pld: number;
}

export const MOFInput: React.FC<MOFInputProps> = ({ onCodeReady, onReadout, setShowSkulpt, onLinkerSelect }) => {
  const [guestIons, setGuestIons] = useState<string[]>([]);
  const [allMetals, setAllMetals] = useState<MetaOption[]>([]);
  const [allLinkers, setAllLinkers] = useState<MetaOption[]>([]);

  const [searchMode, setSearchMode] = useState<"metalFirst" | "linkerFirst">("metalFirst");
  const [selectedMetal, setSelectedMetal] = useState<string | undefined>(undefined);
  const [selectedLinker, setSelectedLinker] = useState<string | undefined>(undefined);
  const [guestIon, setGuestIon] = useState<string>("Li+");

  const [showGuest, setShowGuest] = useState<boolean>(true);
  const [simpleMode, setSimpleMode] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [filteredLinkers, setFilteredLinkers] = useState<MetaOption[]>([]);
  const [filteredMetals, setFilteredMetals] = useState<MetaOption[]>([]);

  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/mof-meta/`)
      .then((res) => {
        setGuestIons(res.data.guest_ions || []);
        setAllMetals(res.data.metals || []);
        setFilteredMetals(res.data.metals || []);

        const smilesOnlyLinkers = (res.data.linkers || []).map((l: MetaOption) => ({
          value: l.value,
          label: l.value
        }));

        setAllLinkers(smilesOnlyLinkers);
        setFilteredLinkers(smilesOnlyLinkers);
      })
      .catch(() => setError("Failed to fetch initial MOF database elements."));
  }, []);

  useEffect(() => {
  if (!selectedMetal && !selectedLinker) return;

  const params = searchMode === "metalFirst" 
    ? { metal: selectedMetal } 
    : { linker: selectedLinker };

  axios.get(`${BACKEND_URL}/api/mof-filter/`, { params })
    .then((res) => {
      const results = res.data.results; // [{type: "linker"|"metal", value: "..."}]

      if (searchMode === "metalFirst" && selectedMetal) {
        // Filter options based on returned valid linkers
        const validLinkerValues = results.map((r: any) => r.value);
        setFilteredLinkers(allLinkers.filter(l => validLinkerValues.includes(l.value)));

        // Reset if current selection is invalid
        if (selectedLinker && !validLinkerValues.includes(selectedLinker)) {
          setSelectedLinker(undefined);
          if (onLinkerSelect) onLinkerSelect("");
        }
      } 
      else if (searchMode === "linkerFirst" && selectedLinker) {
        // Filter options based on returned valid metals
        const validMetalValues = results.map((r: any) => r.value);
        setFilteredMetals(allMetals.filter(m => validMetalValues.includes(m.value)));

        // Reset if current selection is invalid
        if (selectedMetal && !validMetalValues.includes(selectedMetal)) {
          setSelectedMetal(undefined);
        }
      }
    })
    .catch(err => console.error("Filter API Error:", err));

}, [selectedMetal, selectedLinker, searchMode, allMetals, allLinkers]);

  const handleReset = () => {
    setSelectedMetal(undefined);
    setSelectedLinker(undefined);
    setFilteredLinkers(allLinkers);
    setFilteredMetals(allMetals);
    setShowSkulpt(false);
    if (onLinkerSelect) onLinkerSelect("");
  };

  const handleGenerate = async () => {
    if (!selectedMetal || !selectedLinker) return;
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${BACKEND_URL}/api/mof-generate/`, {
        metal: selectedMetal,
        linker: selectedLinker,
        guest_ion: showGuest ? guestIon : null,
        simple_mode: simpleMode,
      });

      if (response.data.code) {
        onCodeReady(response.data.code);
        setShowSkulpt(true);
      } else {
        setError("Execution bundle missing code tracks.");
      }

      if (onReadout) {
        onReadout(response.data.readout || null);
      }
    } catch (err: any) {
      setError(err.response?.data?.error || "Error compiling core structural generation files.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h3>MOF Configurator</h3>
      {error && <Alert message={error} type="error" showIcon closable onClose={() => setError(null)} />}

      <Form layout="vertical">
        <Form.Item label="Search Priority Type">
          <Radio.Group value={searchMode} onChange={(e) => { setSearchMode(e.target.value); handleReset(); }}>
            <Radio.Button value="metalFirst">Filter by Metal first</Radio.Button>
            <Radio.Button value="linkerFirst">Filter by Linker first</Radio.Button>
          </Radio.Group>
        </Form.Item>

        <Form.Item label="Metal Core Selection">
          <Select
            showSearch
            placeholder="Select a metal"
            value={selectedMetal}
            onChange={setSelectedMetal}
            options={searchMode === "metalFirst" ? allMetals : filteredMetals}
            disabled={searchMode === "linkerFirst" && !selectedLinker}
            filterOption={(input, option) =>
              (option?.value ?? "").toLowerCase().includes(input.toLowerCase())
            }
            notFoundContent="Not found in database"
          />
        </Form.Item>

        <Form.Item label="Organic Structural Linker (SMILES Only)">
          {/* ── CHANGED BLOCK ── */}
          <Select
            showSearch
            placeholder="Paste or search a linker SMILES"
            value={selectedLinker}
            onChange={(value) => {
              setSelectedLinker(value);
              if (onLinkerSelect) onLinkerSelect(value);
            }}
            options={searchMode === "linkerFirst" ? allLinkers : filteredLinkers}
            disabled={searchMode === "metalFirst" && !selectedMetal}
            filterOption={(input, option) =>
              (option?.value ?? "").toLowerCase().includes(input.toLowerCase())
            }
            notFoundContent="Not found in database"
          />
        </Form.Item>
        <div style={{ margin: "8px 0 16px 0", borderTop: "1px solid #eee", paddingTop: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 500 }}>Simulate Guest Ion</span>
            <Switch checked={showGuest} onChange={setShowGuest} size="small" />
          </div>
            {showGuest && (
              <Select
                showSearch
                placeholder="Select a guest ion"
                value={guestIon}
                onChange={setGuestIon}
                options={guestIons.map((ion) => ({ value: ion, label: ion }))}
                filterOption={(input, option) =>
                  (option?.value ?? "").toLowerCase().includes(input.toLowerCase())
                }
                notFoundContent="Not found in database"
              />
            )}
        </div>

        <div style={{ borderTop: "1px solid #eee", paddingTop: 12, display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <span style={{ fontSize: 12, fontWeight: 500 }}>Simple path rendering</span>
          <Switch checked={simpleMode} onChange={setSimpleMode} size="small" />
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <Button type="primary" onClick={handleGenerate} loading={loading} disabled={!selectedMetal || !selectedLinker}>
            Compute Structure
          </Button>
          <Button onClick={handleReset}>Reset</Button>
        </div>
      </Form>
    </div>
  );
};

export default MOFInput;