// Import needed modules
import { Input } from "antd";
 
// Create an interface for type safety
interface LLMEntryProps {
  query: string;
  onQueryChange: (newQuery: string) => void;
  response: string;
  setResponse: (setResponse: string) => void;
  loading: boolean;
  setLoading: (setLoading: boolean) => void;
  onSubmit: () => void;
  // Optional: only present when rendered inside ChemApp
  onSubmitData?: () => void;
  onSubmitWithData?: () => void;
}
 
const { TextArea } = Input;
 
const LLMEntryBox: React.FC<LLMEntryProps> = ({
  query,
  onQueryChange,
  onSubmit,
  loading,
  onSubmitData,
  onSubmitWithData,
}) => {
  // True when ChemApp has wired up the extra two handlers
  const isChemApp = !!onSubmitData && !!onSubmitWithData;
 
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      {/* Query text area */}
      <TextArea
        showCount
        placeholder="Enter your query to the LLM here."
        style={{
          height: 300,
          resize: "none",
          marginBottom: 16,
          width: "100%",
          maxWidth: 800,
        }}
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
      />
 
      {/* Button row */}
      <div
        style={{
          display: "flex",
          gap: 8,
          flexWrap: "wrap",
          justifyContent: "center",
        }}
      >
        {/* Button 1 – always shown: plain submit, no CSV */}
        <button
          onClick={onSubmit}
          disabled={loading || !query.trim()}
          style={{ padding: "8px 16px", minWidth: 140 }}
          title="Send your query to Gemini with no extra context."
        >
          {loading ? "Loading..." : "Submit request"}
        </button>
 
        {/* Buttons 2 & 3 – only shown inside ChemApp */}
        {isChemApp && (
          <>
            {/* Button 2 – send CSV to Gemini as a standalone priming call */}
            <button
              onClick={onSubmitData}
              disabled={loading}
              style={{ padding: "8px 16px", minWidth: 160 }}
              title="Send the MOF dataset to Gemini so it can reference it in later answers."
            >
              {loading ? "Loading..." : "Submit data to LLM"}
            </button>
 
            {/* Button 3 – prepend CSV to every query */}
            <button
              onClick={onSubmitWithData}
              disabled={loading || !query.trim()}
              style={{ padding: "8px 16px", minWidth: 200 }}
              title="Send your query AND the full MOF dataset to Gemini together."
            >
              {loading ? "Loading..." : "Submit request with data"}
            </button>
          </>
        )}
      </div>
    </div>
  );
};
 
// Export the module for use
export default LLMEntryBox;