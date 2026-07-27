// Import needed modules
import { JSX, useEffect, useState } from "react";
import axios from "axios";
import SplashGate from "./components/Splashgate.js";
import ChemApp from "./components/ChemApp.js";
import { BACKEND_URL } from "./config.js";

// Check if cookie token exists on the server
//
// This is the authoritative check — the real Gemini API key only
// exists server-side, referenced by an httponly cookie the frontend
// can't read directly (see views.check_cookie), so this asks the
// backend to confirm on our behalf rather than inspecting
// document.cookie. It's independent of the `localStorage.getItem
// ("splash_terms_agreed")` check below, which only tracks whether the
// splash gate's terms were agreed to on this browser — both must pass
// to skip the splash gate (see the `termsAgreed && cookiePresent`
// check in App below), since a fresh cookie doesn't imply the terms
// were seen on this browser, and terms agreed on this browser doesn't
// imply the server-side cookie/key are still valid (e.g. after the
// cache entry expires or "Clear Token" is used elsewhere).
const checkTokenServerSide = async (): Promise<boolean> => {
  try {
    const url = `${BACKEND_URL}/api/check-cookie/`;
    console.log('🔍 Checking token at:', url);
    console.log('🔍 Full URL will be:', new URL(url, window.location.href).href);
    
    const res = await axios.get(url, { withCredentials: true });
    
    console.log('✅ Token check response:', res.data);
    
    if (res.data.token_exists === true) {
      return true;
    }
    return false;
  } catch (err) {
    console.error("❌ Failed to check token:", err);
    return false;
  }
};

// Run app
function App(): JSX.Element {
  // Create constatns and their mutations for reference
  const [cookiePresent, setCookiePresent] = useState<boolean>(false);
  const [termsAgreed, setTermsAgreed] = useState<boolean>(false);

  // Use a hook to check for previous agreement and cookies
  useEffect(() => {
    const checkCookie = async () => {
      // First, get CSRF token
      try {
        await axios.get(`${BACKEND_URL}/api/csrf/`, { withCredentials: true });
        console.log('✅ CSRF token obtained');
      } catch (err) {
        console.error('⚠️ Failed to get CSRF token:', err);
      }
      
      // Then check for auth cookie
      const present = await checkTokenServerSide();
      setCookiePresent(present);
      console.log('Cookie present:', present);
      console.log('Backend URL:', BACKEND_URL);
    };
    checkCookie();

    // See the note on checkTokenServerSide above — this is the
    // splash-gate consent flag set by Splashgate.tsx, unrelated to the
    // real server-side auth cookie named "gemini_token".
    if (localStorage.getItem("splash_terms_agreed")) {
      setTermsAgreed(true);
    }
  }, []);

  // If the cookie and terms are present, proceed to the Chemistry app
  if (termsAgreed && cookiePresent) {
    return <ChemApp />;
  }

  // If a cookie is missing or the terms are not agreed to, move to the splashgate to collect them 
  else {
    return <SplashGate />;
  }
}

// Export function for use
export default App;