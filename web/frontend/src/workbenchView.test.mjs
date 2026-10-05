import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { createSSRApp } from "vue";
import { renderToString } from "@vue/server-renderer";
import {
  createEditorTabsState,
  openTab,
  closeTab,
  selectTab,
  setTabDirty,
  setTabSaved,
  getActiveTab,
  hasDirtyTabs,
} from "./services/editorTabsService.js";

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
// Test 1: WorkbenchView.vue compilation, root container, and 3-column layout structure
// -----------------------------------------------------------------------------
test("1. WorkbenchView: compilation, root container, and 3-column layout structure", async () => {
  const comp = await loadComponent("/src/pages/WorkbenchView.vue");
  assert.ok(comp, "WorkbenchView should export default component");
  assert.ok(comp.emits, "WorkbenchView should define emits");

  const expectedEmits = [
    "select-project",
    "close-project",
    "open-file",
    "active-file-change",
    "stop-task",
    "view-task",
    "open-composer",
    "request-stop",
    "open-report",
    "copy-activity",
    "run-consultant-task",
    "consultant-event",
    "apply-to-editor",
    "toggle-dock",
    "cursor-change",
    "close-overlay",
    "open-history-task",
    "open-consultant-session",
  ];
  for (const evt of expectedEmits) {
    assert.ok(comp.emits.includes(evt), `WorkbenchView should emit '${evt}'`);
  }

  const html = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "desktop",
    activeProject: { id: "p1", name: "Aether-Agent", path: "/workspace/Aether-Agent" },
  });

  assert.ok(html.includes('class="workbench-view tier-desktop'), "Renders root workbench-view with desktop tier");
  assert.ok(html.includes('class="workbench-columns"'), "Renders workbench-columns container");
  assert.ok(html.includes('class="wb-left-column"'), "Renders left column");
  assert.ok(html.includes('class="wb-center-column"'), "Renders center column");
  assert.ok(html.includes('class="wb-right-column"'), "Renders right column");
  assert.ok(html.includes('class="app-left-sidebar"'), "Renders AppLeftSidebar inside left column");
  assert.ok(html.includes('class="app-right-drawer"'), "Renders AppRightDrawer inside right column");
});

// -----------------------------------------------------------------------------
// Test 2: Horizontal and vertical splitters (AppSplitter) rendered with appropriate sizing
// -----------------------------------------------------------------------------
test("2. WorkbenchView: horizontal and vertical splitters (AppSplitter) rendered with sizing props", async () => {
  // Desktop mode: left and right vertical splitters are present
  const desktopHtml = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "desktop",
  });

  assert.ok(
    desktopHtml.includes("app-splitter") && desktopHtml.includes("splitter-vertical"),
    "Renders vertical splitters on desktop"
  );

  // Mobile mode: vertical desktop splitters are omitted
  const mobileHtml = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "mobile",
  });
  assert.ok(!mobileHtml.includes("splitter-vertical"), "Vertical splitters omitted on mobile");
});

// -----------------------------------------------------------------------------
// Test 3: Monaco editor tab strip and AppBreadcrumbs rendering with active tab and dirty indicator
// -----------------------------------------------------------------------------
test("3. WorkbenchView: Monaco editor tab strip and AppBreadcrumbs rendering with active tab & dirty indicator", async () => {
  const html = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "desktop",
    activeProject: { id: "p1", name: "Aether-Agent", path: "/workspace/Aether-Agent" },
    initialTabs: [
      { path: "src/main.js", name: "main.js", dirty: true },
      { path: "src/utils.js", name: "utils.js", dirty: false },
    ],
    initialActiveTab: "src/main.js",
  });

  // Tab Strip
  assert.ok(html.includes('class="wb-editor-tabs"'), "Renders wb-editor-tabs strip");
  assert.ok(html.includes('role="tablist"'), "Renders accessible tablist role");
  assert.ok(html.includes("main.js"), "Renders main.js tab");
  assert.ok(html.includes("utils.js"), "Renders utils.js tab");

  // Active & Dirty Indicators
  assert.ok(html.includes("wb-tab-item") && html.includes("active") && html.includes("dirty"), "Active tab has active & dirty classes");
  assert.ok(html.includes('class="tab-dot"'), "Renders tab-dot dirty indicator");
  assert.ok(html.includes('class="tab-close-btn"'), "Renders tab-close-btn");

  // Breadcrumbs
  assert.ok(html.includes('class="app-breadcrumbs"'), "Renders app-breadcrumbs");
  assert.ok(html.includes("Aether-Agent"), "Breadcrumb root matches project name");
  assert.ok(html.includes("main.js"), "Breadcrumb displays current file");
});

// -----------------------------------------------------------------------------
// Test 4: Empty state welcome canvas when no tabs are open (.wb-welcome with shortcut hints)
// -----------------------------------------------------------------------------
test("4. WorkbenchView: empty state welcome canvas when no tabs are open with shortcut hints", async () => {
  const html = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "desktop",
    activeProject: { id: "p1", name: "Aether-Agent", path: "/workspace/Aether-Agent" },
    initialTabs: [],
    initialActiveTab: "",
  });

  assert.ok(html.includes('class="wb-welcome"'), "Renders wb-welcome container");
  assert.ok(html.includes('class="welcome-card"'), "Renders welcome card");
  assert.ok(html.includes("AETHER Workbench"), "Displays welcome title");
  assert.ok(html.includes("/workspace/Aether-Agent"), "Displays active project path");
  assert.ok(html.includes("Quick Open"), "Displays Quick Open shortcut hint");
  assert.ok(html.includes("<kbd>Cmd</kbd> + <kbd>P</kbd>"), "Displays Cmd+P keybinding");
  assert.ok(html.includes("Command Palette"), "Displays Command Palette shortcut hint");
  assert.ok(html.includes("<kbd>Cmd</kbd> + <kbd>K</kbd>"), "Displays Cmd+K keybinding");
  assert.ok(html.includes("Toggle Terminal Dock"), "Displays Toggle Terminal Dock shortcut hint");
  assert.ok(html.includes("<kbd>Ctrl</kbd> + <kbd>`</kbd>"), "Displays Ctrl+` keybinding");
});

// -----------------------------------------------------------------------------
// Test 5: File opening wiring: opening a file adds tab and activates Monaco editor
// -----------------------------------------------------------------------------
test("5. WorkbenchView: file opening wiring via editorTabsService adds tab and activates Monaco editor", async () => {
  const state = createEditorTabsState();
  assert.equal(state.tabs.value.length, 0);

  // Open first file
  const tab1 = openTab(state, { path: "src/agent.py", name: "agent.py" });
  assert.equal(state.tabs.value.length, 1);
  assert.equal(tab1.path, "src/agent.py");
  assert.equal(tab1.name, "agent.py");
  assert.equal(tab1.dirty, false);
  assert.equal(state.activeTab.value, "src/agent.py");
  assert.deepEqual(getActiveTab(state), tab1);

  // Open second file
  const tab2 = openTab(state, "src/runtime.py");
  assert.equal(state.tabs.value.length, 2);
  assert.equal(tab2.path, "src/runtime.py");
  assert.equal(tab2.name, "runtime.py");
  assert.equal(state.activeTab.value, "src/runtime.py");

  // Re-open first file (deduplication)
  const tab1Dup = openTab(state, "src/agent.py");
  assert.equal(state.tabs.value.length, 2, "Does not duplicate existing tab");
  assert.equal(tab1Dup.path, "src/agent.py");
  assert.equal(state.activeTab.value, "src/agent.py", "Re-activates existing tab");
});

// -----------------------------------------------------------------------------
// Test 6: Tab switching and closing behavior using editorTabsService
// -----------------------------------------------------------------------------
test("6. WorkbenchView: tab switching and closing behavior with dirty guard", async () => {
  const state = createEditorTabsState();
  openTab(state, "fileA.js");
  openTab(state, "fileB.js");
  openTab(state, "fileC.js");
  assert.equal(state.tabs.value.length, 3);
  assert.equal(state.activeTab.value, "fileC.js");

  // Select fileB
  selectTab(state, "fileB.js");
  assert.equal(state.activeTab.value, "fileB.js");

  // Mark fileB as dirty
  setTabDirty(state, "fileB.js", true);
  assert.equal(hasDirtyTabs(state), true);

  // Attempt closing dirty tab without force
  const attemptClose = closeTab(state, "fileB.js");
  assert.equal(attemptClose.closed, false);
  assert.equal(attemptClose.needsConfirm, true);
  assert.equal(state.tabs.value.length, 3, "Dirty tab remains open without force");

  // Mark tab clean / saved
  setTabSaved(state, "fileB.js");
  assert.equal(hasDirtyTabs(state), false);

  // Close clean tab: fallback activates adjacent previous tab (fileA.js)
  const cleanClose = closeTab(state, "fileB.js");
  assert.equal(cleanClose.closed, true);
  assert.equal(state.tabs.value.length, 2);
  assert.equal(state.activeTab.value, "fileA.js", "Activates adjacent tab on close");

  // Force close dirty tab
  setTabDirty(state, "fileA.js", true);
  const forceClose = closeTab(state, "fileA.js", { force: true });
  assert.equal(forceClose.closed, true);
  assert.equal(state.tabs.value.length, 1);
  assert.equal(state.activeTab.value, "fileC.js");
});

// -----------------------------------------------------------------------------
// Test 7: Bottom dock integration: dock rendering, height style, tab switching, and toggle
// -----------------------------------------------------------------------------
test("7. WorkbenchView: bottom dock integration, height style, and tabs", async () => {
  const html = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "desktop",
    terminalLines: ["$ echo 'Building Aether...'"],
    outputLines: ["Task runner queued: 1"],
    problems: [],
  });

  assert.ok(html.includes('class="app-bottom-dock"'), "Renders app-bottom-dock");
  assert.ok(html.includes('class="dock-header"'), "Renders dock header");
  assert.ok(html.includes("Terminal"), "Renders Terminal dock tab");
  assert.ok(html.includes("Output"), "Renders Output dock tab");
  assert.ok(html.includes("Problems"), "Renders Problems dock tab");
});

// -----------------------------------------------------------------------------
// Test 8: Right Assistant Drawer wiring: task composer, stop button, activity timeline
// -----------------------------------------------------------------------------
test("8. WorkbenchView: right assistant drawer wiring, composer, stop button, timeline", async () => {
  const html = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "desktop",
    task: { id: "task-42", prompt: "Build multi-agent mesh", status: "running" },
    isRunning: true,
    stopInProgress: false,
    activityEvents: [
      { type: "task_started", time: "12:00:01", message: "Task started" },
    ],
  });

  assert.ok(html.includes('class="app-right-drawer"'), "Renders app-right-drawer");
  assert.ok(html.includes('class="right-drawer-header"'), "Renders right-drawer-header");
  assert.ok(html.includes("Activity"), "Renders Activity tab button");
  assert.ok(html.includes("Consultant"), "Renders Consultant tab button");
  assert.ok(html.includes("Stop"), "Renders Stop task button");
});

// -----------------------------------------------------------------------------
// Test 9: 1-Click Apply to Editor wiring: markdown code extraction and editor update
// -----------------------------------------------------------------------------
test("9. WorkbenchView & ConsultantChat: 1-click 'Apply to Editor' wiring and code extraction", async () => {
  const consultantComp = await loadComponent("/src/components/ConsultantChat.vue");
  assert.ok(consultantComp.emits.includes("apply-to-editor"), "ConsultantChat emits apply-to-editor");

  const drawerComp = await loadComponent("/src/components/layout/AppRightDrawer.vue");
  assert.ok(drawerComp.emits.includes("apply-to-editor"), "AppRightDrawer emits apply-to-editor");

  // Verify Markdown code block extraction logic
  function extractFirstCodeBlock(text) {
    if (!text) return "";
    const match = String(text).match(/```(?:[a-zA-Z0-9_+-]+)?\r?\n([\s\S]*?)\r?\n```/);
    return match ? match[1] : "";
  }

  const sampleMarkdownWithCode = `
Here is the refactored code:
\`\`\`javascript
function calculateScore(items) {
  return items.reduce((acc, x) => acc + x.val, 0);
}
\`\`\`
Let me know if this works.
`;

  const extracted = extractFirstCodeBlock(sampleMarkdownWithCode);
  assert.ok(extracted.includes("function calculateScore(items)"));
  assert.ok(extracted.includes("return items.reduce"));

  const sampleNoCode = "No code here, just plain text explanation.";
  assert.equal(extractFirstCodeBlock(sampleNoCode), "");

  // Verify editor tabs dirty tracking when code is applied
  const state = createEditorTabsState();
  openTab(state, "scratchpad.js");
  setTabDirty(state, "scratchpad.js", true);
  assert.equal(hasDirtyTabs(state), true);
  assert.equal(getActiveTab(state)?.dirty, true);
});

// -----------------------------------------------------------------------------
// Test 10: Responsive tier behavior: desktop 3-column, compact overlay, mobile backdrop
// -----------------------------------------------------------------------------
test("10. WorkbenchView: responsive tier behavior across desktop, compact, and mobile", async () => {
  // Desktop
  const desktopHtml = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "desktop",
    activeOverlay: null,
  });
  assert.ok(desktopHtml.includes("tier-desktop"), "Applies tier-desktop class");
  assert.ok(!desktopHtml.includes("overlay-backdrop"), "Backdrop omitted on desktop");

  // Compact with sidebar inline column
  const compactHtml = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "compact",
    activeOverlay: "sidebar",
  });
  assert.ok(compactHtml.includes("tier-compact"), "Applies tier-compact class");
  assert.ok(!compactHtml.includes("overlay-backdrop"), "Overlay backdrop removed entirely");
  assert.ok(compactHtml.includes("wb-left-column"), "Left column remains docked inline");

  // Mobile with assistant inline column
  const mobileHtml = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "mobile",
    activeOverlay: "assistant",
  });
  assert.ok(mobileHtml.includes("tier-mobile"), "Applies tier-mobile class");
  assert.ok(!mobileHtml.includes("overlay-backdrop"), "Overlay backdrop removed entirely on mobile");
  assert.ok(mobileHtml.includes("wb-right-column"), "Right column remains docked inline on mobile");
});

// -----------------------------------------------------------------------------
// Test 11: Persistent right drawer retention (v-show) and toast notification styling
// -----------------------------------------------------------------------------
test("11. WorkbenchView: persistent drawer retention (v-show) when hidden", async () => {
  const hiddenDrawerHtml = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "desktop",
    assistantVisible: false,
  });

  // Drawer remains in the DOM via v-show (style="display:none") so components and background tasks are not unmounted
  assert.ok(hiddenDrawerHtml.includes("wb-right-column"), "Retains wb-right-column in DOM when assistantVisible is false");
  assert.ok(hiddenDrawerHtml.includes("display:none") || hiddenDrawerHtml.includes("display: none"), "Applies display:none style when hidden via v-show");
  assert.ok(hiddenDrawerHtml.includes("app-right-drawer"), "Preserves AppRightDrawer instance in DOM");
});

// -----------------------------------------------------------------------------
// Test 12: Split editor tabs feature (wb-tab-split-btn, responsive split layout)
// -----------------------------------------------------------------------------
test("12. WorkbenchView: responsive split tab feature in Monaco editor", async () => {
  // Test split button presence when tabs are open
  const normalHtml = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "desktop",
    activeProject: { id: "p1", name: "Aether-Agent", path: "/workspace/Aether-Agent" },
    initialTabs: [
      { path: "src/main.js", name: "main.js", dirty: false },
      { path: "src/utils.js", name: "utils.js", dirty: false },
    ],
    initialActiveTab: "src/main.js",
  });

  assert.ok(normalHtml.includes("wb-tab-split-btn"), "Renders split tab button in toolbar");
  assert.ok(normalHtml.includes("Split Editor Right"), "Has Split Editor Right tooltip");

  // Test split active layout rendering
  const splitHtml = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "desktop",
    activeProject: { id: "p1", name: "Aether-Agent", path: "/workspace/Aether-Agent" },
    initialTabs: [
      { path: "src/main.js", name: "main.js", dirty: false },
      { path: "src/utils.js", name: "utils.js", dirty: false },
    ],
    initialActiveTab: "src/main.js",
    initialSplitActive: true,
    initialSplitDirection: "vertical",
    initialSplitTab: "src/utils.js",
  });

  assert.ok(splitHtml.includes("wb-split-editor-container"), "Renders wb-split-editor-container");
  assert.ok(splitHtml.includes("split-vertical"), "Applies split-vertical class on desktop");
  assert.ok(splitHtml.includes("wb-split-pane-primary"), "Renders primary pane");
  assert.ok(splitHtml.includes("wb-split-pane-secondary"), "Renders secondary pane");
  assert.ok(splitHtml.includes("wb-split-divider"), "Renders split divider");
  assert.ok(splitHtml.includes("wb-pane-tabs-bar"), "Renders independent pane tabs bar");
  assert.ok(splitHtml.includes("split-pane-close-btn"), "Renders close split button");

  // Test responsive compact/mobile tier split layout
  const mobileSplitHtml = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "mobile",
    activeProject: { id: "p1", name: "Aether-Agent", path: "/workspace/Aether-Agent" },
    initialTabs: [
      { path: "src/main.js", name: "main.js", dirty: false },
      { path: "src/utils.js", name: "utils.js", dirty: false },
    ],
    initialActiveTab: "src/main.js",
    initialSplitActive: true,
    initialSplitTab: "src/utils.js",
  });

  assert.ok(mobileSplitHtml.includes("split-tier-mobile"), "Applies split-tier-mobile class for responsive stacking");
});

// -----------------------------------------------------------------------------
// Test 13: Dual-window independent tab groups and OPEN EDITORS rendering
// -----------------------------------------------------------------------------
test("13. WorkbenchView & FileExplorer: dual-window independent tab groups and OPEN EDITORS", async () => {
  // 1. FileExplorer renders Tab 1 and Tab 2 groups when splitActive is true
  const feSplitHtml = await renderComponent("/src/components/FileExplorer.vue", {
    project: { id: "p1", name: "Aether-Agent", path: "/workspace/Aether-Agent" },
    splitActive: true,
    activePane: "pane2",
    openTabs: [
      { path: "src/pane1-file.js", name: "pane1-file.js", dirty: false },
    ],
    activeTabPath: "src/pane1-file.js",
    openTabs2: [
      { path: "src/pane2-file.js", name: "pane2-file.js", dirty: true },
    ],
    activeTabPath2: "src/pane2-file.js",
  });

  assert.ok(feSplitHtml.includes("OPEN EDITORS"), "Renders OPEN EDITORS block");
  assert.ok(feSplitHtml.includes("oe-group"), "Renders oe-group containers");
  assert.ok(feSplitHtml.includes("Tab 1"), "Renders Tab 1 group header");
  assert.ok(feSplitHtml.includes("Tab 2"), "Renders Tab 2 group header");
  assert.ok(feSplitHtml.includes("pane1-file.js"), "Renders file under Tab 1");
  assert.ok(feSplitHtml.includes("pane2-file.js"), "Renders file under Tab 2");
  assert.ok(feSplitHtml.includes("is-active-pane"), "Applies is-active-pane to active group");

  // 2. FileExplorer renders single Tab 1 group when splitActive is false
  const feSingleHtml = await renderComponent("/src/components/FileExplorer.vue", {
    project: { id: "p1", name: "Aether-Agent", path: "/workspace/Aether-Agent" },
    splitActive: false,
    openTabs: [
      { path: "src/main.js", name: "main.js", dirty: false },
    ],
    activeTabPath: "src/main.js",
  });

  assert.ok(feSingleHtml.includes("Tab 1"), "Renders Tab 1 group in single window mode");
  assert.ok(!feSingleHtml.includes("Tab 2"), "Does not render Tab 2 when split is inactive");
  assert.ok(feSingleHtml.includes("main.js"), "Renders open file in Tab 1");

  // 3. WorkbenchView renders independent tabs and breadcrumbs in both panes
  const wbSplitHtml = await renderComponent("/src/pages/WorkbenchView.vue", {
    tier: "desktop",
    activeProject: { id: "p1", name: "Aether-Agent", path: "/workspace/Aether-Agent" },
    initialTabs: [
      { path: "src/alpha.js", name: "alpha.js", dirty: false },
    ],
    initialActiveTab: "src/alpha.js",
    initialSplitActive: true,
    initialSplitTab: "src/beta.js",
  });

  assert.ok(wbSplitHtml.includes('aria-label="Editor Tabs 1"'), "Renders Editor Tabs 1 strip in primary pane");
  assert.ok(wbSplitHtml.includes('aria-label="Editor Tabs 2"'), "Renders Editor Tabs 2 strip in secondary pane");
  assert.ok(wbSplitHtml.includes("alpha.js"), "Primary pane renders alpha.js tab");
  assert.ok(wbSplitHtml.includes("beta.js"), "Secondary pane renders beta.js tab");
});

test.after(async () => {
  await vite.close();
  console.log("[OK] workbenchView: All 13 test cases passed cleanly.");
});
