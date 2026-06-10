// Import needed modules
import React from "react";
import processResponse from "../utils/responseProcessor.js";
import { Button } from "antd";
import axios from "axios";
import { BACKEND_URL } from '../config.js';

// Create an interface for type safety
interface LLMResponseProps {
  response: string;
  loading: boolean;
  error?: string;
  onSaveCode: (processedCode: string) => void;
}

// Create a box to display information about the LLM response
const LLMResponseBox: React.FC<LLMResponseProps> = ({
  response,
  loading,
  error,
  onSaveCode,
}) => {
  const displayContent = () => {
    if (loading) return "Loading...";
    if (error) return <span style={{ color: "red" }}>{error}</span>;
    if (!response) return "";
    return processResponse(response);
  };

// Function to clear the stored token
const handleClearToken = async () => {
  try {
    localStorage.removeItem("gemini_token");
    localStorage.removeItem("resourceSelection");
    await axios.post(
      `${BACKEND_URL}` + "/api/clear-token/",
      {},
      { withCredentials: true }
    );
    alert("Token and session cleared.");
    window.location.reload();
  } catch (err) {
    console.error(err);
    alert("Failed to delete token.");
  }
};


  // Return HTML for rendering
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div
        style={{
          height: 280,
          overflowY: "auto",
          whiteSpace: "pre-wrap",
          backgroundColor: "#1e1e1e",
          color: "#d4d4d4",
          fontFamily: "monospace",
          fontSize: 14,
          padding: 10,
          borderRadius: 4,
          border: "1px solid #ccc",
        }}
      >
        {/* Populate the response box with the response from the LLM */}
        {displayContent()}
      </div>
      {/* If there is a response, display the save to editor button */}
      {response && !loading && !error && (
        <div
          style={{
            marginTop: 12,
            display: "flex",
            justifyContent: "center",
            gap: "12px",
          }}
        >
        </div>
      )}
       {/* Create a button to transfer the code to the editor */}
        {localStorage.getItem("resourceSelection") === "ai" && (
          <Button onClick={() => onSaveCode(processResponse(response))}>
          Save to Editor
        </Button>
        )
      }
        {/* Add a button to clear the token */}
        <Button danger onClick={handleClearToken}>
          Clear Token
        </Button>
    </div>
  );
};

// Export component for use
export default LLMResponseBox;
