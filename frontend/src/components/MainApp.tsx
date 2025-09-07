// Import needed modules
import { useState, useEffect } from "react";
import axios from "axios";
import LLMEntryBox from "./LLMEntryBox.js";
import LLMResponseBox from "./LLMResponseBox.js";
import PythonEditor from "./PythonEditor.js";
import SkulptDisplay from "./SkulptDisplay.js";
import { Row, Col} from "antd";
import { BACKEND_URL } from "../config.js";

// Create interfaces for type safety
interface Puzzle {
  id: number;
  title: string;
  image_url: string;
  code: string;
}

// Define main app
const MainApp = () => {
  // Define constants for reference
  const [userQuery, updateQuery] = useState<string>("");
  const [writtenCode, updateCode] = useState<string>(
    `# Type your code here! Like this:\nprint("You can do this!")\n`
  );
  const [response, setResponse] = useState<string>("");
  const [error, setError] = useState<string>(""); 
  const [loading, setLoading] = useState<boolean>(false);
  const [puzzles, setPuzzles] = useState<Puzzle[]>([]);
  const [selectedPuzzle, setSelectedPuzzle] = useState<Puzzle | null>(null);

  // Create a hook to load needed content as the main app loads
  useEffect(() => {
    // Fetch the puzzle data from the backend server
    axios
      .get({BACKEND_URL} + "/api/puzzles/")
      .then((res) => {
        setPuzzles(res.data);
      })
      .catch((err) => {
        console.error("Failed to load puzzles:", err);
      });
  }, []);

  // Define behavior for form submission
  const onSubmit = async () => {
    // If there is no data in the query box, return nothing and end the process
    if (!userQuery.trim()) return;
    // Set variable defaults if there is a query
    setLoading(true);
    setResponse("");
    setError(""); 
    // Attempt to pass the query and API key to the backend for processing if submitted - wait for a response
      try {
        const res = await axios.post(
          {BACKEND_URL} + "/api/ask/",
          {
            prompt: userQuery.trim(),
          },
          {
            withCredentials: true 
          }
        );
        setResponse(res.data.response);
    }
    //If an error occurs, provide it to the user
    catch (err: any) {
      const backendError = err?.response?.data?.error || "Unexpected error occurred.";
      setError(backendError);        
      setResponse(backendError);     
    } 
    // If there is no response yet, 
    finally {
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
            onSaveCode={(code) => updateCode(code)}
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
          <PythonEditor code={writtenCode} onChange={updateCode} />
          {selectedPuzzle && (
            <img
              src={selectedPuzzle.image_url}
              alt={selectedPuzzle.title}
              style={{ maxWidth: "100%", marginTop: 12, borderRadius: 6 }}
            />
          )}
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
          <SkulptDisplay code={writtenCode} onCodeChange={updateCode} />
        </Col>
      </Row>
    </>
  );
};

// Export component for use
export default MainApp;
