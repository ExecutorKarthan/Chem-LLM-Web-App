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
      {error && <Alert message={error} type="error" showIcon closable onClose={() => setError(null)} />}
      <Form layout="vertical">
        <Form.Item label="Search Priority Type">
          <Radio.Group value={searchMode} onChange={(e) => { setSearchMode(e.target.value); handleReset(); }}>
            <Radio.Button value="metalFirst">Filter by Metal first</Radio.Button>
            <Radio.Button value="linkerFirst">Filter by Linker first</Radio.Button>
          </Radio.Group>
        </Form.Item>

        {searchMode === "metalFirst" ? (
          <>
            <Form.Item label="Metal Core Selection">
              <Select showSearch value={selectedMetal} onChange={(v) => { setSelectedMetal(v); setSelectedLinker(undefined); onLinkerNameUpdate(""); }} options={allMetals} />
            </Form.Item>
            <Form.Item label="Organic Structural Linker">
              <Select showSearch value={selectedLinker} disabled={!selectedMetal} options={filteredLinkers} onChange={(v) => { setSelectedLinker(v); if (onLinkerSelect) onLinkerSelect(v); axios.get(`${BACKEND_URL}/api/mof-filter/`, { params: { metal: selectedMetal, linker: v } }).then(res => onLinkerNameUpdate(res.data.common_name || "")); }} />
            </Form.Item>
          </>
        ) : (
          <>
            <Form.Item label="Organic Structural Linker">
              <Select showSearch value={selectedLinker} options={allLinkers} onChange={(v) => { setSelectedLinker(v); setSelectedMetal(undefined); if (onLinkerSelect) onLinkerSelect(v); axios.get(`${BACKEND_URL}/api/mof-filter/`, { params: { linker: v } }).then(res => onLinkerNameUpdate(res.data.common_name || "")); }} />
            </Form.Item>
            <Form.Item label="Metal Core Selection">
              <Select showSearch value={selectedMetal} disabled={!selectedLinker} options={filteredMetals} onChange={setSelectedMetal} />
            </Form.Item>
          </>
        )}

        <div style={{ margin: "8px 0 16px 0", borderTop: "1px solid #eee", paddingTop: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 500 }}>Simulate Guest Ion</span>
            <Switch checked={showGuest} onChange={setShowGuest} size="small" />
          </div>
          {showGuest && (
            <Select showSearch value={guestIon} onChange={setGuestIon} options={guestIons.map(i => ({ value: i, label: i }))} />
          )}
        </div>

        <div style={{ borderTop: "1px solid #eee", paddingTop: 12, display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <span style={{ fontSize: 12, fontWeight: 500 }}>Simple path rendering</span>
          <Switch checked={simpleMode} onChange={setSimpleMode} size="small" />
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <Button type="primary" onClick={handleGenerate} loading={loading} disabled={!selectedMetal || !selectedLinker}>Compute Structure</Button>
          <Button onClick={handleReset}>Reset</Button>
        </div>
      </Form>
    </div>
  );
};

export default MOFInput;