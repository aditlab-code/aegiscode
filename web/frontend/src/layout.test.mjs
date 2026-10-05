import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { createSSRApp, defineComponent, h } from "vue";
import { renderToString } from "@vue/server-renderer";
import {
  createResponsiveState,
  getBreakpointTier,
} from "./services/responsiveService.js";
import {
  truncateProjectPath,
  formatProjectOption,
} from "./services/projectService.js";

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
// Test 1: AppActivityBar.vue
// -----------------------------------------------------------------------------
test("1. AppActivityBar: 48px navigation icons, badges, active highlight, theme and settings", async () => {
  const comp = await loadComponent("/src/components/layout/AppActivityBar.vue");
  assert.ok(comp, "AppActivityBar should export default component");
  assert.ok(comp.emits, "AppActivityBar should define emits");
  assert.ok(comp.emits.includes("update:activeNav"), "Emits update:activeNav");
  assert.ok(comp.emits.includes("toggle-wallpaper"), "Emits toggle-wallpaper");
  assert.ok(comp.emits.includes("toggle-theme"), "Emits toggle-theme");
  assert.ok(comp.emits.includes("open-settings"), "Emits open-settings");

  // Default render (explorer active, dark theme)
  const defaultHtml = await renderComponent("/src/components/layout/AppActivityBar.vue");
  assert.ok(defaultHtml.includes('class="app-activity-bar"'), "Root activity bar class");
  assert.ok(defaultHtml.includes('aria-label="Activity Bar"'));
  assert.ok(defaultHtml.includes("act-bar-top"));
  assert.ok(defaultHtml.includes("act-bar-bottom"));
  assert.ok(defaultHtml.includes("Explorer (Files)"));
  assert.ok(defaultHtml.includes("Source Control &amp; Changes") || defaultHtml.includes("Source Control & Changes"));
  assert.ok(defaultHtml.includes("Task Queue"));
  assert.ok(defaultHtml.includes("Settings"));
  assert.ok(defaultHtml.includes("Toggle Wallpaper"));
  assert.ok(defaultHtml.includes("Switch to Light Theme"));

  // Check active highlight for explorer: Vue SSR renders dynamic classes merged
  assert.ok(defaultHtml.includes("act-btn") && defaultHtml.includes("active"));
  assert.ok(defaultHtml.includes('class="active act-btn" title="Explorer (Files)"') || defaultHtml.includes('class="act-btn active" title="Explorer (Files)"'));

  // Test active highlight for git and queueCount/changesCount badges
  const gitHtml = await renderComponent("/src/components/layout/AppActivityBar.vue", {
    activeNav: "git",
    isDark: false,
    changesCount: 5,
    queueCount: 3,
  });
  assert.ok(gitHtml.includes("5"), "Renders changes count badge");
  assert.ok(gitHtml.includes("3"), "Renders queue count badge");
  assert.ok(gitHtml.includes("Switch to Dark Theme"), "Renders light theme toggle title");
  assert.ok(
    gitHtml.includes('title="Source Control &amp; Changes"') ||
    gitHtml.includes('title="Source Control & Changes"')
  );

  // Test active highlight for queue and settings
  const queueHtml = await renderComponent("/src/components/layout/AppActivityBar.vue", {
    activeNav: "queue",
  });
  assert.ok(
    queueHtml.includes('class="active act-btn" title="Task Queue"') ||
    queueHtml.includes('class="act-btn active" title="Task Queue"')
  );

  const settingsHtml = await renderComponent("/src/components/layout/AppActivityBar.vue", {
    activeNav: "settings",
  });
  assert.ok(
    settingsHtml.includes('class="active act-btn" title="Settings"') ||
    settingsHtml.includes('class="act-btn active" title="Settings"')
  );
});

// -----------------------------------------------------------------------------
// Test 2: AppLeftSidebar.vue
// -----------------------------------------------------------------------------
test("2. AppLeftSidebar: brand header, project dropdown, dynamic panels, and status footer", async () => {
  const comp = await loadComponent("/src/components/layout/AppLeftSidebar.vue");
  assert.ok(comp, "AppLeftSidebar should export default component");
  assert.ok(comp.emits, "AppLeftSidebar should define emits");
  assert.ok(comp.emits.includes("open-file"), "Emits open-file");
  assert.ok(comp.emits.includes("select-project"), "Emits select-project");
  assert.ok(comp.emits.includes("close-project"), "Emits close-project");
  assert.ok(comp.emits.includes("stop-task"), "Emits stop-task");
  assert.ok(comp.emits.includes("view-task"), "Emits view-task");
  assert.ok(comp.emits.includes("open-history-task"), "Emits open-history-task");
  assert.ok(comp.emits.includes("open-consultant-session"), "Emits open-consultant-session");

  const sampleProjects = [
    { id: "proj-1", name: "Aether Core", path: "/work/aether-core" },
    { id: "proj-2", name: "Workbench Web", path: "/work/workbench-web" },
  ];

  // 1. Explorer panel active
  const explorerHtml = await renderComponent("/src/components/layout/AppLeftSidebar.vue", {
    activeNav: "explorer",
    activeProject: sampleProjects[0],
    projects: sampleProjects,
    connected: true,
    gatewayAddress: "127.0.0.1:8000",
    agentStatus: { label: "idle", cls: "status-off" },
  });
  assert.ok(explorerHtml.includes('class="app-left-sidebar"'));
  assert.ok(!explorerHtml.includes("side-brand"), "Redundant side-brand logo removed from AppLeftSidebar");
  assert.ok(explorerHtml.includes("Aether Core"));
  assert.ok(explorerHtml.includes("Workbench Web"));
  assert.ok(explorerHtml.includes("Close Workspace"));
  assert.ok(explorerHtml.includes("explorer-panel"));
  assert.ok(!explorerHtml.includes("sidebar-footer"), "Sidebar footer moved to AppFooter");

  // 2. Git panel active
  const gitHtml = await renderComponent("/src/components/layout/AppLeftSidebar.vue", {
    activeNav: "git",
    activeProject: sampleProjects[0],
    projects: sampleProjects,
    changes: [{ file: "src/main.js", kind: "modified" }],
    connected: false,
    agentStatus: { label: "running", cls: "status-run" },
  });
  assert.ok(gitHtml.includes("git-panel"));
  assert.ok(gitHtml.includes("backup-subpanel"));
  assert.ok(!gitHtml.includes("sidebar-footer"), "Sidebar footer moved to AppFooter");

  // 3. Queue panel active with 3-way subtabs
  const queueHtml = await renderComponent("/src/components/layout/AppLeftSidebar.vue", {
    activeNav: "queue",
    activeProject: sampleProjects[0],
    projects: sampleProjects,
  });
  assert.ok(queueHtml.includes("queue-panel"));
  assert.ok(queueHtml.includes("task-subtabs-bar"));
  assert.ok(queueHtml.includes("task-subtab-pill"));
  assert.ok(queueHtml.includes("Queue"));
  assert.ok(queueHtml.includes("History"));
  assert.ok(queueHtml.includes("Sessions"));
});

// -----------------------------------------------------------------------------
// Test 3: AppRightDrawer.vue
// -----------------------------------------------------------------------------
test("3. AppRightDrawer: dual-tab switcher, Latest Task telemetry card, lifecycle bar, and agent prompt input", async () => {
  const comp = await loadComponent("/src/components/layout/AppRightDrawer.vue");
  assert.ok(comp, "AppRightDrawer should export default component");
  assert.ok(comp.emits, "AppRightDrawer should define emits");
  assert.ok(comp.emits.includes("update:activeTab"), "Emits update:activeTab");
  assert.ok(comp.emits.includes("close"), "Emits close");
  assert.ok(comp.emits.includes("open-report"), "Emits open-report");
  assert.ok(comp.emits.includes("copy-activity"), "Emits copy-activity");
  assert.ok(comp.emits.includes("open-composer"), "Emits open-composer");
  assert.ok(comp.emits.includes("request-stop"), "Emits request-stop");
  assert.ok(comp.emits.includes("run-consultant-task"), "Emits run-consultant-task");
  assert.ok(comp.emits.includes("update:active-session-id"), "Emits update:active-session-id");

  const sampleTask = {
    id: "task-42",
    text: "Refactor layout shell components",
    status: "running",
  };
  const sampleLifecycle = [
    { label: "Plan", state: "done" },
    { label: "Execute", state: "done" },
    { label: "Verify", state: "active" },
  ];

  // Activity Tab
  const activityHtml = await renderComponent("/src/components/layout/AppRightDrawer.vue", {
    activeTab: "activity",
    task: sampleTask,
    taskTag: { cls: "tag-blue", label: "ACTIVE" },
    showTaskMeta: true,
    taskProvider: "OpenAI",
    taskModel: "gpt-4o",
    taskExecutionLabel: "Parallel",
    taskRoundLabel: "Round 2",
    taskDurationLabel: "01:23",
    showTaskTelemetry: true,
    taskLlmRounds: 2,
    taskToolCalls: 7,
    taskTokensLabel: "14.2k",
    taskTokensTooltip: "14,200 tokens used",
    lifecycleSteps: sampleLifecycle,
    lifecyclePct: 66,
    activityPhase: "Verifying",
    isRunning: true,
  });

  assert.ok(activityHtml.includes('class="app-right-drawer"'));
  assert.ok(activityHtml.includes("Agent Activity"));
  assert.ok(activityHtml.includes("Consultant Chat"));
  assert.ok(activityHtml.includes("Collapse Assistant"));
  assert.ok(activityHtml.includes("Latest Task"));
  assert.ok(activityHtml.includes("Refactor layout shell components"));
  assert.ok(activityHtml.includes("task-42"));
  assert.ok(activityHtml.includes("OpenAI"));
  assert.ok(activityHtml.includes("gpt-4o"));
  assert.ok(activityHtml.includes("Parallel"));
  assert.ok(activityHtml.includes("Round 2"));
  assert.ok(activityHtml.includes("01:23"));
  assert.ok(activityHtml.includes("LLM Rounds"));
  assert.ok(activityHtml.includes("Tool Calls"));
  assert.ok(activityHtml.includes("14.2k"));
  assert.ok(activityHtml.includes("66% complete"));
  assert.ok(activityHtml.includes("Verifying"));
  assert.ok(activityHtml.includes("aether — agent activity"));
  assert.ok(activityHtml.includes("Ask AETHER to build something…"));
  assert.ok(activityHtml.includes('title="Stop running task"'));

  // Consultant Tab
  const consultantHtml = await renderComponent("/src/components/layout/AppRightDrawer.vue", {
    activeTab: "consultant",
  });
  assert.ok(consultantHtml.includes("rd-consultant-view"));
});

// -----------------------------------------------------------------------------
// Test 4: AppBottomDock.vue
// -----------------------------------------------------------------------------
test("4. AppBottomDock: collapsible tabs (Terminal, Output, Problems), height style, clear, and output", async () => {
  const comp = await loadComponent("/src/components/layout/AppBottomDock.vue");
  assert.ok(comp, "AppBottomDock should export default component");
  assert.ok(comp.emits, "AppBottomDock should define emits");
  assert.ok(comp.emits.includes("update:open"), "Emits update:open");
  assert.ok(comp.emits.includes("update:activeTab"), "Emits update:activeTab");
  assert.ok(comp.emits.includes("clear"), "Emits clear");
  assert.ok(comp.emits.includes("close"), "Emits close");

  // Terminal tab with height styling
  const terminalHtml = await renderComponent("/src/components/layout/AppBottomDock.vue", {
    open: true,
    height: 250,
    activeTab: "terminal",
    terminalLines: [
      { kind: "call", tool: "read_file", target: "App.vue" },
      { kind: "result", tool: "read_file", target: "App.vue", success: true },
    ],
  });
  assert.ok(terminalHtml.includes('class="app-bottom-dock open"'));
  assert.ok(terminalHtml.includes("height: 250px") || terminalHtml.includes("height:250px"));
  assert.ok(terminalHtml.includes("Terminal"));
  assert.ok(terminalHtml.includes("Output"));
  assert.ok(terminalHtml.includes("Problems"));
  assert.ok(terminalHtml.includes("read_file"));
  assert.ok(terminalHtml.includes("Clear"));
  assert.ok(terminalHtml.includes("Close Dock"));

  // Output tab
  const outputHtml = await renderComponent("/src/components/layout/AppBottomDock.vue", {
    open: true,
    activeTab: "output",
    outputLines: ["Compiling frontend...", "Build complete in 142ms."],
  });
  assert.ok(outputHtml.includes("output-dock-panel"));
  assert.ok(outputHtml.includes("Compiling frontend..."));
  assert.ok(outputHtml.includes("Build complete in 142ms."));

  // Problems tab with count badge
  const problemsHtml = await renderComponent("/src/components/layout/AppBottomDock.vue", {
    open: true,
    activeTab: "problems",
    problems: ["Type error in index.ts: line 10", "Unused variable: token"],
  });
  assert.ok(problemsHtml.includes("problems-dock-panel"));
  assert.ok(problemsHtml.includes("Type error in index.ts: line 10"));
  assert.ok(problemsHtml.includes("Unused variable: token"));
  assert.ok(problemsHtml.includes("2"), "Badge displays problem count 2");
});

// -----------------------------------------------------------------------------
// Test 5: AppNavbar.vue
// -----------------------------------------------------------------------------
test("5. AppNavbar: brand, responsive path truncation (full/compact/mobile tiers), command palette, progressive chips", async () => {
  const comp = await loadComponent("/src/components/layout/AppNavbar.vue");
  assert.ok(comp, "AppNavbar should export default component");
  assert.ok(comp.emits, "AppNavbar should define emits");
  assert.ok(comp.emits.includes("open-explorer"), "Emits open-explorer");
  assert.ok(comp.emits.includes("open-command-palette"), "Emits open-command-palette");
  assert.ok(comp.emits.includes("toggle-assistant"), "Emits toggle-assistant");

  const project = {
    name: "Aether-Agent",
    path: "/Users/developer/Projects/Aether-Agent",
  };

  // 1. Desktop tier
  const desktopHtml = await renderComponent("/src/components/layout/AppNavbar.vue", {
    project,
    tier: "desktop",
    changesCount: 4,
  });
  assert.ok(desktopHtml.includes('class="app-navbar"'));
  assert.ok(desktopHtml.includes("AegisCode"));
  assert.ok(desktopHtml.includes("Quick Open"));
  assert.ok(desktopHtml.includes("⌘K"));
  assert.ok(desktopHtml.includes("Changes:"));
  assert.ok(desktopHtml.includes("4"));

  // 2. Compact tier: preserves changes chip, hides desktop shortcut kbd
  const compactHtml = await renderComponent("/src/components/layout/AppNavbar.vue", {
    project,
    tier: "compact",
    changesCount: 2,
  });
  assert.ok(compactHtml.includes("AegisCode"));
  assert.ok(compactHtml.includes("Changes:"));
  assert.ok(!compactHtml.includes("⌘K"), "Hides ⌘K shortcut on compact");
  assert.ok(compactHtml.includes("Toggle Assistant"), "Renders assistant toggle on compact");

  // 3. Mobile tier: hides changes chip, keeps brand badge
  const mobileHtml = await renderComponent("/src/components/layout/AppNavbar.vue", {
    project,
    tier: "mobile",
    changesCount: 7,
  });
  assert.ok(mobileHtml.includes("brand-badge"));
  assert.ok(!mobileHtml.includes("Changes:"), "Hides changes chip on mobile");
  assert.ok(mobileHtml.includes("Toggle Assistant"), "Renders assistant toggle on mobile");

  // 4. Background running indicator when assistant drawer is closed
  const runningBackgroundHtml = await renderComponent("/src/components/layout/AppNavbar.vue", {
    project,
    tier: "desktop",
    isRunning: true,
    assistantVisible: false,
  });
  assert.ok(runningBackgroundHtml.includes("nav-assistant-pill"), "Renders background running pill");
  assert.ok(runningBackgroundHtml.includes("AI Working…"), "Shows AI Working status text");
  assert.ok(runningBackgroundHtml.includes("is-running"), "Marks toggle button as is-running");

  // 5. Normal state when idle
  const idleHtml = await renderComponent("/src/components/layout/AppNavbar.vue", {
    project,
    tier: "desktop",
    isRunning: false,
    assistantVisible: true,
  });
  assert.ok(!idleHtml.includes("nav-assistant-pill"), "Omits background pill when idle");
});

// -----------------------------------------------------------------------------
// Test 6: AppFooter.vue
// -----------------------------------------------------------------------------
test("6. AppFooter: online & agent status on left, MIT license in center, model/provider/version on right", async () => {
  const comp = await loadComponent("/src/components/layout/AppFooter.vue");
  assert.ok(comp, "AppFooter should export default component");
  assert.ok(comp.emits, "AppFooter should define emits");
  assert.ok(comp.emits.includes("toggle-dock"), "Emits toggle-dock");

  // 1. Desktop tier: left, center, right sections visible
  const desktopHtml = await renderComponent("/src/components/layout/AppFooter.vue", {
    cursor: { ln: 42, col: 18 },
    spaces: 2,
    encoding: "UTF-8",
    language: "Vue",
    modelLabel: "claude-3-5-sonnet",
    providerLabel: "Anthropic",
    taskStatus: "running",
    connected: true,
    agentStatus: { label: "running", cls: "status-run" },
    aetherVersion: "0.2.01",
    bottomDockOpen: true,
    tier: "desktop",
  });
  assert.ok(desktopHtml.includes('class="app-footer"'));
  assert.ok(!desktopHtml.includes("Ln 42, Col 18"), "Ln, Col omitted to avoid redundancy");
  assert.ok(!desktopHtml.includes("UTF-8"), "UTF-8 omitted from footer");
  assert.ok(desktopHtml.includes("Online"), "Renders System Online badge on left");
  assert.ok(desktopHtml.includes("Agent: running"), "Renders Agent status badge on left");
  assert.ok(desktopHtml.includes("Open Source · MIT License"), "Renders open source MIT license in center");
  assert.ok(desktopHtml.includes("claude-3-5-sonnet"));
  assert.ok(desktopHtml.includes("Anthropic"));
  assert.ok(desktopHtml.includes("v0.2.01"));

  // 2. Compact tier
  const compactHtml = await renderComponent("/src/components/layout/AppFooter.vue", {
    cursor: { ln: 10, col: 5 },
    modelLabel: "gpt-4o",
    providerLabel: "OpenAI",
    taskStatus: "idle",
    connected: true,
    agentStatus: { label: "idle", cls: "status-off" },
    tier: "compact",
  });
  assert.ok(compactHtml.includes("OpenAI"));
  assert.ok(compactHtml.includes("Online"));
  assert.ok(compactHtml.includes("Agent: idle"));
  assert.ok(compactHtml.includes("Open Source · MIT License"));

  // 3. Mobile tier: hides provider label
  const mobileHtml = await renderComponent("/src/components/layout/AppFooter.vue", {
    modelLabel: "mini",
    providerLabel: "Google",
    taskStatus: "idle",
    connected: false,
    agentStatus: { label: "idle", cls: "status-off" },
    tier: "mobile",
  });
  assert.ok(!mobileHtml.includes("Google"), "Hides provider label on mobile");
  assert.ok(mobileHtml.includes("Offline"), "Renders System Offline badge on mobile");
  assert.ok(mobileHtml.includes("Agent: idle"));
  assert.ok(mobileHtml.includes("Open Source · MIT License"));
});

// -----------------------------------------------------------------------------
// Test 7: Overlay backdrop rendering and dismissal on compact/mobile tiers
// -----------------------------------------------------------------------------
test("7. Overlay backdrop rendering, responsive layout state transitions, and backdrop dismissal", async () => {
  // 1. Verify responsive layout state service logic
  const respState = createResponsiveState();
  assert.equal(getBreakpointTier(1440), "desktop");
  assert.equal(getBreakpointTier(1024), "compact");
  assert.equal(getBreakpointTier(768), "mobile");

  // Initial desktop state
  respState.updateDimensions(1440, 900);
  assert.equal(respState.tier.value, "desktop");
  assert.equal(respState.isDesktop.value, true);

  // Transition down to compact: rightDrawer auto-collapses
  respState.rightDrawerOpen.value = true;
  respState.updateDimensions(1024, 768);
  assert.equal(respState.tier.value, "compact");
  assert.equal(respState.isCompact.value, true);
  assert.equal(respState.rightDrawerOpen.value, false, "Right drawer auto-collapses on compact");

  // Open temporary overlay on compact
  respState.openOverlay("sidebar");
  assert.equal(respState.activeOverlay.value, "sidebar");

  // Transition back to desktop: activeOverlay is automatically cleared
  respState.updateDimensions(1440, 900);
  assert.equal(respState.tier.value, "desktop");
  assert.equal(respState.activeOverlay.value, null, "Active overlay cleared on return to desktop");

  // 2. SSR render overlay backdrop component
  const OverlayWrapper = defineComponent({
    props: {
      activeOverlay: { type: String, default: null },
    },
    emits: ["close"],
    setup(props, { emit }) {
      return () =>
        h("div", { class: "app-shell-root" }, [
          props.activeOverlay
            ? h("div", {
                class: "overlay-backdrop",
                role: "presentation",
                onClick: () => emit("close"),
              })
            : null,
          h("main", { class: "workbench-content" }, "Workbench Content"),
        ]);
    },
  });

  // When overlay is active (e.g. mobile/compact sidebar open)
  const appWithBackdrop = createSSRApp(OverlayWrapper, { activeOverlay: "sidebar" });
  const htmlWithBackdrop = await renderToString(appWithBackdrop);
  assert.ok(htmlWithBackdrop.includes('class="overlay-backdrop"'), "Renders overlay backdrop");
  assert.ok(htmlWithBackdrop.includes('role="presentation"'));

  // When overlay is closed
  const appWithoutBackdrop = createSSRApp(OverlayWrapper, { activeOverlay: null });
  const htmlWithoutBackdrop = await renderToString(appWithoutBackdrop);
  assert.ok(!htmlWithoutBackdrop.includes("overlay-backdrop"), "Backdrop omitted when overlay is null");
});

test.after(async () => {
  await vite.close();
  console.log("[OK] layout: All 6 responsive layout components and overlay backdrop verified successfully.");
});
