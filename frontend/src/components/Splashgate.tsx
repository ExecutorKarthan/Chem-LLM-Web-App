// Import needed modules
import { useState } from "react";
import axios from "axios";
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faEye, faEyeSlash } from '@fortawesome/free-solid-svg-icons';
import { BACKEND_URL } from "../config.js";
import getCSRFToken from "../utils/CSRFReader.js";

// Create an initial page that will restrict people from accessing the app
// without accepting the terms or providing an API key
//
// Flow: user checks "agree" and enters their raw Gemini API key here ->
// handleSubmit exchanges it for a token via /api/tokenize-key/ (the
// real key ends up cached server-side, referenced by an httponly
// cookie — see views.tokenize_key) -> on success, a client-side-only
// localStorage flag "splash_terms_agreed" is set purely as a "user has
// completed onboarding" marker -> the page reloads, and App.tsx checks
// that localStorage flag to decide whether to show this splash gate
// again or go straight to the app. Clearing that localStorage flag
// (see LLMResponseBox's handleClearToken) makes the splash gate
// reappear on next load.
const SplashGate: React.FC = () => {

  // Create constants and their mutators for reference
  const [agreed, setAgreed] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);

  // Generate behavior for the submission button
  const handleSubmit = async () => {
    if (!agreed) {
      setError("You must agree to the terms.");
      return;
    }
    if (!apiKey.trim()) {
      setError("API key is required.");
      return;
    }

    try {
      // Ensure we have a CSRF token before submitting.
      // BACKEND_URL is "" in production (relative URLs, Django serves everything)
      // and "http://localhost:8000" in development (Vite dev server proxies /api).
      // It is never hardcoded here — see src/config.ts.
      // NOTE: console.log debug statements throughout this function
      // (with emoji prefixes) look like leftovers from troubleshooting
      // the CSRF/tokenize flow — harmless in production but noisy;
      // safe to trim once this path is confirmed stable.
      await axios.get(`${BACKEND_URL}/api/csrf/`, { withCredentials: true });

      const csrfToken = getCSRFToken();
      console.log('🔐 CSRF token:', csrfToken ? 'Found' : 'Not found');

      const url = `${BACKEND_URL}/api/tokenize-key/`;
      console.log('🔑 Tokenizing key at:', url);

      const response = await axios.post(
        url,
        { apiKey: apiKey.trim() },
        {
          withCredentials: true,
          headers: {
            'X-CSRFToken': csrfToken || '',
          },
        },
      );

      console.log('✅ Tokenize response:', response.status);

      if (response.status === 200) {
        // Purely a client-side "onboarding complete" marker for
        // App.tsx's gate check — NOT the real API key/token (that's
        // server-side, referenced by an httponly cookie named
        // "gemini_token"). Deliberately named differently here to
        // avoid confusion with that unrelated server-side cookie.
        localStorage.setItem("splash_terms_agreed", "true");
        window.location.reload();
      } else {
        setError("Failed to authenticate API key.");
      }
    } catch (err: any) {
      console.error("❌ Tokenize error:", err);
      console.error("Error response:", err.response?.data);
      setError(err.response?.data?.error || "Failed to connect to the server.");
    }
  };

  // Return the HTML for the browser to show
  return (
    <div style={{ padding: "2rem", maxWidth: "600px", margin: "auto" }}>
      {/* Define a section for terms and conditions */}
      <h1>Terms &amp; Conditions</h1>
      <p>
        By using this app, you agree to the following terms and conditions:
        <br /><br />
        <strong>1. Use in Accordance with Model Provider Terms</strong><br />
        This tool uses the Gemini large language model provided by Google. Your use of this application must fully comply with Google's{' '}
        <a href="https://policies.google.com/terms" target="_blank" rel="noopener noreferrer">AI Terms of Service</a> and any other applicable terms governing the use of their large language models.
        <br /><br />
        <strong>2. Intended for Academic Use Only</strong><br />
        This tool is designed exclusively for educational demonstration and instructional purposes. It is not intended for commercial or recreational use.
        <br /><br />
        <strong>3. No Student Use Without Explicit District Approval</strong><br />
        Students must <strong>not</strong> use this tool unless:<br />
        &nbsp;&nbsp;&bull; Their school district's IT department has explicitly approved such use, <strong>and</strong><br />
        &nbsp;&nbsp;&bull; The use complies with Google's terms for AI services.<br />
        School districts are responsible for ensuring compliance with their institution's policies regarding student interaction with AI technologies.
        <br /><br />
        <strong>4. API Key Handling and Browser Security</strong><br />
        Your API key is temporarily stored in your browser as a token in a secure cookie (not on any external server). For security reasons:<br />
        &nbsp;&nbsp;&bull; Do <strong>not</strong> leave your browser unattended while the key is active.<br />
        &nbsp;&nbsp;&bull; <strong>Refreshing</strong> or <strong>closing</strong> the tab or browser will NOT automatically clear the secure cookie.<br />
        &nbsp;&nbsp;&bull; To exit the application securely, please clear your session cache <strong>or</strong> use the "clear token" button.<br />
        &nbsp;&nbsp;&bull; It is your responsibility to manage this key securely and to avoid unauthorized access.
        <br /><br />
        By clicking "Continue" or using the application, you confirm that you understand and accept these conditions.
      </p>
      {/* Checkbox to agree to terms and conditions */}
      <label style={{ display: "block", margin: "1rem 0" }}>
        <input
          type="checkbox"
          checked={agreed}
          onChange={(e) => setAgreed(e.target.checked)}
        />
        I agree to the terms and conditions
      </label>
      {/* API key input */}
      <label style={{ display: "block", marginBottom: "1rem", position: "relative" }}>
        Enter your Gemini API key:
        <input
          type={showApiKey ? "text" : "password"}
          value={apiKey}
          aria-label="Gemini API Key"
          placeholder="Paste your API key here"
          onChange={(e) => setApiKey(e.target.value)}
          style={{
            width: "100%",
            padding: "0.5rem",
            marginTop: "0.5rem",
            paddingRight: "2.5rem",
          }}
        />
        {/* Toggle API key visibility */}
        <button
          type="button"
          onClick={() => setShowApiKey(prev => !prev)}
          style={{
            position: "absolute",
            top: "2.35rem",
            right: "-2.8rem",
            background: "transparent",
            border: "none",
            fontSize: "1rem",
            cursor: "pointer",
            padding: 0,
            lineHeight: 1,
          }}
          aria-label={showApiKey ? "Hide API key" : "Show API key"}
        >
          <FontAwesomeIcon icon={showApiKey ? faEye : faEyeSlash} />
        </button>
        {/* Link to get an API key */}
        <small style={{ display: "block", marginTop: "0.5rem", fontSize: "0.9rem" }}>
          Don't have a Gemini API key?&nbsp;
          <a
            href="https://makersuite.google.com/app/apikey"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "#007bff", textDecoration: "underline" }}
          >
            Get one here
          </a>.
        </small>
      </label>
      {/* Error message display */}
      {error && (
        <p style={{ color: "red", marginBottom: "1rem" }}>{error}</p>
      )}
      {/* Submit button */}
      <button onClick={() => handleSubmit()} style={{ padding: "0.75rem 1.5rem" }}>
        MOF AI Chemistry
      </button>
    </div>
  );
};

// Export the component for use
export default SplashGate;