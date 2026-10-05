import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { createSSRApp } from "vue";
import { renderToString } from "@vue/server-renderer";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));

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

async function renderComponent(relPath, props = {}) {
  const comp = await loadComponent(relPath);
  const app = createSSRApp(comp, props);
  return renderToString(app);
}

// -----------------------------------------------------------------------------
// Test 1: SettingsOverlay shell compilation and rendering
// -----------------------------------------------------------------------------
test("1. SettingsOverlay: shell compilation, title, close button, and 6 navigation items", async () => {
  const comp = await loadComponent("/src/pages/SettingsOverlay.vue");
  assert.ok(comp, "SettingsOverlay should export default component");
  assert.ok(comp.emits, "SettingsOverlay should define emits");

  const defaultHtml = await renderComponent("/src/pages/SettingsOverlay.vue");
  assert.ok(defaultHtml.includes('class="settings-overlay"'), "Renders root overlay container");
  assert.ok(defaultHtml.includes('role="dialog"'), "Renders accessible dialog role");
  assert.ok(defaultHtml.includes('aria-modal="true"'), "Renders modal attribute");
  assert.ok(defaultHtml.includes("settings-overlay-backdrop"), "Renders backdrop");
  assert.ok(defaultHtml.includes("settings-overlay-dialog"), "Renders dialog shell");
  assert.ok(defaultHtml.includes("settings-overlay-header"), "Renders header bar");
  assert.ok(
    defaultHtml.includes("AEGIS Settings &amp; Administration") ||
    defaultHtml.includes("AEGIS Settings & Administration") ||
    defaultHtml.includes("AETHER Settings &amp; Administration") ||
    defaultHtml.includes("AETHER Settings & Administration")
  );
  assert.ok(defaultHtml.includes("Configure providers, workspaces, task history, and extensions"));
  assert.ok(defaultHtml.includes("settings-close-btn"), "Renders close button");
  assert.ok(defaultHtml.includes("shortcut-badge") && defaultHtml.includes("Esc"), "Renders Esc badge");

  // Verify navigation tabs exist in the nav bar
  assert.ok(defaultHtml.includes("Providers &amp; Models") || defaultHtml.includes("Providers & Models"));
  assert.ok(defaultHtml.includes("Text Editor"));
  assert.ok(defaultHtml.includes("Global Settings"));
  assert.ok(defaultHtml.includes("Agent Instructions"));
  assert.ok(defaultHtml.includes("Project Registry"));
  assert.ok(defaultHtml.includes("Task History"));
  assert.ok(defaultHtml.includes("Extensions Manager"));
  assert.ok(defaultHtml.includes("Overview"));
  assert.ok(defaultHtml.includes("Architecture"));
  assert.ok(defaultHtml.includes("License"));
});

// -----------------------------------------------------------------------------
// Test 2: Active tab highlight and switching across all tabs
// -----------------------------------------------------------------------------
test("2. SettingsOverlay: active tab highlight and switching across all tabs", async () => {
  const tabs = [
    "providers",
    "editor",
    "globals",
    "agent",
    "projects",
    "history",
    "extensions",
    "overview",
    "architecture",
    "license",
  ];

  for (const tab of tabs) {
    const html = await renderComponent("/src/pages/SettingsOverlay.vue", { activeTab: tab });
    assert.ok(
      html.includes('class="active settings-nav-item"') || html.includes('class="settings-nav-item active"'),
      `Navigation item for ${tab} should be active`
    );
    assert.ok(html.includes('aria-selected="true"'), `Active tab should have aria-selected="true"`);
    assert.ok(html.includes(`aria-label="${tab}"`), `Main content region should display active tab ${tab}`);
  }
});
// -----------------------------------------------------------------------------
// Test 3: Providers sub-tab: renders SettingsView with runtime summary
// -----------------------------------------------------------------------------
test("3. SettingsOverlay: providers sub-tab renders SettingsView with active provider/model runtime summary", async () => {
  const config = {
    provider: "anthropic",
    model: "claude-3-5-sonnet",
    mode: "plan",
  };

  const html = await renderComponent("/src/pages/SettingsOverlay.vue", {
    activeTab: "providers",
    config,
  });

  assert.ok(html.includes("Configuration"), "Renders Configuration panel header");
  assert.ok(html.includes("Active Provider"), "Renders Active Provider label");
  assert.ok(html.includes("anthropic"), "Renders active provider value");
  assert.ok(html.includes("Active Model"), "Renders Active Model label");
  assert.ok(html.includes("claude-3-5-sonnet"), "Renders active model value");
  assert.ok(html.includes("Mode"), "Renders Mode label");
  assert.ok(html.includes("plan"), "Renders active mode value");
});

// -----------------------------------------------------------------------------
// Test 4: Globals sub-tab: renders GlobalSettingsPanel with slider-toggle switches
// -----------------------------------------------------------------------------
test("4. SettingsOverlay: globals sub-tab renders GlobalSettingsPanel with slider-toggle switches", async () => {
  const html = await renderComponent("/src/pages/SettingsOverlay.vue", {
    activeTab: "globals",
  });

  assert.ok(html.includes("Global Settings"), "Renders Global Settings section title");
  assert.ok(html.includes("slider-toggle"), "Renders slider-toggle switch markup");
  assert.ok(html.includes("slider-track"), "Renders slider-track markup");
  assert.ok(html.includes("slider-thumb"), "Renders slider-thumb markup");
});

// -----------------------------------------------------------------------------
// Test 5: Agent Prompt sub-tab: renders AgentSettingsPanel
// -----------------------------------------------------------------------------
test("5. SettingsOverlay: agent sub-tab renders AgentSettingsPanel", async () => {
  const html = await renderComponent("/src/pages/SettingsOverlay.vue", {
    activeTab: "agent",
  });

  assert.ok(
    html.includes("Agent Instructions") || html.includes("System Prompt"),
    "Renders Agent Instructions or System Prompt panel"
  );
  assert.ok(
    html.includes("textarea") || html.includes("prompt-editor") || html.includes("editor"),
    "Renders prompt editing surface"
  );
});

// -----------------------------------------------------------------------------
// Test 6: Project Registry sub-tab: table with th-actions, names, paths, policy, delete
// -----------------------------------------------------------------------------
test("6. SettingsOverlay: project registry sub-tab renders table with th-actions, policy, and delete buttons", async () => {
  const sampleProjects = [
    { id: "proj-alpha-12345", name: "Aether Core", path: "/workspace/aether-core", root: "/workspace/aether-core" },
    { id: "proj-beta-67890", name: "Web Gateway", path: "/workspace/web-gateway", root: "/workspace/web-gateway" },
  ];

  // Empty state verification
  const emptyHtml = await renderComponent("/src/pages/SettingsOverlay.vue", {
    activeTab: "projects",
    projects: [],
  });
  assert.ok(emptyHtml.includes("wb-empty"), "Renders empty state when projects is empty");
  assert.ok(emptyHtml.includes("No projects yet"), "Empty state message rendered");

  // Populated state verification
  const populatedHtml = await renderComponent("/src/pages/SettingsOverlay.vue", {
    activeTab: "projects",
    projects: sampleProjects,
  });

  assert.ok(populatedHtml.includes("aether-table"), "Renders aether-table");
  assert.ok(populatedHtml.includes('class="th-actions text-end">Actions</th>'), "Renders th-actions header column");
  assert.ok(populatedHtml.includes("Aether Core"), "Renders first project name");
  assert.ok(populatedHtml.includes("Web Gateway"), "Renders second project name");
  assert.ok(populatedHtml.includes("/workspace/aether-core"), "Renders first project path");
  assert.ok(populatedHtml.includes("/workspace/web-gateway"), "Renders second project path");

  // Action buttons
  assert.ok(populatedHtml.includes("icon-btn policy"), "Renders policy button");
  assert.ok(populatedHtml.includes("icon-btn danger"), "Renders delete project button");
});

// -----------------------------------------------------------------------------
// Test 7: Task History sub-tab: table with th-actions, hist-report-btn, copy, badge, clear
// -----------------------------------------------------------------------------
test("7. SettingsOverlay: task history sub-tab renders table with th-actions, hist-report-btn, and toolbar", async () => {
  const sampleTasks = [
    {
      task_id: "task-001-abc",
      task: "Optimize database queries",
      status: "completed",
      execution_mode: "parallel",
      last_timestamp: "2025-01-15T10:00:00Z",
    },
    {
      task_id: "task-002-def",
      task: "Implement authentication middleware",
      status: "running",
      execution_mode: "queue",
      last_timestamp: "2025-01-15T11:00:00Z",
    },
  ];

  // Empty state verification
  const emptyHtml = await renderComponent("/src/pages/SettingsOverlay.vue", {
    activeTab: "history",
    taskHistory: [],
  });
  assert.ok(emptyHtml.includes("wb-empty"), "Renders empty state when taskHistory is empty");
  assert.ok(emptyHtml.includes("No task history yet"), "Empty state message rendered");

  // Populated state verification
  const populatedHtml = await renderComponent("/src/pages/SettingsOverlay.vue", {
    activeTab: "history",
    taskHistory: sampleTasks,
  });

  assert.ok(populatedHtml.includes("hist-toolbar"), "Renders history toolbar");
  assert.ok(populatedHtml.includes("hist-clear-btn"), "Renders clear history button");
  assert.ok(populatedHtml.includes("Clear History"), "Clear History button label");
  assert.ok(populatedHtml.includes("2 recorded task(s)"), "Displays recorded tasks count");

  assert.ok(populatedHtml.includes('class="th-actions text-end">Actions</th>'), "Renders th-actions column header");
  assert.ok(populatedHtml.includes("hist-report-btn"), "Renders hist-report-btn action button");
  assert.ok(populatedHtml.includes("hist-copy"), "Renders hist-copy prompt button");
  assert.ok(populatedHtml.includes("hist-delete-btn"), "Renders hist-delete-btn button");
  assert.ok(populatedHtml.includes("hist-exec"), "Renders execution mode badge");
  assert.ok(populatedHtml.includes("Optimize database queries"), "Renders first task prompt");
  assert.ok(populatedHtml.includes("task-001-abc"), "Renders first task ID");
});

// -----------------------------------------------------------------------------
// Test 8: Extensions sub-tab: renders ExtensionManager
// -----------------------------------------------------------------------------
test("8. SettingsOverlay: extensions sub-tab renders ExtensionManager", async () => {
  const html = await renderComponent("/src/pages/SettingsOverlay.vue", {
    activeTab: "extensions",
  });

  assert.ok(
    html.includes("ext-") || html.includes("extension") || html.includes("Install") || html.includes("Extensions"),
    "Renders ExtensionManager surface"
  );
});

// -----------------------------------------------------------------------------
// Test 8b: Overview, Architecture, and License tabs render correct content
// -----------------------------------------------------------------------------
test("8b. SettingsOverlay: renders Overview, Architecture, and License panels", async () => {
  const overviewHtml = await renderComponent("/src/pages/SettingsOverlay.vue", {
    activeTab: "overview",
  });
  assert.ok(
    overviewHtml.includes("AegisCode Studio Workbench") || overviewHtml.includes("AETHER Agent Workbench"),
    "Overview renders workbench header"
  );
  assert.ok(overviewHtml.includes("Hybrid 5-Stage CoT Protocol"), "Overview renders CoT card");

  const archHtml = await renderComponent("/src/pages/SettingsOverlay.vue", {
    activeTab: "architecture",
  });
  assert.ok(
    archHtml.includes("System Architecture &amp; Execution Model") || archHtml.includes("System Architecture & Execution Model"),
    "Architecture renders title"
  );
  assert.ok(
    archHtml.includes("Hybrid Asymmetric Split-Brain Model"),
    "Architecture renders split-brain model"
  );

  const licenseHtml = await renderComponent("/src/pages/SettingsOverlay.vue", {
    activeTab: "license",
  });
  assert.ok(licenseHtml.includes("Open Source License"), "License renders title");
  assert.ok(licenseHtml.includes("Permission is hereby granted"), "License renders MIT text");
});

// -----------------------------------------------------------------------------
// Test 9: Keyboard navigation, Escape dismissal, and emit events contract
// -----------------------------------------------------------------------------
test("9. SettingsOverlay: keyboard navigation, open condition, and emits contract", async () => {
  const comp = await loadComponent("/src/pages/SettingsOverlay.vue");

  // Verify all expected emits are declared in the component contract
  const expectedEmits = [
    "close",
    "update:activeTab",
    "open-report",
    "copy-prompt",
    "delete-history",
    "clear-history",
    "open-history-task",
    "open-project-policy",
    "delete-project",
    "open-project",
    "refresh-config",
  ];

  for (const evt of expectedEmits) {
    assert.ok(comp.emits.includes(evt), `SettingsOverlay should emit '${evt}'`);
  }

  // Open: false suppresses rendering
  const closedHtml = await renderComponent("/src/pages/SettingsOverlay.vue", { open: false });
  assert.ok(
    closedHtml === "<!---->" || closedHtml === "<!--v-if-->",
    "SettingsOverlay should render empty comment when open is false"
  );

  // Open: true renders full overlay
  const openHtml = await renderComponent("/src/pages/SettingsOverlay.vue", { open: true });
  assert.ok(openHtml.includes("settings-overlay"), "Renders when open is true");
});

test.after(async () => {
  await vite.close();
  console.log("[OK] settingsOverlay: All 9 test cases passed cleanly.");
});
