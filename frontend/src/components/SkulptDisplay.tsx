// SkulptDisplay.tsx
//
// Runs Python turtle-graphics code in the browser using Skulpt, with a
// custom module loader (`builtinRead`) that fetches our MOF renderer
// source files from the Django backend on demand — so the Python source
// for mof_renderer.py and friends never has to be bundled into the
// frontend build. The backend whitelist lives in api/views.py
// (get_mof_engine_file).

import React, { useEffect, useRef, useState, useCallback } from "react";
import { BACKEND_URL } from "../config.js";

interface SkulptDisplayProps {
  code: string;
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

// Modules that live on our backend rather than in Skulpt's own stdlib.
// Any `import X` or `from X import ...` for one of these names triggers
// a synchronous fetch to /api/mof-engine/X.py instead of looking in
// Skulpt's builtin file table.
const MOF_ENGINE_MODULES = new Set([
  "smiles_lexer",
  "smiles_parser",
  "ring_utils",
  "ring_layout",
  "coordination_geometry",
  "layout_engine",
  "turtle_renderer",
  "mof_renderer",
  "mof_data",
]);

// Cache fetched source so re-running code doesn't re-fetch every module
// on every click.
const mofEngineCache = new Map<string, string>();

const fetchMofEngineFileSync = (moduleName: string): string => {
  if (mofEngineCache.has(moduleName)) {
    return mofEngineCache.get(moduleName)!;
  }

  // Skulpt's `read` callback is synchronous, so we use a synchronous XHR
  // here. This only runs for our own whitelisted backend modules, not
  // for general network requests, so blocking briefly is acceptable.
  const xhr = new XMLHttpRequest();
  xhr.open("GET", `${BACKEND_URL}/api/mof-engine/${moduleName}.py`, false);
  xhr.send(null);

  if (xhr.status !== 200) {
    throw new Error(
      `Failed to load module '${moduleName}' from backend (status ${xhr.status})`
    );
  }

  mofEngineCache.set(moduleName, xhr.responseText);
  return xhr.responseText;
};

const SkulptDisplay: React.FC<SkulptDisplayProps> = ({ code }) => {
  const outputRef = useRef<HTMLPreElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  const [outputText, setOutputText] = useState<string>("");
  const [skulptLoaded, setSkulptLoaded] = useState(false);
  const [running, setRunning] = useState(false);

  // Auto-run whenever the parent pushes new code down
  const prevCodeRef = React.useRef<string>("");
  React.useEffect(() => {
    if (code && code !== prevCodeRef.current && skulptLoaded) {
      prevCodeRef.current = code;
      runCode();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, skulptLoaded]);

  // Load Skulpt from CDN once
  useEffect(() => {
    if (window.Sk) {
      setSkulptLoaded(true);
      return;
    }

    const loadScript = (src: string) =>
      new Promise<void>((resolve, reject) => {
        const script = document.createElement("script");
        script.src = src;
        script.async = true;
        script.onload = () => resolve();
        script.onerror = () =>
          reject(new Error(`Failed to load script: ${src}`));
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
  }, []);

  // builtinRead: Skulpt stdlib files use this normally; we intercept
  // requests for our own modules and route them to the backend instead.
  
const builtinRead = (filename: string): string => {
  console.log("Skulpt requested:", filename);

  // 1. If Skulpt is checking for a JS wrapper for your custom module, 
  // do NOT return Python code. Tell Skulpt it doesn't exist so it looks for the .py file.
  if (filename.endsWith(".js")) {
    const baseName = filename.replace(/^.*\//, "").replace(/\.js$/, "");
    if (MOF_ENGINE_MODULES.has(baseName)) {
      throw new Error(`No JS implementation for ${baseName}`);
    }
  }

  // 2. Only intercept and fetch from your backend if it's explicitly a .py file
  const baseName = filename.replace(/^.*\//, "").replace(/\.(py|js)$/, "");

  if (filename.endsWith(".py") && MOF_ENGINE_MODULES.has(baseName)) {
    const source = fetchMofEngineFileSync(baseName);

    console.log("==========");
    console.log(baseName);
    console.log(source.substring(0, 500));
    console.log("==========");

    return source;
  }

  // Fallback to Skulpt's standard library
  if (!window.Sk.builtinFiles || !window.Sk.builtinFiles["files"][filename]) {
    throw new Error(`File not found: '${filename}'`);
  }

  return window.Sk.builtinFiles["files"][filename];
};

  const outf = (text: string) => {
    setOutputText((prev) => prev + text);
  };

  const runCode = () => {
    if (!skulptLoaded || !window.Sk || !window.Sk.builtinFiles) {
      setOutputText("Skulpt is still loading — try again in a moment.");
      return;
    }
    if (!code.trim()) {
      setOutputText("Nothing to run — fill in the MOF fields and click Draw.");
      return;
    }

    setRunning(true);
    setOutputText("");
    if (canvasRef.current) {
      canvasRef.current.innerHTML = "";
    }

    // Small delay so the cleared canvas div is in the DOM before Skulpt
    // measures its dimensions.
    setTimeout(() => {
      const width = canvasRef.current?.clientWidth ?? 700;
      const height = canvasRef.current?.clientHeight ?? 500;

      window.Sk.configure({
        output: outf,
        read: builtinRead,
      });

      window.Sk.TurtleGraphics = {
        target: canvasRef.current,
        width,
        height,
      };

// We explicitly lock down Skulpt's canvas targeting settings here.
      window.Sk.TurtleGraphics = {
        target: canvasRef.current,
        width: width,
        height: height,
        // Pro-tip: If things look offset, adding these tells Skulpt's underlying 
        // engine to center the coordinate context (0,0) exactly in the container midpoints.
      };

      window.Sk.misceval
        .asyncToPromise(() =>
          window.Sk.importMainWithBody("<stdin>", false, code, true)
        )
        .then(
          () => {
            setRunning(false);
          },
          (err: unknown) => {
            let errorMessage = "Unknown error";
            console.error("Skulpt execution error:", err);
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
            setRunning(false);
          }
        );
    }, 100);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%" }}>
      <div style={{ marginBottom: 12 }}>
        <button
          onClick={runCode}
          disabled={!skulptLoaded || running}
          style={{ fontSize: "1rem", padding: "8px 18px" }}
        >
          {running ? "Drawing..." : "Draw MOF"}
        </button>
        {!skulptLoaded && (
          <span style={{ marginLeft: 10, fontSize: 12, color: "#888" }}>
            Loading Python engine...
          </span>
        )}
      </div>

      <div
        ref={canvasRef}
        style={{
          minHeight: 400,
          maxHeight: 600,
          border: "1px solid #ddd",
          borderRadius: 4,
          backgroundColor: "white",
          width: "100%",
        }}
      />

      {outputText.trim() !== "" && (
        <pre
          ref={outputRef}
          style={{
            backgroundColor: "#f5f5f5",
            padding: 10,
            minHeight: 60,
            maxHeight: 160,
            overflowY: "auto",
            whiteSpace: "pre-wrap",
            marginTop: 10,
            width: "100%",
            boxSizing: "border-box",
            fontSize: 12,
          }}
          dangerouslySetInnerHTML={{ __html: outputText }}
        />
      )}
    </div>
  );
};

export default SkulptDisplay;