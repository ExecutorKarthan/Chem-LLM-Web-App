// Create a function to filter out and store Python code from the LLM
//
// Extracts just the first fenced (```) code block from an LLM
// response, for the "Save to Editor" flow — a chat response is
// typically prose plus one code block, and only the code itself should
// get saved, not the surrounding explanation.
//
// Behavior:
//   - If the response contains at least one ``` fence: everything
//     between the first opening fence and its matching closing fence is
//     kept; anything before the opening fence, and anything after the
//     closing fence (including further code blocks), is dropped. The
//     `break` on the closing fence deliberately stops processing the
//     rest of the response entirely, rather than continuing to scan
//     for additional blocks.
//   - If the response contains no ``` fence at all: the whole response
//     is returned unchanged, on the assumption that a fence-less
//     response is itself just code (or that there's nothing to strip).
//
// Note: `lines.some(...)` re-scans the entire response on every line
// while not yet in a code block, so this is O(n^2) in the number of
// lines — fine for a chat response's typical length, but would be
// worth precomputing once (e.g. `const hasFence = lines.some(...)`
// before the loop) if this were ever used on much longer text.
function processedResponse(response: string): string {
  // Split the LLm response by line and create reference variables
  const lines = response.split("\n");
  let inCodeBlock = false;
  const filteredLines: string[] = [];
  // Go line by line, removing space  
  for (let line of lines) {
    const trimmed = line.trim();
    // Start or stop collecting lines between triple backticks
    if (trimmed.startsWith("```")) {
      if (!inCodeBlock) {
        inCodeBlock = true;
      } 
      // Stop processing after the closing ```
      else {
        break;
      }
      continue;
    }
    // Add the code line if it is in the block or if it is after the ```
    if (inCodeBlock || !lines.some(l => l.trim().startsWith("```"))) {
      filteredLines.push(line);
    }
  }
  // Combine all the line, separated by a new line
  return filteredLines.join("\n");
}

// Export the function for use
export default processedResponse;
