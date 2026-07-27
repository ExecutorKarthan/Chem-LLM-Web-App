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

// Full element names for the legend labels — purely descriptive chemistry
// facts (not derived from the renderer), so hardcoding this doesn't create
// a drift risk the way duplicating ATOM_COLORS would.
const ELEMENT_NAMES: Record<string, string> = {
  H: "Hydrogen", C: "Carbon", N: "Nitrogen", O: "Oxygen", S: "Sulfur",
  F: "Fluorine", Cl: "Chlorine", Br: "Bromine", I: "Iodine", P: "Phosphorus",
  Cu: "Copper", Zn: "Zinc", Fe: "Iron", Co: "Cobalt", Ni: "Nickel",
  Mn: "Manganese", Pd: "Palladium", Pt: "Platinum", Ag: "Silver", Au: "Gold",
  Cd: "Cadmium", Cr: "Chromium", Ti: "Titanium", Zr: "Zirconium", In: "Indium",
  Al: "Aluminum", Li: "Lithium", Na: "Sodium", K: "Potassium", Rb: "Rubidium",
  Cs: "Cesium", Mg: "Magnesium", Ca: "Calcium", Sr: "Strontium", Ba: "Barium",
  Y: "Yttrium", La: "Lanthanum",
};

const SkulptDisplay: React.FC<SkulptDisplayProps> = ({ code }) => {
  const outputRef = useRef<HTMLPreElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  const [outputText, setOutputText] = useState<string>("");
  const [skulptLoaded, setSkulptLoaded] = useState(false);
  const [running, setRunning] = useState(false);
  const [legendEntries, setLegendEntries] = useState<{ symbol: string; color: string }[]>([]);

  // Auto-run whenever the parent pushes new code down
  const prevCodeRef = React.useRef<string>("");
  React.useEffect(() => {
    if (code && code !== prevCodeRef.current && skulptLoaded) {
      prevCodeRef.current = code;
      runCode();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, skulptLoaded]);

  // Re-fit and redraw (debounced) when the window/container is resized,
  // so a structure drawn on a wide window doesn't stay oversized (or
  // undersized) after the user resizes their browser.
  const resizeTimeoutRef = React.useRef<number | null>(null);
  React.useEffect(() => {
    const handleResize = () => {
      if (resizeTimeoutRef.current !== null) {
        window.clearTimeout(resizeTimeoutRef.current);
      }
      resizeTimeoutRef.current = window.setTimeout(() => {
        if (skulptLoaded && code.trim()) {
          runCode();
        }
      }, 400);
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      if (resizeTimeoutRef.current !== null) {
        window.clearTimeout(resizeTimeoutRef.current);
      }
    };
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
  //
  // Skulpt calls this once per `import`, first probing for a `.js`
  // wrapper (a native-JS implementation of the module) before falling
  // back to a `.py` file. None of our MOF-engine modules have a JS
  // wrapper, so step 1 below deliberately throws for those names —
  // NOT finding the .js is what tells Skulpt to try the .py path next;
  // returning a string here instead would make Skulpt treat this as a
  // (wrong) JS module.

const builtinRead = (filename: string): string => {
  // NOTE: left over from debugging module resolution — safe to remove
  // once this is confirmed stable, but currently harmless (Skulpt's
  // own console, not user-facing).
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
    const marker = "@@LEGEND@@";
    const idx = text.indexOf(marker);
    if (idx === -1) {
      setOutputText((prev) => prev + text);
      return;
    }

    // mof_renderer.py prints one line like "@@LEGEND@@Zn:#7799AA;C:#404040"
    // before drawing starts. Pull that out for the color-key panel instead
    // of showing it as raw output text.
    const before = text.slice(0, idx);
    const afterMarker = text.slice(idx + marker.length);
    const newlineIdx = afterMarker.indexOf("\n");
    const payload = newlineIdx === -1 ? afterMarker : afterMarker.slice(0, newlineIdx);
    const rest = newlineIdx === -1 ? "" : afterMarker.slice(newlineIdx + 1);

    const entries = payload
      .split(";")
      .filter(Boolean)
      .map((pair) => {
        const [symbol, color] = pair.split(":");
        return { symbol, color };
      })
      .filter((e) => e.symbol && e.color);
    setLegendEntries(entries);

    const visible = before + rest;
    if (visible) {
      setOutputText((prev) => prev + visible);
    }
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
    setLegendEntries([]);
    if (canvasRef.current) {
      canvasRef.current.innerHTML = "";
    }

    // Small delay so the cleared canvas div is in the DOM before Skulpt
    // measures its dimensions.
    setTimeout(() => {
      const width = canvasRef.current?.clientWidth ?? 950;
      const height = canvasRef.current?.clientHeight ?? 620;

      window.Sk.configure({
        output: outf,
        read: builtinRead,
      });

      window.Sk.TurtleGraphics = {
        target: canvasRef.current,
        width,
        height,
      };

      // NOTE: this second assignment immediately overwrites the one
      // above with equivalent values — looks like leftover debugging
      // cruft (the comments below suggest it was added while
      // troubleshooting a canvas-offset issue) rather than something
      // intentionally different. Harmless as-is since the two objects
      // are equivalent, but safe to delete if you want to trim this up.
      window.Sk.TurtleGraphics = {
        target: canvasRef.current,
        width: width,
        height: height,
        // Pro-tip: If things look offset, adding these tells Skulpt's underlying 
        // engine to center the coordinate context (0,0) exactly in the container midpoints.
      };

      // mof_renderer.py's auto-fit logic (MIN/MAX_CANVAS_WIDTH/HEIGHT) is
      // otherwise a set of fixed Python constants with no idea how much
      // room the current browser window actually has. Overriding them
      // here — right before the generated drawing code runs — makes the
      // structure size/scale itself against the real, current container
      // size instead of a generic desktop-sized default. `min`/`max`
      // guard against a window narrower/shorter than the module's normal
      // minimum, so the fit floor never exceeds what's actually available.
      const sizingPreamble =
        `import mof_renderer\n` +
        `mof_renderer.MIN_CANVAS_WIDTH = min(420.0, ${width})\n` +
        `mof_renderer.MAX_CANVAS_WIDTH = max(${width}, 420.0)\n` +
        `mof_renderer.MIN_CANVAS_HEIGHT = min(360.0, ${height})\n` +
        `mof_renderer.MAX_CANVAS_HEIGHT = max(${height}, 360.0)\n`;
      const codeToRun = sizingPreamble + code;

      window.Sk.misceval
        .asyncToPromise(() =>
          window.Sk.importMainWithBody("<stdin>", false, codeToRun, true)
        )
        .then(() => {
          console.log("Success");
          })
        .catch((err: any) => {
           // This logs the full internal Skulpt error to your Browser Developer Tools
          console.error("SKULPT FATAL ERROR:", err);
          console.error("DEBUG - Last few lines of code executed:", code.split('\n').slice(-10));
          // Alert the user with the specific error type
          alert(`Python Error: ${err.toString()}`);
        });
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
          minHeight: 380,
          maxHeight: 640,
          border: "1px solid #ddd",
          borderRadius: 4,
          backgroundColor: "white",
          width: "100%",
          overflow: "auto",
        }}
      />

      {legendEntries.length > 0 && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "6px 16px",
            marginTop: 10,
            padding: "8px 12px",
            border: "1px solid #eee",
            borderRadius: 4,
            backgroundColor: "#fafafa",
            fontSize: 12,
          }}
        >
          {legendEntries.map(({ symbol, color }) => (
            <div key={symbol} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span
                style={{
                  display: "inline-block",
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  backgroundColor: color,
                  border: "1px solid rgba(0,0,0,0.2)",
                  flexShrink: 0,
                }}
              />
              <span>
                {symbol}
                {ELEMENT_NAMES[symbol] ? ` — ${ELEMENT_NAMES[symbol]}` : ""}
              </span>
            </div>
          ))}
        </div>
      )}

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