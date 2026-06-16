// Import needed modules
import { useState } from "react";
import axios from "axios";
import LLMEntryBox from "./LLMEntryBox.js";
import LLMResponseBox from "./LLMResponseBox.js";
import { Row, Col } from "antd";
import { BACKEND_URL } from "../config.js";
import SmilesInput from "./SMILESInput.js";
import MoleculeViewer from "./MoleculeViewer.js";

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

// Define Chem app
const ChemApp = () => {
  const [userQuery, updateQuery] = useState<string>("");
  const [response, setResponse] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [submittedSmiles, setSubmittedSmiles] = useState<string[]>([]);

  // ─── Shared pre-flight setup ───────────────────────────────────────────────
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

  // ─── Button 1: plain submit – no CSV ──────────────────────────────────────
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

  // ─── Button 2: prime Gemini with CSV only ─────────────────────────────────
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

  // ─── Button 3: submit query WITH CSV prepended every time ─────────────────
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

  // Column style shared between both rows
  const colStyle = (extra?: React.CSSProperties): React.CSSProperties => ({
    border: "1px solid #ddd",
    borderRadius: 6,
    padding: 16,
    boxSizing: "border-box",
    ...extra,
  });

  return (
    <>
      {/*
        Mobile stacking order (xs/sm): LLMEntry → LLMResponse → SMILESInput → MoleculeViewer
        Each Col is full-width on mobile (xs=24), half-width on md+ (md=12).
        Both Rows share wrap so they reflow naturally.
      */}

      {/* ── Row 1: LLM Entry | LLM Response ── */}
      <Row gutter={[16, 16]} justify="center" wrap style={{ marginBottom: 16 }}>
        <Col xs={24} md={12} style={colStyle({ minHeight: 350, display: "flex", flexDirection: "column" })}>
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

      {/* ── Row 2: SMILES Input | Molecule Viewer ── */}
      <Row gutter={[16, 16]} justify="center" wrap>
        <Col xs={24} md={12} style={colStyle({ minHeight: 350, display: "flex", flexDirection: "column" })}>
          <SmilesInput onSubmitSmiles={setSubmittedSmiles} />
        </Col>
        <Col
          xs={24}
          md={12}
          style={colStyle({
            // Let the viewer grow to fit all molecule panels —
            // no maxHeight so tall molecules are never clipped.
            overflowY: "auto",
          })}
        >
          <MoleculeViewer smiles={submittedSmiles} />
        </Col>
      </Row>
    </>
  );
};

// Export component for use
export default ChemApp;