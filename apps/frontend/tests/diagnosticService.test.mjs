import test from "node:test";
import assert from "node:assert/strict";
import {
  classifyDiagnostic,
  mapMonacoMarkersToDiagnostics,
  summarizeDiagnostics,
  validateCodeSyntax,
} from "../src/services/diagnosticService.js";

test("1. diagnosticService: classifyDiagnostic categorizes syntax errors & extracts locations", () => {
  const line = "SyntaxError: Unexpected token '{' in src/components/AppNavbar.vue:42:15";
  const item = classifyDiagnostic(line, 1);

  assert.equal(item.type, "syntax");
  assert.equal(item.severity, "error");
  assert.equal(item.label, "Syntax Error");
  assert.equal(item.file, "src/components/AppNavbar.vue");
  assert.equal(item.line, 42);
  assert.equal(item.col, 15);
});

test("2. diagnosticService: classifyDiagnostic categorizes type errors and Python traceback", () => {
  const typeLine = "TypeError: Cannot read properties of undefined (reading 'map')";
  const typeItem = classifyDiagnostic(typeLine, 2);
  assert.equal(typeItem.type, "type");
  assert.equal(typeItem.severity, "error");

  const pyLine = 'File "src/agent_ai/runtime/planner.py", line 128, in execute_step';
  const pyItem = classifyDiagnostic(pyLine, 3);
  assert.equal(pyItem.file, "src/agent_ai/runtime/planner.py");
  assert.equal(pyItem.line, 128);
});

test("3. diagnosticService: classifyDiagnostic categorizes linter warnings", () => {
  const lintLine = "warning: unused variable 'token' [eslint: no-unused-vars] in utils.js:20";
  const item = classifyDiagnostic(lintLine, 4);

  assert.equal(item.type, "lint");
  assert.equal(item.severity, "warning");
  assert.equal(item.label, "Lint / Warning");
  assert.equal(item.file, "utils.js");
  assert.equal(item.line, 20);
});

test("4. diagnosticService: classifyDiagnostic leaves clean info lines unflagged", () => {
  const infoLine = "[vite] hmr update /src/App.vue";
  const item = classifyDiagnostic(infoLine, 5);

  assert.equal(item.type, "info");
  assert.equal(item.severity, "info");
  assert.equal(item.label, "Info");
});

test("5. diagnosticService: mapMonacoMarkersToDiagnostics maps Monaco editor markers", () => {
  const sampleMarkers = [
    {
      severity: 8, // MarkerSeverity.Error
      message: "Type 'number' is not assignable to type 'string'.",
      startLineNumber: 10,
      startColumn: 5,
    },
    {
      severity: 4, // MarkerSeverity.Warning
      message: "ESLint: 'counter' is defined but never used.",
      startLineNumber: 25,
      startColumn: 9,
    },
  ];

  const diags = mapMonacoMarkersToDiagnostics(sampleMarkers, "src/index.ts");
  assert.equal(diags.length, 2);
  assert.equal(diags[0].type, "type");
  assert.equal(diags[0].line, 10);
  assert.equal(diags[0].file, "src/index.ts");
  assert.equal(diags[1].type, "lint");
  assert.equal(diags[1].line, 25);
});

test("6. diagnosticService: summarizeDiagnostics calculates correct counts", () => {
  const items = [
    classifyDiagnostic("SyntaxError: Unexpected token"),
    classifyDiagnostic("TypeError: x is not a function"),
    classifyDiagnostic("warning: no-unused-vars in app.js:10"),
    classifyDiagnostic("warning: prefer-const in app.js:15"),
    classifyDiagnostic("Fatal error: Uncaught Exception"),
    classifyDiagnostic("Building application..."),
  ];

  const summary = summarizeDiagnostics(items);
  assert.equal(summary.syntax, 1);
  assert.equal(summary.type, 1);
  assert.equal(summary.lint, 2);
  assert.equal(summary.error, 1);
  assert.equal(summary.info, 1);
  assert.equal(summary.total, 5, "Total includes non-info issues");
});

test("7. diagnosticService: validateCodeSyntax catches bracket imbalance and invalid JSON", () => {
  const badJs = "function test() {\n  const x = [1, 2, 3;\n}";
  const jsErrors = validateCodeSyntax(badJs, "javascript", "test.js");
  assert.ok(jsErrors.length > 0);
  assert.equal(jsErrors[0].type, "syntax");
  assert.equal(jsErrors[0].label, "Syntax Error");

  const badJson = '{\n  "name": "aegis",\n  "version": \n}';
  const jsonErrors = validateCodeSyntax(badJson, "json", "config.json");
  assert.ok(jsonErrors.length > 0);
  assert.equal(jsonErrors[0].type, "syntax");
  assert.ok(jsonErrors[0].text.includes("JSON SyntaxError"));
});

test("8. diagnosticService: validateCodeSyntax catches missing Python colons", () => {
  const badPy = "def compute_metrics(x, y)\n    return x + y";
  const pyErrors = validateCodeSyntax(badPy, "python", "app.py");
  assert.equal(pyErrors.length, 1);
  assert.equal(pyErrors[0].type, "syntax");
  assert.equal(pyErrors[0].line, 1);
  assert.ok(pyErrors[0].text.includes("expected ':'"));
});

test("9. diagnosticService: validateCodeSyntax catches JSON lints (comments, duplicate keys)", () => {
  const commentedJson = '{\n  // this is a comment\n  "name": "Aegis",\n  "name": "Duplicate"\n}';
  const errors = validateCodeSyntax(commentedJson, "json", "package.json");

  const commentLint = errors.find((e) => e.text.includes("comments") && e.type === "lint");
  assert.ok(commentLint, "Detects comment in JSON as lint");
  assert.equal(commentLint.line, 2);

  const dupLint = errors.find((e) => e.text.includes("Duplicate") && e.type === "lint");
  assert.ok(dupLint, "Detects duplicate key in JSON as lint");
  assert.equal(dupLint.line, 4);
});

test("10. diagnosticService: validateCodeSyntax catches JSON syntax errors (trailing comma, single quotes)", () => {
  const trailingCommaJson = '{\n  "version": "1.0",\n}';
  const errors = validateCodeSyntax(trailingCommaJson, "json", "data.json");
  const trailingErr = errors.find((e) => e.text.includes("Trailing comma"));
  assert.ok(trailingErr, "Detects trailing comma in JSON");
  assert.equal(trailingErr.line, 2);

  const singleQuoteJson = "{\n  'title': 'Hello'\n}";
  const sqErrors = validateCodeSyntax(singleQuoteJson, "json", "data.json");
  const sqErr = sqErrors.find((e) => e.text.includes("single quotes"));
  assert.ok(sqErr, "Detects single quotes in JSON");
  assert.equal(sqErr.line, 2);
});

test("11. diagnosticService: validateCodeSyntax catches .gitignore lints (spaces, backslash, duplicates, prefix)", () => {
  const gitignoreContent = [
    "# Dependencies",
    "node_modules/",
    "  build/",                // Leading space (line 3)
    "dist/  ",                 // Trailing space (line 4)
    "windows\\temp\\*.tmp",    // Windows backslash (line 5)
    "./coverage",              // Redundant ./ (line 6)
    "out//logs",               // Consecutive slashes (line 7)
    "node_modules/",           // Duplicate pattern (line 8)
  ].join("\n");

  const errors = validateCodeSyntax(gitignoreContent, "gitignore", ".gitignore");
  assert.ok(errors.length >= 6, "Expected at least 6 lints detected");

  const leadingErr = errors.find((e) => e.text.includes("Leading whitespace"));
  assert.ok(leadingErr, "Catches leading space");
  assert.equal(leadingErr.line, 3);

  const trailingErr = errors.find((e) => e.text.includes("Trailing whitespace"));
  assert.ok(trailingErr, "Catches trailing space");
  assert.equal(trailingErr.line, 4);

  const backslashErr = errors.find((e) => e.text.includes("Backslash '\\'"));
  assert.ok(backslashErr, "Catches Windows backslash");
  assert.equal(backslashErr.line, 5);

  const prefixErr = errors.find((e) => e.text.includes("Redundant './'"));
  assert.ok(prefixErr, "Catches redundant ./ prefix");
  assert.equal(prefixErr.line, 6);

  const slashesErr = errors.find((e) => e.text.includes("Consecutive slashes"));
  assert.ok(slashesErr, "Catches consecutive slashes");
  assert.equal(slashesErr.line, 7);

  const dupErr = errors.find((e) => e.text.includes("Duplicate pattern"));
  assert.ok(dupErr, "Catches duplicate pattern");
  assert.equal(dupErr.line, 8);
});

test("12. diagnosticService: validateCodeSyntax catches .gitignore empty negation and excluded parent conflict", () => {
  const gitignoreContent = [
    "!",                        // Empty negation (line 1)
    "build/",                   // Excluded parent directory (line 2)
    "!build/output.js",         // Conflict: Git cannot re-include child of excluded dir (line 3)
  ].join("\n");

  const errors = validateCodeSyntax(gitignoreContent, "gitignore", "/project/.gitignore");
  assert.ok(errors.length >= 2);

  const emptyNegation = errors.find((e) => e.type === "syntax" && e.text.includes("Empty negation"));
  assert.ok(emptyNegation, "Catches empty negation syntax error");
  assert.equal(emptyNegation.line, 1);

  const excludedConflict = errors.find((e) => e.type === "lint" && e.text.includes("Cannot re-include"));
  assert.ok(excludedConflict, "Catches excluded parent directory negation conflict");
  assert.equal(excludedConflict.line, 3);
});

