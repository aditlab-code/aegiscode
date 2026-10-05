/**
 * src/services/diagnosticService.js
 *
 * Lightweight, high-performance diagnostic and lint error detector for
 * live log streams and Monaco code editor markers.
 */

// Regex patterns for single-pass classification of logs & code errors.
export const SYNTAX_REGEX = /\b(?:syntaxerror|parsing error|unexpected token|invalid syntax|parse error|unterminated (?:string|regex|comment)|expected expression)\b/i;
export const TYPE_REGEX = /\b(?:typeerror|cannot find name|is not assignable to type|property '.*' does not exist|ts\(\d+\)|unhashable type)\b/i;
export const LINT_REGEX = /\b(?:warning|eslint|flake8|ruff|no-unused|unused (?:var|variable|import)|deprecated|prefer-|rule:)\b/i;
export const ERROR_REGEX = /\b(?:error|exception|failed|traceback|referenceerror|fatal|cannot read propert(?:y|ies))\b/i;

// Regex to capture file location: "path/to/file.ext:42:15" or File "path/to/file.ext", line 42
export const FILE_LINE_REGEX = /(?:File\s+"([^"]+)",\s*line\s*(\d+)|([a-zA-Z0-9_\-\.\/\\~]+\.[a-zA-Z0-9]+):(\d+)(?::(\d+))?)/;

/**
 * Classify a raw string line or object into a diagnostic item.
 * @param {string|object} item
 * @param {number} idx
 * @returns {object}
 */
export function classifyDiagnostic(item, idx = 0) {
  const rawText = typeof item === "string" ? item : (item?.text || item?.message || JSON.stringify(item));
  const ts = item?.ts || Date.now();
  const id = item?.id || `diag-${idx}-${ts}`;

  let type = "info";
  let severity = "info";
  let label = "Info";

  if (SYNTAX_REGEX.test(rawText)) {
    type = "syntax";
    severity = "error";
    label = "Syntax Error";
  } else if (TYPE_REGEX.test(rawText)) {
    type = "type";
    severity = "error";
    label = "Type Error";
  } else if (LINT_REGEX.test(rawText)) {
    type = "lint";
    severity = "warning";
    label = "Lint / Warning";
  } else if (ERROR_REGEX.test(rawText)) {
    type = "error";
    severity = "error";
    label = "Error";
  }

  // Extract file / line info if present
  let file = item?.file || null;
  let line = item?.line ? Number(item.line) : null;
  let col = item?.col ? Number(item.col) : null;

  if (!file && typeof rawText === "string") {
    const locMatch = rawText.match(FILE_LINE_REGEX);
    if (locMatch) {
      if (locMatch[1]) {
        file = locMatch[1];
        line = parseInt(locMatch[2], 10);
      } else if (locMatch[3]) {
        file = locMatch[3];
        line = parseInt(locMatch[4], 10);
        if (locMatch[5]) {
          col = parseInt(locMatch[5], 10);
        }
      }
    }
  }

  return {
    id,
    text: rawText,
    type,
    severity,
    label,
    file,
    line,
    col,
    ts,
  };
}

/**
 * Map Monaco editor markers to standardized diagnostic objects.
 * @param {Array} markers
 * @param {string} filePath
 * @returns {Array}
 */
export function mapMonacoMarkersToDiagnostics(markers = [], filePath = "") {
  if (!Array.isArray(markers)) return [];
  return markers.map((m, idx) => {
    let type = "lint";
    let severity = "warning";
    let label = "Lint / Warning";

    // Monaco MarkerSeverity: Hint = 1, Info = 2, Warning = 4, Error = 8
    const sev = m.severity ?? 4;
    const msg = m.message || "";

    if (SYNTAX_REGEX.test(msg) || /syntax|expected/i.test(m.source || "")) {
      type = "syntax";
      severity = "error";
      label = "Syntax Error";
    } else if (TYPE_REGEX.test(msg) || /ts\(\d+\)/.test(msg)) {
      type = "type";
      severity = "error";
      label = "Type Error";
    } else if (sev === 8) {
      type = "error";
      severity = "error";
      label = "Error";
    } else {
      type = "lint";
      severity = "warning";
      label = "Lint / Warning";
    }

    return {
      id: `marker-${idx}-${m.startLineNumber || 0}-${m.startColumn || 0}`,
      text: msg,
      type,
      severity,
      label,
      file: filePath,
      line: m.startLineNumber || 1,
      col: m.startColumn || 1,
      ts: Date.now(),
      source: m.source || "editor",
    };
  });
}

/**
 * Summarize counts of classified diagnostics.
 * @param {Array} diagnostics
 * @returns {object}
 */
export function summarizeDiagnostics(diagnostics = []) {
  const summary = {
    total: 0,
    syntax: 0,
    lint: 0,
    type: 0,
    error: 0,
    info: 0,
  };

  if (!Array.isArray(diagnostics)) return summary;

  for (const d of diagnostics) {
    if (!d) continue;
    if (d.type === "syntax") summary.syntax++;
    else if (d.type === "lint") summary.lint++;
    else if (d.type === "type") summary.type++;
    else if (d.type === "error") summary.error++;
    else summary.info++;

    if (d.type && d.type !== "info") {
      summary.total++;
    }
  }

  return summary;
}

/**
 * Comprehensive, lightweight JSON linter & syntax validator.
 * Detects comments, single quotes, trailing commas, unquoted keys, duplicate keys,
 * and structural syntax errors with exact line and column locations.
 * @param {string} code
 * @param {string} filePath
 * @returns {Array}
 */
export function validateJsonSyntax(code = "", filePath = "") {
  if (!code || typeof code !== "string") return [];
  const errors = [];
  const lines = code.split("\n");

  let inMultiComment = false;
  const seenKeys = new Map();

  for (let i = 0; i < lines.length; i++) {
    const lineNum = i + 1;
    const rawLine = lines[i];
    const trimmed = rawLine.trim();
    if (!trimmed) continue;

    // Check block comments /* ... */
    if (trimmed.startsWith("/*") || inMultiComment) {
      errors.push({
        id: `json-lint-comment-${lineNum}`,
        text: "JSON Lint: Block comments '/* ... */' are not permitted in standard JSON",
        type: "lint",
        severity: "warning",
        label: "Lint / Warning",
        file: filePath,
        line: lineNum,
        col: rawLine.indexOf("/*") >= 0 ? rawLine.indexOf("/*") + 1 : 1,
        source: "json-linter",
      });
      if (trimmed.includes("*/")) {
        inMultiComment = false;
      } else {
        inMultiComment = true;
      }
      continue;
    }

    // Check single-line comment // ...
    if (trimmed.startsWith("//")) {
      errors.push({
        id: `json-lint-comment-${lineNum}`,
        text: "JSON Lint: Single-line comments '//' are not permitted in standard JSON",
        type: "lint",
        severity: "warning",
        label: "Lint / Warning",
        file: filePath,
        line: lineNum,
        col: rawLine.indexOf("//") + 1 || 1,
        source: "json-linter",
      });
      continue;
    }

    // Check trailing comma before closing brace or bracket (single-line or multi-line)
    let hasTrailingComma = /,\s*[}\]]/.test(trimmed);
    if (!hasTrailingComma && trimmed.endsWith(",")) {
      for (let j = i + 1; j < lines.length; j++) {
        const nextTrimmed = lines[j].trim();
        if (!nextTrimmed || nextTrimmed.startsWith("//") || nextTrimmed.startsWith("/*")) continue;
        if (nextTrimmed.startsWith("}") || nextTrimmed.startsWith("]")) {
          hasTrailingComma = true;
        }
        break;
      }
    }
    if (hasTrailingComma) {
      const col = rawLine.lastIndexOf(",") + 1;
      errors.push({
        id: `json-trailing-comma-${lineNum}`,
        text: "JSON SyntaxError: Trailing comma is not permitted in JSON",
        type: "syntax",
        severity: "error",
        label: "Syntax Error",
        file: filePath,
        line: lineNum,
        col: col || 1,
        source: "json-linter",
      });
    }

    // Check single-quoted strings: e.g. 'key': or: 'value'
    if (/'[^']*'/.test(trimmed)) {
      const col = rawLine.indexOf("'") + 1;
      errors.push({
        id: `json-single-quote-${lineNum}`,
        text: "JSON SyntaxError: Strings must use double quotes, single quotes are not permitted in JSON",
        type: "syntax",
        severity: "error",
        label: "Syntax Error",
        file: filePath,
        line: lineNum,
        col: col || 1,
        source: "json-linter",
      });
    }

    // Check unquoted object keys: e.g. foo: "bar"
    const unquotedKeyMatch = trimmed.match(/^([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:/);
    if (unquotedKeyMatch) {
      const key = unquotedKeyMatch[1];
      const col = rawLine.indexOf(key) + 1;
      errors.push({
        id: `json-unquoted-key-${lineNum}`,
        text: `JSON SyntaxError: Property key '${key}' must be enclosed in double quotes`,
        type: "syntax",
        severity: "error",
        label: "Syntax Error",
        file: filePath,
        line: lineNum,
        col: col || 1,
        source: "json-linter",
      });
    }

    // Check duplicate keys: e.g. "key": ...
    const keyMatch = trimmed.match(/^"([^"\\]*(?:\\.[^"\\]*)*)"\s*:/);
    if (keyMatch) {
      const k = keyMatch[1];
      if (seenKeys.has(k)) {
        errors.push({
          id: `json-duplicate-key-${lineNum}`,
          text: `JSON Lint: Duplicate object key "${k}" (previously defined on line ${seenKeys.get(k)})`,
          type: "lint",
          severity: "warning",
          label: "Lint / Warning",
          file: filePath,
          line: lineNum,
          col: rawLine.indexOf(`"${k}"`) + 1 || 1,
          source: "json-linter",
        });
      } else {
        seenKeys.set(k, lineNum);
      }
    }
  }

  // 2. Full parser check for unclosed braces / invalid numbers / malformed structures
  try {
    JSON.parse(code);
  } catch (e) {
    let lineNum = 1;
    let colNum = 1;
    const matchLineCol = e.message.match(/line (\d+) column (\d+)/i);
    const matchPos = e.message.match(/at position (\d+)/i);

    if (matchLineCol) {
      lineNum = parseInt(matchLineCol[1], 10);
      colNum = parseInt(matchLineCol[2], 10);
    } else if (matchPos) {
      const pos = parseInt(matchPos[1], 10);
      const upToPos = code.substring(0, pos);
      const splitLines = upToPos.split("\n");
      lineNum = splitLines.length;
      colNum = splitLines[splitLines.length - 1].length + 1;
    } else {
      lineNum = lines.length;
      colNum = lines[lines.length - 1].length + 1;
    }

    const alreadyHasSyntaxError = errors.some(
      (err) => err.line === lineNum && err.type === "syntax"
    );
    if (!alreadyHasSyntaxError) {
      errors.push({
        id: `syntax-json-parse-${lineNum}-${colNum}`,
        text: `JSON SyntaxError: ${e.message}`,
        type: "syntax",
        severity: "error",
        label: "Syntax Error",
        file: filePath,
        line: lineNum,
        col: colNum,
        source: "json-linter",
      });
    }
  }

  return errors;
}

/**
 * Comprehensive, lightweight .gitignore linter & syntax validator.
 * Validates gitignore files against Git specifications and common pitfalls:
 * - Empty negation '!' without pattern
 * - Trailing whitespace (prevents patterns from matching)
 * - Leading whitespace (treated literally by Git)
 * - Windows backslashes '\' (Git requires forward slash '/')
 * - Duplicate pattern definitions
 * - Redundant './' prefixes
 * - Consecutive slashes '//'
 * - Negation of previously excluded parent directory (Git cannot re-include files within excluded directories)
 *
 * @param {string} code
 * @param {string} filePath
 * @returns {Array}
 */
export function validateGitignoreSyntax(code = "", filePath = "") {
  if (!code || typeof code !== "string") return [];
  const errors = [];
  const lines = code.split("\n");

  const seenPatterns = new Map();
  const excludedDirectories = new Map(); // cleanDir -> lineNum

  for (let i = 0; i < lines.length; i++) {
    const lineNum = i + 1;
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // Check blank line that contains only whitespace
    if (!trimmed) {
      if (rawLine.length > 0) {
        errors.push({
          id: `gitignore-blank-space-${lineNum}`,
          text: ".gitignore Lint: Blank line contains whitespace",
          type: "lint",
          severity: "warning",
          label: "Lint / Warning",
          file: filePath,
          line: lineNum,
          col: 1,
          source: "gitignore-linter",
        });
      }
      continue;
    }

    // Skip comment lines
    if (trimmed.startsWith("#")) {
      continue;
    }

    // 1. Leading whitespace check
    if (rawLine.startsWith(" ") || rawLine.startsWith("\t")) {
      errors.push({
        id: `gitignore-leading-space-${lineNum}`,
        text: ".gitignore Lint: Leading whitespace before pattern (Git treats leading spaces as literal filename characters)",
        type: "lint",
        severity: "warning",
        label: "Lint / Warning",
        file: filePath,
        line: lineNum,
        col: 1,
        source: "gitignore-linter",
      });
    }

    // 2. Trailing whitespace check (if not escaped with backslash)
    if (/[ \t]+$/.test(rawLine) && !/\\ $/.test(rawLine)) {
      errors.push({
        id: `gitignore-trailing-space-${lineNum}`,
        text: ".gitignore Lint: Trailing whitespace detected (Git treats unescaped trailing space as literal filename character)",
        type: "lint",
        severity: "warning",
        label: "Lint / Warning",
        file: filePath,
        line: lineNum,
        col: rawLine.length,
        source: "gitignore-linter",
      });
    }

    // 3. Empty negation '!' check
    if (trimmed === "!" || trimmed === "! ") {
      errors.push({
        id: `gitignore-empty-negation-${lineNum}`,
        text: ".gitignore SyntaxError: Empty negation pattern '!' with no file or directory specified",
        type: "syntax",
        severity: "error",
        label: "Syntax Error",
        file: filePath,
        line: lineNum,
        col: 1,
        source: "gitignore-linter",
      });
      continue;
    }

    // 4. Windows backslash check (e.g. dist\*.js or bin\Release)
    if (/\\[a-zA-Z0-9_\-.]/.test(trimmed)) {
      const bCol = rawLine.indexOf("\\") + 1;
      errors.push({
        id: `gitignore-backslash-${lineNum}`,
        text: ".gitignore Lint: Backslash '\\' used in path. Gitignore requires forward slash '/' as path separator",
        type: "lint",
        severity: "warning",
        label: "Lint / Warning",
        file: filePath,
        line: lineNum,
        col: bCol || 1,
        source: "gitignore-linter",
      });
    }

    // 5. Redundant leading './' prefix
    if (trimmed.startsWith("./")) {
      const clean = trimmed.slice(2);
      errors.push({
        id: `gitignore-redundant-prefix-${lineNum}`,
        text: `.gitignore Lint: Redundant './' prefix. Use '${clean}' or '/${clean}' instead`,
        type: "lint",
        severity: "warning",
        label: "Lint / Warning",
        file: filePath,
        line: lineNum,
        col: rawLine.indexOf("./") + 1 || 1,
        source: "gitignore-linter",
      });
    }

    // 6. Consecutive slashes '//'
    if (trimmed.includes("//")) {
      errors.push({
        id: `gitignore-consecutive-slashes-${lineNum}`,
        text: ".gitignore Lint: Consecutive slashes '//' detected in pattern",
        type: "lint",
        severity: "warning",
        label: "Lint / Warning",
        file: filePath,
        line: lineNum,
        col: rawLine.indexOf("//") + 1 || 1,
        source: "gitignore-linter",
      });
    }

    // 7. Duplicate pattern check
    const normalizedPattern = trimmed;
    if (seenPatterns.has(normalizedPattern)) {
      const prevLine = seenPatterns.get(normalizedPattern);
      errors.push({
        id: `gitignore-duplicate-${lineNum}`,
        text: `.gitignore Lint: Duplicate pattern '${normalizedPattern}' (previously defined on line ${prevLine})`,
        type: "lint",
        severity: "warning",
        label: "Lint / Warning",
        file: filePath,
        line: lineNum,
        col: 1,
        source: "gitignore-linter",
      });
    } else {
      seenPatterns.set(normalizedPattern, lineNum);
    }

    // 8. Negation ordering & parent directory exclusion check
    if (trimmed.startsWith("!")) {
      const negatedPath = trimmed.slice(1).replace(/^\//, "");
      for (const [dir, excludedLine] of excludedDirectories.entries()) {
        if (negatedPath === dir || negatedPath.startsWith(dir + "/")) {
          errors.push({
            id: `gitignore-negate-excluded-${lineNum}`,
            text: `.gitignore Lint: Cannot re-include '!${negatedPath}' because parent directory '${dir}/' was excluded on line ${excludedLine} (Git does not re-include files within excluded directories; use '${dir}/*' to allow re-inclusion)`,
            type: "lint",
            severity: "warning",
            label: "Lint / Warning",
            file: filePath,
            line: lineNum,
            col: 1,
            source: "gitignore-linter",
          });
          break;
        }
      }
    } else {
      // If this pattern excludes a whole directory (ends with /)
      if (trimmed.endsWith("/")) {
        const cleanDir = trimmed.replace(/^\//, "").replace(/\/+$/, "");
        if (cleanDir && !cleanDir.includes("*")) {
          excludedDirectories.set(cleanDir, lineNum);
        }
      }
    }
  }

  return errors;
}

/**
 * Fast, lightweight syntax analyzer for common programming languages.
 * Validates JSON, bracket balances, and block terminators (e.g. Python ':').
 * @param {string} code
 * @param {string} language
 * @param {string} filePath
 * @returns {Array}
 */
export function validateCodeSyntax(code = "", language = "", filePath = "") {
  if (!code || typeof code !== "string") return [];
  const errors = [];
  const lines = code.split("\n");

  // 1. JSON validation
  if (language === "json" || filePath.endsWith(".json")) {
    return validateJsonSyntax(code, filePath);
  }

  // 2. Gitignore / Ignore files validation
  const lowerPath = filePath.toLowerCase();
  const lowerLang = String(language || "").toLowerCase();
  if (
    lowerLang === "gitignore" ||
    lowerLang === "ignore" ||
    lowerPath === ".gitignore" ||
    lowerPath.endsWith("/.gitignore") ||
    lowerPath.endsWith(".gitignore") ||
    lowerPath.endsWith(".dockerignore") ||
    lowerPath.endsWith(".npmignore") ||
    lowerPath.endsWith(".eslintignore") ||
    lowerPath.endsWith(".prettierignore")
  ) {
    return validateGitignoreSyntax(code, filePath);
  }

  // 2. Bracket balance & basic syntax check (for JS, TS, Python, etc.)
  const stack = [];
  const pairs = { ")": "(", "}": "{", "]": "[" };
  let inBlockComment = false;

  for (let i = 0; i < lines.length; i++) {
    const lineNum = i + 1;
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // Check block comment /* ... */
    if (trimmed.startsWith("/*")) inBlockComment = true;
    if (inBlockComment) {
      if (trimmed.includes("*/")) inBlockComment = false;
      continue;
    }

    // Skip full comment lines
    if (trimmed.startsWith("//") || trimmed.startsWith("#")) continue;

    // Python syntax rules (missing ':' on compound statement headers)
    if (language === "python" || filePath.endsWith(".py")) {
      const pyBlockStart = /^(?:def\s+[a-zA-Z0-9_]+\s*\(.*?\)|class\s+[a-zA-Z0-9_]+(?:\(.*?\))?|if\s+.+|elif\s+.+|else|for\s+.+\s+in\s+.+|while\s+.+|try|except(?:\s+.+)?|finally|with\s+.+)$/;
      if (pyBlockStart.test(trimmed) && !trimmed.endsWith(":") && !trimmed.endsWith("\\")) {
        errors.push({
          id: `syntax-py-colon-${lineNum}`,
          text: `SyntaxError: expected ':' at end of line`,
          type: "syntax",
          severity: "error",
          label: "Syntax Error",
          file: filePath,
          line: lineNum,
          col: rawLine.length,
          source: "syntax-checker",
        });
      }
    }

    // Bracket scanner (ignoring string literals)
    let inQuote = null;
    let escaped = false;
    for (let c = 0; c < rawLine.length; c++) {
      const char = rawLine[c];
      if (escaped) {
        escaped = false;
        continue;
      }
      if (char === "\\") {
        escaped = true;
        continue;
      }
      if (inQuote) {
        if (char === inQuote) inQuote = null;
        continue;
      }
      if (char === '"' || char === "'" || char === "`") {
        inQuote = char;
        continue;
      }

      if (char === "(" || char === "{" || char === "[") {
        stack.push({ char, line: lineNum, col: c + 1 });
      } else if (char === ")" || char === "}" || char === "]") {
        if (stack.length === 0) {
          errors.push({
            id: `syntax-unexpected-${lineNum}-${c + 1}`,
            text: `SyntaxError: unexpected token '${char}'`,
            type: "syntax",
            severity: "error",
            label: "Syntax Error",
            file: filePath,
            line: lineNum,
            col: c + 1,
            source: "syntax-checker",
          });
        } else {
          const top = stack.pop();
          if (top.char !== pairs[char]) {
            errors.push({
              id: `syntax-mismatched-${lineNum}-${c + 1}`,
              text: `SyntaxError: mismatched '${char}', expected closing for '${top.char}' from line ${top.line}`,
              type: "syntax",
              severity: "error",
              label: "Syntax Error",
              file: filePath,
              line: lineNum,
              col: c + 1,
              source: "syntax-checker",
            });
          }
        }
      }
    }
  }

  // Any unclosed brackets left on stack
  if (stack.length > 0) {
    const unclosed = stack[stack.length - 1];
    errors.push({
      id: `syntax-unclosed-${unclosed.line}-${unclosed.col}`,
      text: `SyntaxError: unclosed '${unclosed.char}' opened at line ${unclosed.line}`,
      type: "syntax",
      severity: "error",
      label: "Syntax Error",
      file: filePath,
      line: unclosed.line,
      col: unclosed.col,
      source: "syntax-checker",
    });
  }

  return errors;
}
