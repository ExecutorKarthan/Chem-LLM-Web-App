// Import needed modules
import { useState } from "react";
import axios from "axios";
import LLMEntryBox from "./LLMEntryBox.js";
import LLMResponseBox from "./LLMResponseBox.js";
import { Row, Col, Switch } from "antd";
import { BACKEND_URL } from "../config.js";
import SmilesInput from "./SMILESInput.js";
import MoleculeViewer from "./MoleculeViewer.js";
import MOFInput from "./MOFInput.js";
import type { PoreReadout } from "./MOFInput.js";
import MofReadoutPanel from "./MofReadoutPanel.js";
import SkulptDisplay from "./SkulptDisplay.js";

// Helper function to get CSRF token from cookies
function getCookie(name: string): string | undefined {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    const part = parts.pop();
    if (part) {
      return part.split(";").shift();
    }
  }
  return undefined;
}

const ChemApp = () => {
  const [userQuery, updateQuery] = useState<string>("");
  const [response, setResponse] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [submittedSmiles, setSubmittedSmiles] = useState<string[]>([]);
  const [submittedSubstructure, setSubmittedSubstructure] = useState<string>("");
  const [linkerViewerMode, setLinkerViewerMode] = useState<boolean>(false);
  const [mofCode, setMofCode] = useState<string>("");
  const [mofReadout, setMofReadout] = useState<PoreReadout | null >(null);

  // --- CONTROL HOOK STATES ---
  const [showSkulptCanvas, setShowSkulptCanvas] = useState<boolean>(false);
  const [activeDropdownLinker, setActiveDropdownLinker] = useState<string>("");

  const beginRequest = () => {
    setLoading(true);
    setResponse("");
    setError("");
    return getCookie("csrftoken") || "";
  };

  const handleError = (err: any) => {
    console.error("Full error object:", err);
    console.error("Error response:", err?.response);

    if (err?.response?.data?.csv_missing) {
      const msg =
        "⚠️ Data submission failed: the linker data file could not be found on the " +
        "server. Please contact your administrator to ensure linker_data.csv exists " +
        "in backend/assets/.";
      setError(msg);
      setResponse(msg);
      return;
    }

    const backendError =
      err?.response?.data?.error || "Unexpected error occurred.";
    setError(backendError);
    setResponse(backendError);
  };

  const onSubmit = async () => {
    if (!userQuery.trim()) return;
    const csrfToken = beginRequest();
    try {
      const res = await axios.post(
        `${BACKEND_URL}/api/ask/`,
        { prompt: userQuery.trim() },
        { withCredentials: true, headers: { "X-CSRFToken": csrfToken } }
      );
      setResponse(res.data.response);
    } catch (err: any) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  const onSubmitData = async () => {
    const csrfToken = beginRequest();
    try {
      const res = await axios.post(
        `${BACKEND_URL}/api/prime/`,
        {},
        { withCredentials: true, headers: { "X-CSRFToken": csrfToken } }
      );
      setResponse(res.data.response);
    } catch (err: any) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  const onSubmitWithData = async () => {
    if (!userQuery.trim()) return;
    const csrfToken = beginRequest();
    try {
      const res = await axios.post(
        `${BACKEND_URL}/api/ask-with-data/`,
        { prompt: userQuery.trim() },
        { withCredentials: true, headers: { "X-CSRFToken": csrfToken } }
      );
      setResponse(res.data.response);
    } catch (err: any) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  // Receives both the molecule list and the substructure query from SmilesInput
  const handleSubmitSmiles = (smilesList: string[], substructure: string) => {
    setSubmittedSmiles(smilesList);
    setSubmittedSubstructure(substructure);
  };

  const colStyle = (extra?: React.CSSProperties): React.CSSProperties => ({
    border: "1px solid #ddd",
    borderRadius: 6,
    padding: 16,
    boxSizing: "border-box",
    ...extra,
  });

  return (
    <>
      {/* ── Row 1: LLM Entry | LLM Response ── */}
      <Row gutter={[16, 16]} justify="center" wrap style={{ marginBottom: 16 }}>
        <Col
          xs={24}
          md={12}
          style={colStyle({ minHeight: 350, display: "flex", flexDirection: "column" })}
        >
          <LLMEntryBox
            query={userQuery}
            onQueryChange={updateQuery}
            response={response}
            setResponse={setResponse}
            loading={loading}
            setLoading={setLoading}
            onSubmit={onSubmit}
            onSubmitData={onSubmitData}
            onSubmitWithData={onSubmitWithData}
          />
        </Col>
        <Col xs={24} md={12} style={colStyle({ minHeight: 350, overflowY: "auto" })}>
          <LLMResponseBox
            response={response}
            loading={loading}
            error={error}
            onSaveCode={(code: string) => {""}}
          />
        </Col>
      </Row>

      {/* ── Mode toggle ── */}
      <Row justify="center" style={{ marginBottom: 8 }}>
        <Col xs={24} style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10 }}>
          <span style={{ fontSize: 13, color: linkerViewerMode ? "#aaa" : "#333", fontWeight: 500 }}>
            MOF Explorer
          </span>
          <Switch 
            checked={linkerViewerMode} 
            onChange={(checked) => {
              setLinkerViewerMode(checked);
              setMofCode("");
              setMofReadout(null);   // ← was []
              setShowSkulptCanvas(false);
              setActiveDropdownLinker("");
            }}
          />
          <span style={{ fontSize: 13, color: linkerViewerMode ? "#333" : "#aaa", fontWeight: 500 }}>
            Linker Viewer
          </span>
        </Col>
      </Row>

      {/* ── Row 2: SMILES Input | Molecule Viewer  —or—  MOF Input | Skulpt Display ── */}
      <Row gutter={[16, 16]} justify="center" wrap>
        <Col
          xs={24}
          md={12}
          style={colStyle({ minHeight: 350, display: "flex", flexDirection: "column" })}
        >
          {linkerViewerMode ? (
            <SmilesInput onSubmitSmiles={handleSubmitSmiles} />
          ) : (
            <MOFInput 
              onCodeReady={setMofCode} 
              onReadout={setMofReadout} 
              setShowSkulpt={setShowSkulptCanvas}
              onLinkerSelect={setActiveDropdownLinker} // Pipes chosen select box option into parent layout state
            />
          )}
        </Col>
        <Col xs={24} md={12} style={colStyle({ overflowY: "auto" })}>
          {linkerViewerMode ? (
            <MoleculeViewer
              smiles={submittedSmiles}
              substructure={submittedSubstructure}
            />
          ) : (
            /* MOF Explorer View Render Decision Split */
            showSkulptCanvas ? (
              <div id="skulpt-canvas-container" style={{ width: "100%" }}>
                <SkulptDisplay code={mofCode} />
                <MofReadoutPanel readout={mofReadout} />
              </div>
            ) : (
              /* If compute hasn't run yet, load MoleculeViewer with the currently selected dropdown linker */
              <MoleculeViewer
                smiles={activeDropdownLinker ? [activeDropdownLinker] : []}
                substructure=""
              />
            )
          )}
        </Col>
      </Row>
    </>
  );
};

export default ChemApp;