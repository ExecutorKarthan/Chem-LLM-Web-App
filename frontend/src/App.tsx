// Import needed modules
import { JSX, useEffect, useState } from "react";
import axios from "axios";
import SplashGate from "./components/Splashgate";
import MainApp from "./components/MainApp";
import { BACKEND_URL } from "./config";

// Check if cookie token exists on the server
const checkTokenServerSide = async (): Promise<boolean> => {
  try {
    // Query the Django server looking for a secure cookie to exist
    const res = await axios.get(
      {BACKEND_URL} + "/api/check-cookie/",
      { withCredentials: true }
    );
    // Return true if the cookie exists
    if (res.data.token_exists === true) {
      return true;
    }
    // Return false if the cookie does not exist
    return false;
  } catch (err) {
    console.error("Failed to check token:", err);
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
      const present = await checkTokenServerSide();
      setCookiePresent(present);
    };
    checkCookie();

    if (localStorage.getItem("gemini_token")) {
      setTermsAgreed(true);
    }
  }, []);

  // If the cookie and terms are present, proceed to the main app
  if (termsAgreed && cookiePresent){
    return <MainApp />;
  }
  // If a cookie is missing or the terms are not agreed to, move to the splashgate to collect them 
  else {
    return <SplashGate />;
  }
}

// Export function for use
export default App;
