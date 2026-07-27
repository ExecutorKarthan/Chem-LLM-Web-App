// ChemApp.tsx
//
// Top-level page layout: an LLM entry/response row, a mode toggle, and
// a second row whose contents swap based on that toggle — "MOF
// Explorer" (MOFInput + MOF Skulpt canvas/readout) vs. "Linker Viewer"
// (SmilesInput + MoleculeViewer, for inspecting arbitrary SMILES
// without going through the MOF metal/linker pairing flow).

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
import type { PoreReadout } from "./MofReadoutPanel.js";
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

  // States for labels: one for single MOF, one for array-based SMILES
  const [linkerCommonName, setLinkerCommonName] = useState<string>("");
  const [linkerCommonNames, setLinkerCommonNames] = useState<string[]>([]);

  const beginRequest = () => {
    setLoading(true);
    setResponse("");
    setError("");
    return getCookie("csrftoken") || "";
  };

  // Surfaces a backend error to both `error` (used for the Alert banner)
  // and `response` (so it's also visible in the main response box).
  // The csv_missing case gets a specific, actionable message since it
  // means the server's MOF reference data is missing entirely — a setup
  // problem rather than a normal per-request failure.
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

  // Three ways to query Gemini, corresponding to the three backend
  // endpoints in views.py: a plain question with no MOF context
  // (onSubmit), a one-off "prime" call that hands Gemini the whole MOF
  // CSV so it acknowledges receiving it (onSubmitData, no user prompt
  // needed), and a question answered with the MOF CSV prepended every
  // time (onSubmitWithData) — useful when the user hasn't primed first
  // or wants the data freshly in-context for that specific question.
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

  // Receives the molecule list and the substructure query from SmilesInput
  const handleSubmitSmiles = async (smilesList: string[], substructure: string) => {
    setSubmittedSmiles(smilesList);
    setSubmittedSubstructure(substructure);

    // Initialize array with default labels
    const names = new Array(smilesList.length).fill("");
    setLinkerCommonNames(names);

    // Resolve common names via PubChem. This is a direct browser->PubChem
    // call (not proxied through the Django backend, unlike the MOF-side
    // name lookups in mof_registry_builder.py), and needs two round trips
    // per molecule since PubChem's API doesn't offer a single SMILES ->
    // synonym endpoint: first resolve the SMILES to a PubChem CID, then
    // look up that CID's synonyms. Each molecule's lookup runs
    // independently (not awaited in sequence) so one slow/failed lookup
    // doesn't block the others from updating their label as soon as
    // they're ready.
    smilesList.forEach(async (smiles, index) => {
      try {
        const encoded = encodeURIComponent(smiles);
        const cidRes = await axios.get(`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/${encoded}/cids/JSON`);
        const cid = cidRes.data.IdentifierList.CID[0];
        const synRes = await axios.get(`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/${cid}/synonyms/JSON`);
        const name = synRes.data.InformationList.Information[0].Synonym[0];

        setLinkerCommonNames(prev => {
          const next = [...prev];
          next[index] = name;
          return next;
        });
      } catch (e) {
        console.warn(`Could not resolve name for molecule ${index + 1}`);
      }
    });
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
            // NOTE: this handler doesn't do anything — `{""}` is just an
            // expression statement, not a save action. If "save code"
            // is meant to actually do something, this still needs
            // implementing; if it's not needed anymore, LLMResponseBox's
            // onSaveCode prop could probably be dropped instead.
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
              setMofReadout(null);
              setShowSkulptCanvas(false);
              setActiveDropdownLinker("");
              setLinkerCommonName("");
              setLinkerCommonNames([]);
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
              onLinkerSelect={(linker) => {
                setActiveDropdownLinker(linker);
                setLinkerCommonName("");
              }}
              onLinkerNameUpdate={setLinkerCommonName}
            />
          )}
        </Col>
        <Col xs={24} md={12} style={colStyle({ overflowY: "auto" })}>
          {linkerViewerMode ? (
            <MoleculeViewer
              smiles={submittedSmiles}
              substructure={submittedSubstructure}
              linkerNames={linkerCommonNames}
            />
          ) : (
            showSkulptCanvas ? (
              <div id="skulpt-canvas-container" style={{ width: "100%" }}>
                <SkulptDisplay code={mofCode} />
                <MofReadoutPanel readout={mofReadout} />
              </div>
            ) : (
              <MoleculeViewer
                smiles={activeDropdownLinker ? [activeDropdownLinker] : []}
                substructure=""
                linkerName={linkerCommonName}
              />
            )
          )}
        </Col>
      </Row>
    </>
  );
};

export default ChemApp;