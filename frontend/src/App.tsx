// Import needed modules
import { JSX, useEffect, useState } from "react";
import axios from "axios";
import SplashGate from "./components/Splashgate.js";
import ChemApp from "./components/ChemApp.js";
import { BACKEND_URL } from "./config.js";

// Check if cookie token exists on the server
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

    if (localStorage.getItem("gemini_token")) {
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