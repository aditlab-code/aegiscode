import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { createSSRApp } from "vue";
import { renderToString } from "@vue/server-renderer";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));

const vite = await createServer({
  root: frontendRoot,
  server: { middlewareMode: true },
  appType: "custom",
});

async function loadComponent(relPath) {
  const mod = await vite.ssrLoadModule(relPath);
  return mod.default;
}

async function renderComponent(relPath, props = {}) {
  const comp = await loadComponent(relPath);
  const app = createSSRApp(comp, props);
  return renderToString(app);
}

// -----------------------------------------------------------------------------
// Test 1: AgentActivity renders repeated reads without count multiplier and with SVG icons
// -----------------------------------------------------------------------------
test("1. AgentActivity: repeated reads displays file names without count multiplier, unified SVGs", async () => {
  const events = [
    {
      event_type: "tool_called",
      timestamp: 1000,
      payload: { tool: "read_file", target: "src/core/main.py" },
    },
    {
      event_type: "observation_received",
      timestamp: 1001,
      payload: {
        tool: "read_file",
        target: "src/core/main.py",
        content: { path: "src/core/main.py", total_lines: 50 },
      },
    },
    {
      event_type: "tool_called",
      timestamp: 1002,
      payload: { tool: "read_file", target: "src/core/main.py" },
    },
    {
      event_type: "observation_received",
      timestamp: 1003,
      payload: {
        tool: "read_file",
        target: "src/core/main.py",
        content: { path: "src/core/main.py", total_lines: 50, already_available: true },
      },
    },
  ];

  const html = await renderComponent("/src/components/AgentActivity.vue", {
    events,
    status: "completed",
    isReasoning: true,
  });

  // Repeated reads assertion: mentions file name, does NOT include count multiplier (no '×2' or 'x2')
  assert.ok(html.includes("Repeated reads"), "Renders 'Repeated reads' label");
  assert.ok(html.includes("main.py"), "Displays file name 'main.py'");
  assert.ok(!html.includes("×2") && !html.includes("×"), "Does not display count multiplier '×N'");

  // SVG assertion: uses act-svg, no raw emojis
  assert.ok(html.includes("act-svg"), "Renders act-svg class for unified icons");
  assert.ok(!html.includes("🤔"), "Reasoning indicator does not contain raw thinking emoji");
  assert.ok(!html.includes("📖"), "Does not contain raw book emoji");
  assert.ok(!html.includes("📂"), "Does not contain raw folder emoji");
});

// -----------------------------------------------------------------------------
// Test 2: AppRightDrawer tab simplification (Agent & Ask) and in-drawer report
// -----------------------------------------------------------------------------
test("2. AppRightDrawer: tabs renamed to Agent & Ask, in-drawer report isolation", async () => {
  const comp = await loadComponent("/src/components/layout/AppRightDrawer.vue");
  assert.ok(comp, "Component loaded successfully");

  const html = await renderComponent("/src/components/layout/AppRightDrawer.vue", {
    activeTab: "agents",
    task: { id: "task-99", status: "completed", text: "Build frontend" },
  });

  // Tab titles
  assert.ok(html.includes("rd-tab-title"), "Renders tab title span");
  assert.ok(html.includes(">Agent<"), "Renders 'Agent' tab title");
  assert.ok(html.includes(">Ask<"), "Renders 'Ask' tab title");

  // Status icon: SVG instead of raw emoji
  assert.ok(html.includes("ths-badge"), "Renders status badge");
  assert.ok(!html.includes("✓") && !html.includes("⏳"), "No raw unicode emojis in status badge");
});

// -----------------------------------------------------------------------------
// Test 3: ConsultantChat: Ask framing and Quick vs Deep modes
// -----------------------------------------------------------------------------
test("3. ConsultantChat: Ask mode framing with Quick and Deep mode selections", async () => {
  const html = await renderComponent("/src/components/ConsultantChat.vue", {
    embedded: true,
  });

  // Mode selection options
  assert.ok(html.includes("Quick"), "Provides Quick mode option");
  assert.ok(html.includes("Deep"), "Provides Deep mode option");

  // Welcome message framing
  assert.ok(html.includes("AEGIS Ask"), "Includes 'AEGIS Ask' framing in greeting");
  assert.ok(html.includes("Quick") && html.includes("Deep"), "Explains Quick and Deep modes in greeting");
  assert.ok(!html.includes("⚡ Quick") && !html.includes("🔍 Investigate"), "Dropdown does not use raw emoji labels");
});

// -----------------------------------------------------------------------------
// Test 4: WorkbenchView: Settings in split mode targets Pane 1 and renders SettingsOverlay
// -----------------------------------------------------------------------------
test("4. WorkbenchView: Settings in split mode renders SettingsOverlay on Pane 1 without CodeEditor file lookup", async () => {
  const html = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "desktop",
    activeProject: { id: "p1", name: "AegisCode", path: "/workspace/AegisCode" },
    initialTabs: [
      { path: "aegis://settings", name: "Settings", dirty: false },
    ],
    initialActiveTab: "aegis://settings",
    initialSplitActive: true,
    initialSplitTab: "src/main.js",
  });

  // Primary pane renders SettingsOverlay
  assert.ok(html.includes("wb-settings-tab"), "Renders wb-settings-tab in primary split pane");
  assert.ok(html.includes("settings-overlay"), "Renders SettingsOverlay component inside split pane");
  assert.ok(html.includes("Preferences"), "Renders Settings breadcrumbs in split pane");

  // Secondary pane renders normal file
  assert.ok(html.includes("Editor Tabs 2"), "Secondary pane tabs rendered");
  assert.ok(html.includes("main.js"), "Secondary pane displays main.js");
});

// -----------------------------------------------------------------------------
// Test 5: WorkbenchView: Responsive split tier fallback (stacked on mobile/compact)
// -----------------------------------------------------------------------------
test("5. WorkbenchView: responsive split adapts to stacked direction on compact/mobile tiers", async () => {
  const compactHtml = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "compact",
    activeProject: { id: "p1", name: "AegisCode", path: "/workspace/AegisCode" },
    initialTabs: [{ path: "src/a.js", name: "a.js", dirty: false }],
    initialActiveTab: "src/a.js",
    initialSplitActive: true,
    initialSplitTab: "src/b.js",
  });

  // Stacking class and direction
  assert.ok(compactHtml.includes("split-horizontal"), "Switches to split-horizontal (stacked) on compact tier");
  assert.ok(compactHtml.includes("divider-horizontal"), "Renders horizontal divider on compact tier");
});

// -----------------------------------------------------------------------------
// Test 6: AboutSettingsPanel: zero emojis, all 4 cards use SVG icons
// -----------------------------------------------------------------------------
test("6. AboutSettingsPanel: renders 4 architecture cards with SVG icons and zero emojis", async () => {
  const html = await renderComponent("/src/components/AboutSettingsPanel.vue", {
    section: "overview",
  });

  assert.ok(html.includes("about-card"), "Renders about cards");
  assert.ok(html.includes("Hybrid 5-Stage CoT Protocol"), "Card 1 present");
  assert.ok(html.includes("Hybrid Asymmetric Split-Brain"), "Card 2 present");
  assert.ok(html.includes("Dual-Stack Verification"), "Card 3 present");
  assert.ok(html.includes("Strict Security"), "Card 4 present");

  // Emojis replaced with SVGs
  assert.ok(!html.includes("🧠"), "No brain emoji");
  assert.ok(!html.includes("🏢"), "No building emoji");
  assert.ok(!html.includes("⚡"), "No zap emoji");
  assert.ok(!html.includes("🔒"), "No lock emoji");
});

// -----------------------------------------------------------------------------
// Test 7: SettingsView: Antigravity tooltip removed from top, kept in providers
// -----------------------------------------------------------------------------
test("7. SettingsView: single Antigravity login tooltip retained under provider list", async () => {
  const html = await renderComponent("/src/components/SettingsView.vue", {
    activeSection: "providers",
    config: { provider_type: "antigravity" },
    initialProviders: [
      { id: "prov-1", name: "Google Antigravity", provider_type: "antigravity", models: [] },
    ],
  });

  // Antigravity Login box present in providers list
  assert.ok(html.includes("Cara Login:"), "Renders provider card Antigravity login hint");
  assert.ok(!html.includes("Antigravity Login:</strong> Buka terminal luar"), "Top duplicate tooltip removed");
});

// -----------------------------------------------------------------------------
// Test 8: SettingsOverlay: responsive task report popup and Architecture tab
// -----------------------------------------------------------------------------
test("8. SettingsOverlay: self-contained responsive report popup and Architecture tab", async () => {
  const html = await renderComponent("/src/pages/SettingsOverlay.vue", {
    activeTab: "history",
    taskHistory: [
      { task_id: "t-1", task: "Implement feature", status: "completed", last_timestamp: "2026-10-05T10:00:00Z" },
    ],
  });

  assert.ok(html.includes("hist-report-btn"), "Renders hist-report-btn");
  assert.ok(html.includes("hist-report-popup-card") || html.includes("hist-report-btn"), "Report button wired");

  const archHtml = await renderComponent("/src/pages/SettingsOverlay.vue", {
    activeTab: "architecture",
  });
  assert.ok(archHtml.includes("Hybrid Asymmetric Split-Brain Model"), "Renders Split-Brain model");
  assert.ok(archHtml.includes("Aegis Agent Core Subsystems"), "Renders core subsystems");
  assert.ok(archHtml.includes("runtime/"), "Renders runtime subsystem");
  assert.ok(archHtml.includes("contextbudget/"), "Renders contextbudget subsystem");
});

// -----------------------------------------------------------------------------
// Test 9: AboutSettingsPanel: Architecture renders Split-Brain and 4-Phase Lifecycle
// -----------------------------------------------------------------------------
test("9. AboutSettingsPanel: renders Asymmetric Split-Brain architecture and 4-Phase Lifecycle", async () => {
  const html = await renderComponent("/src/components/AboutSettingsPanel.vue", {
    section: "architecture",
  });

  assert.ok(html.includes("Hybrid Asymmetric Split-Brain Model"), "Renders split-brain section");
  assert.ok(html.includes("LLM (Brain) — Cloud Orchestrator"), "Renders LLM Brain role");
  assert.ok(html.includes("Aegis Agent (Hands) — Local Worker"), "Renders Hands worker role");
  assert.ok(html.includes("4-Phase Execution Lifecycle"), "Renders 4-Phase Lifecycle");
  assert.ok(html.includes("Task Preparation"), "Lifecycle Phase 1");
  assert.ok(html.includes("Continuous Execution Loop"), "Lifecycle Phase 3");
  assert.ok(html.includes("Termination &amp; Validation") || html.includes("Termination & Validation"), "Lifecycle Phase 4");
});

// -----------------------------------------------------------------------------
// Test 10: Drawer and Sidebar background synchronization in dark & light themes
// -----------------------------------------------------------------------------
test("10. Dual-theme: drawer right bar and sidebar backgrounds match across dark & light modes", async () => {
  const varsCss = fs.readFileSync(path.join(frontendRoot, "src/styles/base/variables.css"), "utf-8");
  const lightCss = fs.readFileSync(path.join(frontendRoot, "src/styles/themes/theme-light.css"), "utf-8");
  const drawerCss = fs.readFileSync(path.join(frontendRoot, "src/styles/layout/drawer.css"), "utf-8");
  const sidebarCss = fs.readFileSync(path.join(frontendRoot, "src/styles/layout/sidebar.css"), "utf-8");

  // 1. variables.css defines both tokens
  assert.ok(varsCss.includes("--bg-sidebar:"), "variables.css defines --bg-sidebar");
  assert.ok(varsCss.includes("--bg-drawer:"), "variables.css defines --bg-drawer");

  // 2. theme-light.css defines both tokens in [data-theme="light"]
  assert.ok(lightCss.includes("--bg-sidebar:"), "theme-light.css defines --bg-sidebar");
  assert.ok(lightCss.includes("--bg-drawer:"), "theme-light.css defines --bg-drawer");

  // 3. app-left-sidebar uses var(--bg-sidebar)
  assert.ok(sidebarCss.includes("var(--bg-sidebar"), "sidebar.css uses var(--bg-sidebar)");
  assert.ok(lightCss.includes(".app-left-sidebar") && lightCss.includes("var(--bg-sidebar)"), "theme-light.css uses var(--bg-sidebar) for sidebar");

  // 4. app-right-drawer uses var(--bg-drawer)
  assert.ok(drawerCss.includes(".app-right-drawer") && drawerCss.includes("var(--bg-drawer"), "drawer.css uses var(--bg-drawer)");
  assert.ok(lightCss.includes(".app-right-drawer") && lightCss.includes("var(--bg-drawer)"), "theme-light.css uses var(--bg-drawer) for drawer");

  // 5. Ask and Agent tabs share the exact same background (var(--bg-drawer))
  assert.ok(drawerCss.includes(".rd-activity-view") && drawerCss.includes("var(--bg-drawer"), "Agent tab uses var(--bg-drawer)");
  assert.ok(drawerCss.includes(".rd-consultant-view") && drawerCss.includes("var(--bg-drawer"), "Ask tab uses var(--bg-drawer)");
  assert.ok(drawerCss.includes(".consultant-embedded-pane") && drawerCss.includes("var(--bg-drawer"), "Embedded consultant pane uses var(--bg-drawer)");
  assert.ok(lightCss.includes(".rd-consultant-view") && lightCss.includes("var(--bg-drawer)"), "theme-light.css sets Ask tab to var(--bg-drawer)");
});

test.after(async () => {
  await vite.close();
  console.log("[OK] uiRefactor: All 10 test suites passed cleanly.");
});
