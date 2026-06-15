// Import needed modules
import { useState } from "react";
import axios from "axios";
import LLMEntryBox from "./LLMEntryBox.js";
import LLMResponseBox from "./LLMResponseBox.js";
import { Row, Col } from "antd";
import { BACKEND_URL } from "../config.js";
 
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
 
    // Special handling when the CSV file is missing on the server
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
 
  // ─── Button 2: prime Gemini with CSV only (no user query needed) ───────────
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
 
  // Return HTML code for rendering
  return (
    <>
      {/* LLM input/output */}
      <Row gutter={[24, 24]} justify="center" wrap style={{ marginBottom: 32 }}>
        <Col
          xs={24}
          sm={24}
          md={12}
          lg={12}
          xl={12}
          style={{
            border: "1px solid #ddd",
            padding: 16,
            borderRadius: 6,
            boxSizing: "border-box",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            minHeight: 350,
          }}
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
        <Col
          xs={24}
          sm={24}
          md={12}
          lg={12}
          xl={12}
          style={{
            border: "1px solid #ddd",
            padding: 16,
            borderRadius: 6,
            boxSizing: "border-box",
            minHeight: 350,
            overflowY: "auto",
          }}
        >
          <LLMResponseBox
            response={response}
            loading={loading}
            error={error}
            onSaveCode={(code: string) => {""}}
          />
        </Col>
      </Row>
      {/* Editor, puzzle image, and Skulpt display */}
      <Row gutter={[24, 24]} justify="center" wrap>
        <Col
          xs={24}
          sm={24}
          md={12}
          lg={12}
          xl={12}
          style={{
            border: "1px solid #ddd",
            borderRadius: 6,
            padding: 12,
            boxSizing: "border-box",
            minHeight: 350,
            display: "flex",
            flexDirection: "column",
          }}
        >
          **INSERT RDKIT INPUT HERE**
        </Col>
        <Col
          xs={24}
          sm={24}
          md={12}
          lg={12}
          xl={12}
          style={{
            border: "1px solid #ddd",
            borderRadius: 6,
            padding: 12,
            boxSizing: "border-box",
            minHeight: 350,
          }}
        >
          **INSERT RDKIT.JS**
        </Col>
      </Row>
    </>
  );
};
 
// Export component for use
export default ChemApp;
 