// Create a function to filter out and store Python code from the LLM 
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
