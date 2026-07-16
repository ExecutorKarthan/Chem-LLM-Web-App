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
  onLinkerNameUpdate: (name: string) => void;
}

export const MOFInput: React.FC<MOFInputProps> = ({ 
  onCodeReady, onReadout, setShowSkulpt, onLinkerSelect, onLinkerNameUpdate 
}) => {
  const [allMetals, setAllMetals] = useState<MetaOption[]>([]);
  const [allLinkers, setAllLinkers] = useState<MetaOption[]>([]);
  const [filteredLinkers, setFilteredLinkers] = useState<MetaOption[]>([]);
  const [filteredMetals, setFilteredMetals] = useState<MetaOption[]>([]);

  const [searchMode, setSearchMode] = useState<"metalFirst" | "linkerFirst">("metalFirst");
  const [selectedMetal, setSelectedMetal] = useState<string | undefined>(undefined);
  const [selectedLinker, setSelectedLinker] = useState<string | undefined>(undefined);
  
  const [guestIons, setGuestIons] = useState<string[]>([]);
  const [guestIon, setGuestIon] = useState<string>("Li+");
  const [showGuest, setShowGuest] = useState<boolean>(true);
  const [simpleMode, setSimpleMode] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Initial Load
  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/mof-meta/`).then((res) => {
      setGuestIons(res.data.guest_ions || []);
      setAllMetals(res.data.metals || []);
      setFilteredMetals(res.data.metals || []);
      const linkers = (res.data.linkers || []).map((l: MetaOption) => ({ value: l.value, label: l.value }));
      setAllLinkers(linkers);
      setFilteredLinkers(linkers);
    }).catch(() => setError("Failed to fetch initial database."));
  }, []);

  // Filter Logic: Triggered only by Primary Selection
  useEffect(() => {
    if (searchMode === "metalFirst") {
      if (!selectedMetal) {
        setFilteredLinkers(allLinkers);
      } else {
        axios.get(`${BACKEND_URL}/api/mof-filter/`, { params: { metal: selectedMetal } })
          .then(res => {
            const valid = res.data.results.map((r: any) => r.value);
            setFilteredLinkers(allLinkers.filter(l => valid.includes(l.value)));
          });
      }
    } else {
      if (!selectedLinker) {
        setFilteredMetals(allMetals);
      } else {
        axios.get(`${BACKEND_URL}/api/mof-filter/`, { params: { linker: selectedLinker } })
          .then(res => {
            const valid = res.data.results.map((r: any) => r.value);
            setFilteredMetals(allMetals.filter(m => valid.includes(m.value)));
          });
      }
    }
  }, [selectedMetal, selectedLinker, searchMode]);

  const handleReset = () => {
    setSelectedMetal(undefined);
    setSelectedLinker(undefined);
    setFilteredLinkers(allLinkers);
    setFilteredMetals(allMetals);
    setShowSkulpt(false);
    onLinkerNameUpdate("");
    if (onLinkerSelect) onLinkerSelect("");
  };

  const handleGenerate = async () => {
    if (!selectedMetal || !selectedLinker) return;
    setLoading(true);
    try {
      const response = await axios.post(`${BACKEND_URL}/api/mof-generate/`, {
        metal: selectedMetal, linker: selectedLinker, guest_ion: showGuest ? guestIon : null, simple_mode: simpleMode
      });
      onCodeReady(response.data.code);
      setShowSkulpt(true);
      if (onReadout) onReadout(response.data.readout || null);
    } catch { setError("Generation failed."); } finally { setLoading(false); }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h3>MOF Configurator</h3>
      <Form layout="vertical">
    <Form.Item label="Search Priority Type">
      <Radio.Group value={searchMode} onChange={(e) => { setSearchMode(e.target.value); handleReset(); }}>
        <Radio.Button value="metalFirst">Filter by Metal first</Radio.Button>
        <Radio.Button value="linkerFirst">Filter by Linker first</Radio.Button>
      </Radio.Group>
    </Form.Item>

    {/* ─── DYNAMIC LAYOUT: Priority Selectors ─── */}
    {searchMode === "metalFirst" ? (
      <>
        {/* Metal First: Metal is Primary */}
        <Form.Item label="Metal Core Selection">
          <Select
            showSearch
            placeholder="Select a metal"
            value={selectedMetal}
            onChange={(val) => {
              setSelectedMetal(val);
              setSelectedLinker(undefined); // Reset dependency
              onLinkerNameUpdate("");
            }}
            options={allMetals}
            filterOption={(input, opt) => (opt?.value ?? "").toLowerCase().includes(input.toLowerCase())}
          />
        </Form.Item>
        <Form.Item label="Organic Structural Linker">
          <Select
            showSearch
            placeholder="Search linker"
            value={selectedLinker}
            disabled={!selectedMetal} // Greys out until metal is selected
            onChange={(val) => {
              setSelectedLinker(val);
              if (onLinkerSelect) onLinkerSelect(val);
              if (val) {
                axios.get(`${BACKEND_URL}/api/mof-filter/`, { params: { metal: selectedMetal, linker: val } })
                  .then(res => onLinkerNameUpdate(res.data.common_name || ""));
              }
            }}
            options={filteredLinkers}
            filterOption={(input, opt) => (opt?.value ?? "").toLowerCase().includes(input.toLowerCase())}
          />
        </Form.Item>
      </>
    ) : (
      <>
        {/* Linker First: Linker is Primary */}
        <Form.Item label="Organic Structural Linker">
          <Select
            showSearch
            placeholder="Search linker"
            value={selectedLinker}
            onChange={(val) => {
              setSelectedLinker(val);
              setSelectedMetal(undefined); // Reset dependency
              if (onLinkerSelect) onLinkerSelect(val);
              if (val) {
                axios.get(`${BACKEND_URL}/api/mof-filter/`, { params: { linker: val } })
                  .then(res => onLinkerNameUpdate(res.data.common_name || ""));
              }
            }}
            options={allLinkers}
            filterOption={(input, opt) => (opt?.value ?? "").toLowerCase().includes(input.toLowerCase())}
          />
        </Form.Item>
        <Form.Item label="Metal Core Selection">
          <Select
            showSearch
            placeholder="Select a metal"
            value={selectedMetal}
            disabled={!selectedLinker} // Greys out until linker is selected
            onChange={setSelectedMetal}
            options={filteredMetals}
            filterOption={(input, opt) => (opt?.value ?? "").toLowerCase().includes(input.toLowerCase())}
          />
        </Form.Item>
      </>
    )}

        <Button type="primary" onClick={handleGenerate} loading={loading} disabled={!selectedMetal || !selectedLinker}>
          Compute Structure
        </Button>
        <Button onClick={handleReset}>Reset</Button>
      </Form>
    </div>
  );
};

export default MOFInput;