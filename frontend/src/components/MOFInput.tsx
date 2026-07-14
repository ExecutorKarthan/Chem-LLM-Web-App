import React, { useState, useEffect } from "react";
import { Select, Button, Switch, Alert, Radio, Form } from "antd";
import axios from "axios";
import { BACKEND_URL } from "../config.js";

export interface ReadoutLine {
  text: string;
  color: string;
}

interface MetaOption {
  value: string;
  label: string;
}

interface MOFInputProps {
  onCodeReady: (code: string) => void;
  onReadout?: (lines: ReadoutLine[]) => void;
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

  // 1. Initial Load: Filter labels to show pure SMILES only
  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/mof-meta/`)
      .then((res) => {
        setGuestIons(res.data.guest_ions || []);
        setAllMetals(res.data.metals || []);
        setFilteredMetals(res.data.metals || []);

        // FORCE display labels to be the pure SMILES formula string
        const smilesOnlyLinkers = (res.data.linkers || []).map((l: MetaOption) => ({
          value: l.value,
          label: l.value 
        }));

        setAllLinkers(smilesOnlyLinkers);
        setFilteredLinkers(smilesOnlyLinkers);
      })
      .catch(() => setError("Failed to fetch initial MOF database elements."));
  }, []);

  // 2. Cross-Filtering Trigger Core
  useEffect(() => {
    if (searchMode === "metalFirst" && selectedMetal) {
      axios.get(`${BACKEND_URL}/api/mof-filter/`, { params: { metal: selectedMetal } })
        .then((res) => {
          const validLinkers = res.data.results.map((r: MofResult) => r.identifier || r.mof_id);
          const matched = allLinkers.filter(l => validLinkers.includes(l.value));
          setFilteredLinkers(matched);
          
          if (selectedLinker && !validLinkers.includes(selectedLinker)) {
            setSelectedLinker(undefined);
            if (onLinkerSelect) onLinkerSelect("");
          }
        });
    } 
    else if (searchMode === "linkerFirst" && selectedLinker) {
      axios.get(`${BACKEND_URL}/api/mof-filter/`, { params: { linker: selectedLinker } })
        .then((res) => {
          const validMetals = new Set<string>();
          res.data.results.forEach((r: MofResult) => {
            if (r.metals) {
              r.metals.split(/[\.,\-_]/).forEach(m => validMetals.add(m.trim()));
            }
          });
          const matched = allMetals.filter(m => validMetals.has(m.value));
          setFilteredMetals(matched);
          
          if (selectedMetal && !validMetals.has(selectedMetal)) {
            setSelectedMetal(undefined);
          }
        });
    }
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
        linker: selectedLinker, // Changed key name from 'mof_id' to 'linker'
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
        onReadout(response.data.readout || []);
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
            optionFilterProp="label"
          />
        </Form.Item>

        <Form.Item label="Organic Structural Linker (SMILES Only)">
          <Select
            showSearch
            placeholder="Select a linker SMILES"
            value={selectedLinker}
            onChange={(value) => {
              setSelectedLinker(value);
              if (onLinkerSelect) onLinkerSelect(value); 
            }}
            options={searchMode === "linkerFirst" ? allLinkers : filteredLinkers}
            disabled={searchMode === "metalFirst" && !selectedMetal}
            optionFilterProp="label"
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
              value={guestIon}
              onChange={setGuestIon}
              options={guestIons.map((ion) => ({ value: ion, label: ion }))}
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