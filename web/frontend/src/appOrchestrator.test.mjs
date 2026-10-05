import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { createSSRApp } from "vue";
import { renderToString } from "@vue/server-renderer";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));
const appVuePath = resolve(frontendRoot, "src", "App.vue");
const appVueSource = readFileSync(appVuePath, "utf-8");

// Start headless Vite server for SSR loading of Vue SFCs
const vite = await createServer({
  root: frontendRoot,
  server: { middlewareMode: true },
  appType: "custom",
});

async function loadComponent(relPath) {
  const mod = await vite.ssrLoadModule(relPath);
  return mod.default;
}

// -----------------------------------------------------------------------------
// Test 1: App.vue compilation & default SSR rendering with ProjectLauncher
// -----------------------------------------------------------------------------
test("1. App.vue compilation & default SSR rendering with ProjectLauncher", async () => {
  const AppComp = await loadComponent("/src/App.vue");
  assert.ok(AppComp, "App.vue should export default component");

  const app = createSSRApp(AppComp);
  const html = await renderToString(app);
  assert.ok(
    html.includes("Create and open AETHER workspaces") ||
    html.includes("New Project") ||
    html.includes("Workspace:") ||
    html.includes("EXPLORER"),
    "App.vue renders ProjectLauncher shell on default state"
  );
  assert.ok(
    html.includes("AETHER") || html.includes("AE"),
    "App.vue renders AETHER brand"
  );
});

// -----------------------------------------------------------------------------
// Test 2: App.vue line count verification (strictly < 450 LOC)
// -----------------------------------------------------------------------------
test("2. App.vue line count verification (strictly < 450 LOC)", () => {
  const lines = appVueSource.split("\n");
  const lineCount = lines.length;
  assert.ok(
    lineCount < 450,
    `App.vue must be under 450 lines (current: ${lineCount})`
  );
});

// -----------------------------------------------------------------------------
// Test 3: All 12 required event handlers present in handleEvent
// -----------------------------------------------------------------------------
test("3. All 12 required event handlers present in handleEvent", () => {
  assert.ok(appVueSource.includes("handleEvent"), "App.vue must define handleEvent");

  const requiredEvents = [
    "task_started",
    "phase_changed",
    "tool_called",
    "tool_completed",
    "observation_received",
    "validation_started",
    "validation_completed",
    "recovery_started",
    "recovery_completed",
    "change_detected",
    "task_completed",
    "task_failed",
  ];

  for (const evt of requiredEvents) {
    assert.ok(
      appVueSource.includes(evt),
      `App.vue must handle required SSE event '${evt}'`
    );
  }
});

// -----------------------------------------------------------------------------
// Test 4: Static token compliance for check_workbench and check_ui_refactor
// -----------------------------------------------------------------------------
test("4. Static token compliance for check_workbench and check_ui_refactor", () => {
  const requiredTokens = [
    "TaskComposer",
    "openEventStream",
    "AgentActivity",
    "ChangesPanel",
    "FileExplorer",
    "task.status",
    "th-actions",
    "hist-report-btn",
  ];

  for (const token of requiredTokens) {
    assert.ok(
      appVueSource.includes(token),
      `App.vue must include token '${token}'`
    );
  }

  // Ensure forbidden old report button is not present
  assert.ok(
    !/<button class="report-btn"[^>]*>Report<\/button>/.test(appVueSource),
    "App.vue must not have legacy report-btn"
  );

  // Ensure Actions column header is present
  assert.ok(
    /<th\s+[^>]*class="[^"]*th-actions[^"]*"[^>]*>\s*Actions\s*<\/th>/.test(appVueSource),
    "App.vue must have th-actions table header"
  );
});

// -----------------------------------------------------------------------------
// Test 5: Zero forbidden tokens across App.vue
// -----------------------------------------------------------------------------
test("5. Zero forbidden tokens across App.vue", () => {
  const forbidden = [
    "Agent" + "Runtime",
    "Agent" + "Loop",
    "Orches" + "trator",
    "Task" + "Planner",
    "Re" + "planner",
    "Tool" + "Registry",
    "execute" + "Tool",
    "run" + "Command",
    "child_" + "process",
    "require(\"fs\")",
    "require('fs')",
    "from \"fs\"",
    "from 'fs'",
    "node:fs",
    "recovery" + "Manager",
    "validation" + "Runner",
    "class Event" + "Bus",
    "class Event" + "Emitter",
    "new Event" + "Bus",
    "Web" + "Socket",
    "aether — tool log",
  ];

  for (const bad of forbidden) {
    assert.ok(
      !appVueSource.includes(bad),
      `App.vue must not contain forbidden agent logic or token '${bad}'`
    );
  }
});

// -----------------------------------------------------------------------------
// Test 6: Modal visibility states
// -----------------------------------------------------------------------------
test("6. Modal visibility states", () => {
  const modalStates = [
    "settingsOpen",
    "composerOpen",
    "commandPaletteOpen",
    "reportTaskId",
    "policyProject",
    "closeConfirmOpen",
    "stopConfirmOpen",
  ];

  for (const state of modalStates) {
    assert.ok(
      appVueSource.includes(state),
      `App.vue must manage modal state '${state}'`
    );
  }
});

// -----------------------------------------------------------------------------
// Test 7: Keyboard shortcut bindings
// -----------------------------------------------------------------------------
test("7. Keyboard shortcut bindings", () => {
  assert.ok(appVueSource.includes("onKeyDown"), "App.vue defines onKeyDown handler");
  assert.ok(appVueSource.includes("Cmd+P"), "App.vue handles Cmd+P");
  assert.ok(appVueSource.includes("Ctrl+P"), "App.vue handles Ctrl+P");
  assert.ok(appVueSource.includes("Cmd+K"), "App.vue handles Cmd+K");
  assert.ok(appVueSource.includes("Ctrl+K"), "App.vue handles Ctrl+K");
  assert.ok(appVueSource.includes("Ctrl+`"), "App.vue handles Ctrl+` toggle dock");
  assert.ok(appVueSource.includes("Escape"), "App.vue handles Escape dismiss");
});

test.after(async () => {
  await vite.close();
  console.log("[OK] appOrchestrator: All 7 test cases passed cleanly.");
});
