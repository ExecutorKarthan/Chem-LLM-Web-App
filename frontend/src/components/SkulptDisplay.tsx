// Import needed modules
import React, { useEffect, useRef, useState } from "react";
import { BACKEND_URL } from "../config.js";

// Define interfaces for type safety on objects used by the code
interface Puzzle {
  id: string;
  code: string;
  image_url: string;
}
interface SkulptDisplayProps {
  code: string;
  onCodeChange?: (newCode: string) => void;
}
declare global {
  interface Window {
    Sk: Skulpt;
  }
}
interface Skulpt {
  configure: (options: SkulptConfigureOptions) => void;
  importMainWithBody: (
    name: string,
    dumpGlobals: boolean,
    body: string,
    canSuspend: boolean
  ) => Promise<void>;
  misceval: {
    asyncToPromise: <T>(fn: () => T | Promise<T>) => Promise<T>;
  };
  builtinFiles: {
    files: Record<string, string>;
  };
  TurtleGraphics?: {
    target: HTMLElement | null;
    width?: number;
    height?: number;
  };
}
interface SkulptConfigureOptions {
  output?: (text: string) => void;
  read?: (filename: string) => string;
}

// Define Skulpt Display so it can execute inputted python code
const SkulptDisplay: React.FC<SkulptDisplayProps> = ({ code, onCodeChange }) => {

  // References to access DOM elements
  const outputRef = useRef<HTMLPreElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  // Define constants and their mutators
  const [outputText, setOutputText] = useState<string>("");
  const [showPuzzle, setShowPuzzle] = useState<boolean>(false);
  const [puzzleData, setPuzzleData] = useState<Puzzle[]>([]);
  const [selectedPuzzle, setSelectedPuzzle] = useState<Puzzle | null>(null);
  const [skulptLoaded, setSkulptLoaded] = useState(false);

  // Create a hook to load primary pieces for the app to be ready
  useEffect(() => {
    // Fetch puzzle data from Django backend server
    fetch({BACKEND_URL} + "/api/puzzles/")
      .then((res) => res.json())
      .then((data) => setPuzzleData(data))
      .catch((err) => console.error("Failed to load puzzles", err));
    // If the Skulpt window is not ready, run the scripts to load the scripts
    if (!window.Sk) {
      const loadScript = (src: string) =>
        new Promise<void>((resolve, reject) => {
          const script = document.createElement("script");
          script.src = src;
          script.async = true;
          script.onload = () => resolve();
          script.onerror = () => reject(new Error(`Failed to load script: ${src}`));
          document.body.appendChild(script);
        });
      (async () => {
        try {
          await loadScript("https://cdn.jsdelivr.net/npm/skulpt/dist/skulpt.min.js");
          await loadScript("https://cdn.jsdelivr.net/npm/skulpt/dist/skulpt-stdlib.js");
          setSkulptLoaded(true);
        } catch (err) {
          console.error(err);
        }
      })();
    } else {
      setSkulptLoaded(true);
    }
  }, []);

  // Load the Skulpt built-in files for it to function
  const builtinRead = (x: string) => {
    if (!window.Sk.builtinFiles || !window.Sk.builtinFiles["files"][x]) {
      throw new Error(`File not found: '${x}'`);
    }
    return window.Sk.builtinFiles["files"][x];
  };

  // Collect Skulpt output text
  const outf = (text: string) => {
    setOutputText((prev) => prev + text);
  };

  // Executes code from the editor in Skulpt
  const runCode = () => {
    // Reload Skulpt if it is not loaded
    if (!skulptLoaded || !window.Sk || !window.Sk.builtinFiles) {
      alert("Skulpt is not fully loaded yet. Try again in a moment.");
      return;
    }
    // Default show nothing 
    setShowPuzzle(false);
    setOutputText("");
    // Sets the current canvas reference to its current HTML of ""
    if (canvasRef.current) {
      canvasRef.current.innerHTML = "";
    }
    // Configure Skulpt window with a 100 second delay so the DOM has time to load before Skulpt
    setTimeout(() => {
      // Define current size of the canvas but defaults to 600 px
      const width = canvasRef.current?.clientWidth ?? 600;
      const height = canvasRef.current?.clientHeight ?? 600;
      // Configure Skulpt runtime
      window.Sk.configure({
        output: outf,
        read: builtinRead,
      });
      // Set turtle graphics window size
      window.Sk.TurtleGraphics = {
        target: canvasRef.current,
        width,
        height,
      };
      // Load preset items for the code to execute correctly on a consistent basis
      const injectedPreamble = `
import turtle
screen = turtle.Screen()
screen.setup(width=${width}, height=${height})
screen.setworldcoordinates(-${Math.floor(width / 2)}, -${Math.floor(height / 2)}, ${Math.floor(width / 2)}, ${Math.floor(height / 2)})
`;
      //Combine preamble with entered code
      const combinedCode = injectedPreamble + "\n" + code;
      // Async execution of Python code in Skulpt
      window.Sk.misceval
        .asyncToPromise(() =>
          window.Sk.importMainWithBody("<stdin>", false, combinedCode, true)
        )
        .then(
          () => console.log("Execution success"),
          (err: unknown) => {
            let errorMessage = "Unknown error";
            console.error("Raw error object:", err);
            if (err instanceof Error) {
              errorMessage = err.message;
            } else if (typeof err === "string") {
              errorMessage = err;
            }
            setOutputText(
              (prev) =>
                prev +
                "<br><strong style='color:red'>Error: </strong>" +
                errorMessage
            );
          }
        );
    }, 100);
  };

  // Response when a puzzle button is selected - displays puzzle code in the editor and an image of the puzzle in the Skulpt window
  const handleShowPuzzle = (label: string, id: string) => {
    // Create variables for reference
    let puzzle: Puzzle | null = null;
    let processedId: string = id; 
    let count: number = 0;
    // Check each ID and strip out its spaces
    while(processedId.indexOf(" ") > 0 && count < 5){
      processedId = processedId.substring(0, processedId.indexOf(" ")) + processedId.substring(processedId.indexOf(" ") +1)
      count+= 1
    }
    // Check the newly processed ID and match it to its correct puzzle data
    for( let i = 0; i < puzzleData.length; i++){ 
      if(puzzleData[i].id.toLowerCase().indexOf(label.toLowerCase()+processedId.toLocaleLowerCase()) > -1 
          && puzzleData[i].id.length == (label + processedId).length){
        puzzle = puzzleData[i];
        break
      }
    }
    // If puzzle data is found, display it
    if (puzzle) {
      setSelectedPuzzle(puzzle);
      setShowPuzzle(true);
      if (onCodeChange) {
        onCodeChange(puzzle.code);
      }
    }
  };

  // Render the code in HTML
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: "100%" }}>
      <div style={{ marginBottom: 20 }}>
        {/* Create a button to run the code */}
        <button onClick={runCode} disabled={!skulptLoaded} style={{ fontSize: "1.2rem", padding: "10px 20px" }}>
          Run Code
        </button>
      </div>
      {/* Create buttons that will categorize and list the different types of puzzles */}
      <div style={{ display: "flex", justifyContent: "space-around", width: "100%", maxWidth: 800 }}>
        {[
          { label: "Small", ids: ["Linear", "One Branch", "One Branch Gate"] },
          { label: "Medium", ids: ["Linear", "One Branch", "One Branch Gate"] },
          { label: "Large", ids: ["Linear", "One Branch", "One Branch Gate"] },
          { label: "Solved", ids: ["Linear", "One Branch", "One Branch Gate"] },
        ].map(({ label, ids }) => (
          <div key={label} style={{ textAlign: "center" }}>
            <h3>{label}</h3>
            {ids.map((id) => (
              <button key={id} style={{ display: "block", margin: "6px auto" }} onClick={() => handleShowPuzzle(label, id)}>
                {id} Puzzle
              </button>
            ))}
          </div>
        ))}
      </div>
      <div style={{ marginTop: 20, width: "100%" }}>
        {/* Dsiplay the image of the puzzle when its button is clicked */}
        {showPuzzle && selectedPuzzle ? (
          <img
            src={`${BACKEND_URL}${selectedPuzzle.image_url}`}
            alt={`Puzzle ${selectedPuzzle.id}`}
            style={{
              marginTop: 20,
              maxWidth: "100%",
              height: "auto",
              border: "1px solid #ccc",
            }}
          />
        ) : (
          <>
            <div
              ref={canvasRef}
              style={{
                marginTop: 20,
                minHeight: 200,
                maxHeight: 600,
                flexGrow: 1,
                border: "1px solid black",
                backgroundColor: "white",
                width: "100%",
              }}
            />
            {/* Show output text only if there's output */}
            {outputText.trim() !== "" && (
              <pre
                ref={outputRef}
                style={{
                  backgroundColor: "#f0f0f0",
                  padding: "10px",
                  minHeight: 100,
                  maxHeight: 200,
                  overflowY: "auto",
                  whiteSpace: "pre-wrap",
                  marginTop: 20,
                  width: "100%",
                  boxSizing: "border-box",
                }}
                dangerouslySetInnerHTML={{ __html: outputText }}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
};

// Export the component for use
export default SkulptDisplay;
