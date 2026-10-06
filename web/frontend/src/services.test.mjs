import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

import {
  THEME_KEY,
  WALLPAPER_KEY,
  THEMES,
  getStoredTheme,
  applyTheme,
  initTheme,
  getStoredWallpaper,
  applyWallpaper,
  initWallpaper,
  createThemeState,
} from "./services/themeService.js";

import {
  HISTORY_GROUPS,
  ACTIVE_STATUSES,
  TERMINAL_STATUSES,
  statusTagClass,
  normalizeExecutionMode,
  executionLabel,
  formatTs,
  taskTimeGroup,
  groupTaskHistory,
  computeTaskTelemetry,
} from "./services/taskService.js";

import {
  getProjectDisplayName,
  truncateProjectPath,
  formatProjectOption,
  sortProjects,
} from "./services/projectService.js";

import {
  createEditorTabsState,
  openTab,
  closeTab,
  selectTab,
  setTabDirty,
  setTabSaved,
  hasDirtyTabs,
  getActiveTab,
} from "./services/editorTabsService.js";

import {
  createCommandRegistry,
  getDefaultCommands,
  filterCommands,
  filterFiles,
  matchesShortcut,
  bindGlobalShortcuts,
} from "./services/commandPaletteService.js";

import {
  BREAKPOINTS,
  DEFAULT_SIZES,
  SIZE_LIMITS,
  getBreakpointTier,
  clampSize,
  createResponsiveState,
} from "./services/responsiveService.js";

// ============================================================================
// 1. themeService tests
// ============================================================================
test("1. themeService: getStoredTheme, applyTheme, toggleTheme, dataset updates, and SSR fallback", () => {
  // SSR fallback: in Node environment without window, returns fallback
  assert.equal(getStoredTheme(), THEMES.DARK);
  assert.equal(getStoredTheme(THEMES.LIGHT), THEMES.LIGHT);

  // Simulated browser environment
  const mockStorage = new Map();
  const mockDataset = {};
  globalThis.window = {
    localStorage: {
      getItem: (k) => mockStorage.get(k) || null,
      setItem: (k, v) => mockStorage.set(k, String(v)),
    },
  };
  globalThis.document = {
    documentElement: {
      dataset: mockDataset,
      setAttribute: (k, v) => {
        mockDataset[k.replace(/^data-/, "")] = v;
      },
    },
  };

  try {
    // Initial with no stored value
    assert.equal(getStoredTheme(), "dark");

    // applyTheme light
    applyTheme(THEMES.LIGHT);
    assert.equal(mockDataset.theme, "light");
    assert.equal(mockStorage.get(THEME_KEY), "light");
    assert.equal(getStoredTheme(), "light");

    // applyTheme dark
    applyTheme(THEMES.DARK);
    assert.equal(mockDataset.theme, "dark");
    assert.equal(mockStorage.get(THEME_KEY), "dark");
    assert.equal(getStoredTheme(), "dark");

    // initTheme
    mockStorage.set(THEME_KEY, "light");
    const active = initTheme();
    assert.equal(active, "light");
    assert.equal(mockDataset.theme, "light");

    // createThemeState reactivity
    const state = createThemeState();
    assert.equal(state.isDark.value, false);

    state.toggleTheme();
    assert.equal(state.isDark.value, true);
    assert.equal(mockDataset.theme, "dark");
    assert.equal(mockStorage.get(THEME_KEY), "dark");

    state.setTheme("light");
    assert.equal(state.isDark.value, false);
    assert.equal(mockDataset.theme, "light");

    // wallpaper: default, storage, and dataset testing
    assert.equal(getStoredWallpaper(), true);
    applyWallpaper(false);
    assert.equal(mockDataset.wallpaper, "disabled");
    assert.equal(mockStorage.get(WALLPAPER_KEY), "disabled");
    assert.equal(getStoredWallpaper(), false);

    applyWallpaper(true);
    assert.equal(mockDataset.wallpaper, "enabled");
    assert.equal(mockStorage.get(WALLPAPER_KEY), "enabled");
    assert.equal(getStoredWallpaper(), true);

    mockStorage.set(WALLPAPER_KEY, "disabled");
    const activeWallpaper = initWallpaper();
    assert.equal(activeWallpaper, false);
    assert.equal(mockDataset.wallpaper, "disabled");

    const wallpaperState = createThemeState();
    assert.equal(wallpaperState.isWallpaperEnabled.value, false);
    wallpaperState.toggleWallpaper();
    assert.equal(wallpaperState.isWallpaperEnabled.value, true);
    assert.equal(mockDataset.wallpaper, "enabled");
    assert.equal(mockStorage.get(WALLPAPER_KEY), "enabled");

    wallpaperState.setWallpaper(false);
    assert.equal(wallpaperState.isWallpaperEnabled.value, false);
    assert.equal(mockDataset.wallpaper, "disabled");
  } finally {
    delete globalThis.window;
    delete globalThis.document;
  }
});

// ============================================================================
// 2. taskService tests
// ============================================================================
test("2. taskService: statusTagClass, executionLabel, ISO date formatting, taskTimeGroup, and telemetry", () => {
  // statusTagClass
  assert.equal(statusTagClass("completed"), "status-on");
  assert.equal(statusTagClass("failed"), "status-err");
  for (const st of ACTIVE_STATUSES) {
    assert.equal(statusTagClass(st), "status-run", `Status ${st} should map to status-run`);
    assert.equal(statusTagClass(st.toUpperCase()), "status-run", `Uppercase ${st} should map to status-run`);
  }
  for (const term of TERMINAL_STATUSES) {
    if (term !== "completed" && term !== "failed") {
      assert.equal(statusTagClass(term), "status-off", `Status ${term} should map to status-off`);
    }
  }
  assert.equal(statusTagClass("queued"), "status-off");
  assert.equal(statusTagClass(""), "status-off");
  assert.equal(statusTagClass(null), "status-off");

  // normalizeExecutionMode & executionLabel
  assert.equal(normalizeExecutionMode("parallel"), "parallel");
  assert.equal(normalizeExecutionMode("PARALLEL"), "parallel");
  assert.equal(normalizeExecutionMode("queue"), "queue");
  assert.equal(normalizeExecutionMode(undefined), "queue");
  assert.equal(executionLabel("parallel"), "Parallel");
  assert.equal(executionLabel("Parallel"), "Parallel");
  assert.equal(executionLabel("queue"), "Queue");
  assert.equal(executionLabel(null), "Queue");

  // formatTs
  assert.equal(formatTs(null), "—");
  assert.equal(formatTs(""), "—");
  const isoStr = "2025-01-15T12:00:00.000Z";
  const formatted = formatTs(isoStr);
  assert.ok(formatted !== "—" && formatted.length > 0);
  assert.equal(formatTs("not-a-date"), "not-a-date");

  // taskTimeGroup & boundaries
  const now = new Date();
  const todayItem = { last_timestamp: now.toISOString() };
  assert.equal(taskTimeGroup(todayItem), "TODAY");
  assert.equal(taskTimeGroup(now.toISOString()), "TODAY");

  const yesterdayDate = new Date(now.getTime() - 24 * 3600 * 1000);
  const yesterdayItem = { last_timestamp: yesterdayDate.toISOString() };
  assert.equal(taskTimeGroup(yesterdayItem), "YESTERDAY");

  const oldDate = new Date("2024-01-01T00:00:00Z");
  assert.equal(taskTimeGroup({ last_timestamp: oldDate.toISOString() }), "OLDER");
  assert.equal(taskTimeGroup(null), "OLDER");
  assert.equal(taskTimeGroup("invalid"), "OLDER");

  // groupTaskHistory
  const tasks = [
    { id: "1", last_timestamp: now.toISOString() },
    { id: "2", last_timestamp: yesterdayDate.toISOString() },
    { id: "3", last_timestamp: oldDate.toISOString() },
  ];
  const grouped = groupTaskHistory(tasks);
  assert.equal(grouped.length, 3);
  assert.equal(grouped[0].label, "TODAY");
  assert.equal(grouped[0].items.length, 1);
  assert.equal(grouped[1].label, "YESTERDAY");
  assert.equal(grouped[1].items.length, 1);
  assert.equal(grouped[2].label, "OLDER");
  assert.equal(grouped[2].items.length, 1);

  // Empty groups omitted
  const onlyToday = groupTaskHistory([{ id: "1", last_timestamp: now.toISOString() }]);
  assert.equal(onlyToday.length, 1);
  assert.equal(onlyToday[0].label, "TODAY");

  // computeTaskTelemetry
  const events = [
    { event_type: "provider_request" },
    { event: "tool_called" },
    { type: "observation_received" },
    { event_type: "tool_called" },
    { event_type: "provider_request" },
    { event_type: "other_event" },
  ];
  const telemetry = computeTaskTelemetry(events);
  assert.deepEqual(telemetry, {
    rounds: 2,
    toolCalls: 2,
    observations: 1,
  });
  assert.deepEqual(computeTaskTelemetry([]), { rounds: 0, toolCalls: 0, observations: 0 });
  assert.deepEqual(computeTaskTelemetry(null), { rounds: 0, toolCalls: 0, observations: 0 });
});

// ============================================================================
// 3. projectService tests
// ============================================================================
test("3. projectService: truncateProjectPath for all tiers, home replacement, maxChars boundary, and option formatting", () => {
  // getProjectDisplayName
  assert.equal(getProjectDisplayName({ name: "Aether Engine" }), "Aether Engine");
  assert.equal(getProjectDisplayName({ title: "Fallback Title" }), "Fallback Title");
  assert.equal(getProjectDisplayName({}), "Untitled Project");
  assert.equal(getProjectDisplayName(null), "Untitled Project");

  // truncateProjectPath: empty handling
  assert.equal(truncateProjectPath(""), "");
  assert.equal(truncateProjectPath(null), "");

  // compact & mobile tiers return folder basename
  assert.equal(
    truncateProjectPath("/Users/dev/repos/Aether-Agent", { tier: "compact" }),
    "Aether-Agent"
  );
  assert.equal(
    truncateProjectPath("/home/ubuntu/apps/web-agent", { tier: "mobile" }),
    "web-agent"
  );
  assert.equal(
    truncateProjectPath("C:\\Projects\\AI\\System-Core", { tier: "compact" }),
    "System-Core"
  );

  // desktop tier: home replacement
  const macHome = "/Users/aditwicaksono/Documents/Project";
  assert.equal(truncateProjectPath(macHome, { maxChars: 50 }), "~/Documents/Project");

  const linuxHome = "/home/developer/code/aether";
  assert.equal(truncateProjectPath(linuxHome, { maxChars: 50 }), "~/code/aether");

  // desktop tier: maxChars middle truncation
  const deepPath = "/Users/adit/Development/VeryLongDirectoryStructure/NestedLevel/Aether-Agent";
  const truncated = truncateProjectPath(deepPath, { maxChars: 30, tier: "desktop" });
  assert.ok(truncated.length <= 30, `Truncated path length (${truncated.length}) exceeds 30`);
  assert.ok(truncated.includes("..."), "Must include middle ellipsis");
  assert.ok(truncated.includes("Aether-Agent"), "Must preserve basename");

  // formatProjectOption
  const opt = formatProjectOption({ id: "p1", name: "Workspace 1", path: "/data/w1" });
  assert.deepEqual(opt, { value: "p1", label: "Workspace 1", path: "/data/w1" });

  // sortProjects
  const projects = [
    { id: "p-beta", name: "Beta Project" },
    { id: "p-gamma", name: "Gamma Project" },
    { id: "p-alpha", name: "Alpha Project" },
  ];
  const sortedDefault = sortProjects(projects);
  assert.equal(sortedDefault[0].name, "Alpha Project");
  assert.equal(sortedDefault[1].name, "Beta Project");
  assert.equal(sortedDefault[2].name, "Gamma Project");

  const sortedActive = sortProjects(projects, "p-gamma");
  assert.equal(sortedActive[0].id, "p-gamma");
  assert.equal(sortedActive[1].name, "Alpha Project");
  assert.equal(sortedActive[2].name, "Beta Project");
});

// ============================================================================
// 4. editorTabsService tests
// ============================================================================
test("4. editorTabsService: tab creation, deduped open, adjacent tab fallback upon close, and dirty flag tracking", () => {
  const state = createEditorTabsState();
  assert.deepEqual(state.tabs.value, []);
  assert.equal(state.activeTab.value, "activity");
  assert.equal(getActiveTab(state), null);

  // Open first tab via string
  const tab1 = openTab(state, "src/main.js");
  assert.equal(tab1.path, "src/main.js");
  assert.equal(tab1.name, "main.js");
  assert.equal(tab1.dirty, false);
  assert.equal(state.tabs.value.length, 1);
  assert.equal(state.activeTab.value, "src/main.js");
  assert.equal(getActiveTab(state).name, "main.js");

  // Deduped open
  const tab1Again = openTab(state, { path: "src/main.js", name: "Custom Name" });
  assert.equal(state.tabs.value.length, 1);
  assert.equal(tab1Again.path, "src/main.js");

  // Open second and third tabs
  openTab(state, "src/App.vue");
  openTab(state, "src/styles.css");
  assert.equal(state.tabs.value.length, 3);
  assert.equal(state.activeTab.value, "src/styles.css");

  // selectTab
  selectTab(state, "src/App.vue");
  assert.equal(state.activeTab.value, "src/App.vue");

  // Dirty tracking
  assert.equal(hasDirtyTabs(state), false);
  setTabDirty(state, "src/App.vue", true);
  assert.equal(hasDirtyTabs(state), true);

  // Close dirty tab without force -> requires confirmation
  const dirtyAttempt = closeTab(state, "src/App.vue");
  assert.equal(dirtyAttempt.closed, false);
  assert.equal(dirtyAttempt.needsConfirm, true);
  assert.equal(state.tabs.value.length, 3);

  // Clear dirty flag and close cleanly
  setTabSaved(state, "src/App.vue");
  assert.equal(hasDirtyTabs(state), false);
  const cleanClose = closeTab(state, "src/App.vue");
  assert.equal(cleanClose.closed, true);
  assert.equal(state.tabs.value.length, 2);
  // Fallback to adjacent tab: index 1 was closed -> activates index 0 (src/main.js)
  assert.equal(state.activeTab.value, "src/main.js");

  // Force close remaining tabs
  setTabDirty(state, "src/styles.css", true);
  const forceResult = closeTab(state, "src/styles.css", { force: true });
  assert.equal(forceResult.closed, true);
  assert.equal(state.tabs.value.length, 1);

  // Close last tab -> returns to 'activity'
  closeTab(state, "src/main.js");
  assert.equal(state.tabs.value.length, 0);
  assert.equal(state.activeTab.value, "activity");
  assert.equal(getActiveTab(state), null);

  // Closing non-existent tab
  const notFound = closeTab(state, "src/nonexistent.js");
  assert.equal(notFound.closed, false);
});

// ============================================================================
// 5. commandPaletteService tests
// ============================================================================
test("5. commandPaletteService: registry operations, default IDE commands, filterCommands, filterFiles, and shortcuts", () => {
  // Registry operations
  const registry = createCommandRegistry();
  let toggleCalled = false;
  registry.registerCommand({
    id: "app.test",
    title: "Run Test",
    category: "Developer",
    shortcut: "Cmd+T",
    handler: (arg) => {
      toggleCalled = true;
      return `result:${arg}`;
    },
  });

  assert.equal(registry.getCommands().length, 1);
  assert.equal(registry.executeCommand("app.test", "ok"), "result:ok");
  assert.equal(toggleCalled, true);

  // Overwrite command
  registry.registerCommand({
    id: "app.test",
    title: "Updated Run Test",
  });
  assert.equal(registry.getCommands().length, 1);
  assert.equal(registry.getCommands()[0].title, "Updated Run Test");

  registry.unregisterCommand("app.test");
  assert.equal(registry.getCommands().length, 0);
  assert.equal(registry.executeCommand("app.test"), null);

  // Default commands
  const defaults = getDefaultCommands();
  assert.equal(defaults.length, 8);
  const ids = defaults.map((c) => c.id);
  assert.ok(ids.includes("workbench.action.quickOpen"));
  assert.ok(ids.includes("workbench.action.showCommands"));
  assert.ok(ids.includes("workbench.action.toggleTerminal"));
  assert.ok(ids.includes("workbench.action.toggleSidebar"));
  assert.ok(ids.includes("workbench.action.toggleRightAssistant"));
  assert.ok(ids.includes("workbench.action.saveFile"));
  assert.ok(ids.includes("workbench.action.toggleTheme"));
  assert.ok(ids.includes("workbench.action.toggleWallpaper"));

  // filterCommands
  const commands = [
    { id: "1", title: "View: Toggle Terminal Dock", category: "View" },
    { id: "2", title: "Files: Quick Open", category: "Files" },
    { id: "3", title: "Preferences: Toggle Theme", category: "Preferences" },
  ];
  assert.equal(filterCommands("", commands).length, 3);
  assert.equal(filterCommands("terminal", commands).length, 1);
  assert.equal(filterCommands("view", commands).length, 1);
  assert.equal(filterCommands("pref", commands).length, 1);
  assert.equal(filterCommands("nonexistent", commands).length, 0);

  // filterFiles
  const filePaths = [
    "src/main.js",
    "src/App.vue",
    "src/services/themeService.js",
    "src/services/taskService.js",
    "src/services/responsiveService.js",
  ];
  assert.equal(filterFiles("", filePaths).length, 5);
  assert.equal(filterFiles("theme", filePaths).length, 1);
  assert.equal(filterFiles("task", filePaths).length, 1);
  assert.equal(filterFiles("s/main", filePaths).length, 1); // Subsequence match

  // matchesShortcut
  assert.equal(matchesShortcut({ metaKey: true, key: "p" }, "Cmd+P"), true);
  assert.equal(matchesShortcut({ ctrlKey: true, key: "p" }, "Cmd+P"), true);
  assert.equal(matchesShortcut({ ctrlKey: true, key: "`" }, "Ctrl+`"), true);
  assert.equal(matchesShortcut({ metaKey: true, shiftKey: true, key: "p" }, "Cmd+Shift+P"), true);
  assert.equal(matchesShortcut({ metaKey: true, key: "p" }, "Cmd+Shift+P"), false);
  assert.equal(matchesShortcut({ key: "p" }, "Cmd+P"), false);
  assert.equal(matchesShortcut(null, "Cmd+P"), false);

  // bindGlobalShortcuts SSR safe fallback & mock listener
  const cleanNoop = bindGlobalShortcuts({}, null);
  assert.equal(typeof cleanNoop, "function");
  cleanNoop();

  const listeners = [];
  const mockTarget = {
    addEventListener: (evt, fn) => listeners.push({ evt, fn }),
    removeEventListener: (evt, fn) => {
      const idx = listeners.findIndex((l) => l.evt === evt && l.fn === fn);
      if (idx !== -1) listeners.splice(idx, 1);
    },
  };

  let triggered = false;
  const unbind = bindGlobalShortcuts(
    {
      "Cmd+P": () => {
        triggered = true;
      },
    },
    mockTarget
  );
  assert.equal(listeners.length, 1);

  // Dispatch keydown
  listeners[0].fn({ metaKey: true, key: "p" });
  assert.equal(triggered, true);

  unbind();
  assert.equal(listeners.length, 0);
});

// ============================================================================
// 6. responsiveService tests
// ============================================================================
test("6. responsiveService: getBreakpointTier, responsive state mutations, overlay management, and auto-collapse", () => {
  // getBreakpointTier
  assert.equal(getBreakpointTier(1920), "desktop");
  assert.equal(getBreakpointTier(1281), "desktop");
  assert.equal(getBreakpointTier(1280), "compact");
  assert.equal(getBreakpointTier(900), "compact");
  assert.equal(getBreakpointTier(899), "mobile");
  assert.equal(getBreakpointTier(375), "mobile");
  assert.equal(getBreakpointTier(0), "mobile");

  // clampSize
  assert.equal(clampSize(100, SIZE_LIMITS.SIDEBAR), 200);
  assert.equal(clampSize(300, SIZE_LIMITS.SIDEBAR), 300);
  assert.equal(clampSize(600, SIZE_LIMITS.SIDEBAR), 450);

  // createResponsiveState initial values (simulated desktop 1440x900)
  const state = createResponsiveState();
  assert.equal(state.tier.value, "desktop");
  assert.equal(state.isDesktop.value, true);
  assert.equal(state.isCompact.value, false);
  assert.equal(state.isMobile.value, false);
  assert.equal(state.sidebarOpen.value, true);
  assert.equal(state.rightDrawerOpen.value, true);
  assert.equal(state.bottomDockOpen.value, false);
  assert.equal(state.activeOverlay.value, null);

  // Toggles
  state.toggleSidebar();
  assert.equal(state.sidebarOpen.value, false);
  state.toggleSidebar(true);
  assert.equal(state.sidebarOpen.value, true);

  state.toggleRightDrawer();
  assert.equal(state.rightDrawerOpen.value, false);
  state.toggleRightDrawer(true);
  assert.equal(state.rightDrawerOpen.value, true);

  state.toggleBottomDock();
  assert.equal(state.bottomDockOpen.value, true);
  state.toggleBottomDock(false);
  assert.equal(state.bottomDockOpen.value, false);

  // Resize to compact (1000px): auto-collapses right drawer
  state.updateDimensions(1000, 800);
  assert.equal(state.tier.value, "compact");
  assert.equal(state.isDesktop.value, false);
  assert.equal(state.isCompact.value, true);
  assert.equal(state.rightDrawerOpen.value, false);

  // Resize to mobile (600px) & open overlay
  state.updateDimensions(600, 800);
  assert.equal(state.tier.value, "mobile");
  assert.equal(state.isMobile.value, true);
  state.openOverlay("sidebar");
  assert.equal(state.activeOverlay.value, "sidebar");

  state.closeOverlays();
  assert.equal(state.activeOverlay.value, null);

  // Open overlay on mobile and resize back to desktop -> overlay auto closes
  state.openOverlay("rightDrawer");
  assert.equal(state.activeOverlay.value, "rightDrawer");
  state.updateDimensions(1440, 900);
  assert.equal(state.tier.value, "desktop");
  assert.equal(state.isDesktop.value, true);
  assert.equal(state.activeOverlay.value, null);

  // Resizing dimension clamps
  state.setSidebarWidth(150);
  assert.equal(state.sidebarWidth.value, 200);
  state.setSidebarWidth(400);
  assert.equal(state.sidebarWidth.value, 400);
  state.setSidebarWidth(900);
  assert.equal(state.sidebarWidth.value, 450);

  state.setRightDrawerWidth(250);
  assert.equal(state.rightDrawerWidth.value, 320);
  state.setRightDrawerWidth(700);
  assert.equal(state.rightDrawerWidth.value, 650);

  state.setBottomDockHeight(100);
  assert.equal(state.bottomDockHeight.value, 150);
  state.setBottomDockHeight(500);
  assert.equal(state.bottomDockHeight.value, 400);

  // SSR safe resize binding
  state.bindResizeListener();
  state.unbindResizeListener();
});

// -----------------------------------------------------------------------------
// Test 7: Dual-theme CSS tokens — --bg-drawer & --bg-sidebar (AGENTS.md §9.1)
// Verifikasi token warna kontainer wajib terdefinisi di kedua tema (dark + light).
// -----------------------------------------------------------------------------
test("7. dual-theme CSS tokens: --bg-drawer dan --bg-sidebar terdefinisi di kedua tema", () => {
  const frontendRoot = fileURLToPath(new URL("..", import.meta.url));
  const darkVars = readFileSync(
    resolve(frontendRoot, "src/styles/base/variables.css"),
    "utf-8"
  );
  const lightVars = readFileSync(
    resolve(frontendRoot, "src/styles/themes/theme-light.css"),
    "utf-8"
  );

  assert.ok(darkVars.includes("--bg-drawer"), "dark theme mendefinisikan --bg-drawer");
  assert.ok(darkVars.includes("--bg-sidebar"), "dark theme mendefinisikan --bg-sidebar");
  assert.ok(lightVars.includes("--bg-drawer"), "light theme mendefinisikan --bg-drawer");
  assert.ok(lightVars.includes("--bg-sidebar"), "light theme mendefinisikan --bg-sidebar");
});

// -----------------------------------------------------------------------------
// Test 8: Harmonisasi Background Right Drawer & Left Sidebar (AGENTS.md §9.1 & §9.2)
// Verifikasi konsistensi wallpaper transparency, absence of hardcoded #101018,
// dan keselarasan child views right drawer.
// -----------------------------------------------------------------------------
test("8. harmonisasi background right drawer & left sidebar di wallpaper, drawer, dan light theme", () => {
  const frontendRoot = fileURLToPath(new URL("..", import.meta.url));
  const wallpaperCss = readFileSync(
    resolve(frontendRoot, "src/styles/themes/wallpaper.css"),
    "utf-8"
  );
  const drawerCss = readFileSync(
    resolve(frontendRoot, "src/styles/layout/drawer.css"),
    "utf-8"
  );
  const lightThemeCss = readFileSync(
    resolve(frontendRoot, "src/styles/themes/theme-light.css"),
    "utf-8"
  );

  // 1. Wallpaper mode mencakup seluruh elemen right drawer untuk konsistensi transparansi
  assert.ok(wallpaperCss.includes(".right-drawer-body"), "wallpaper.css mencakup .right-drawer-body");
  assert.ok(wallpaperCss.includes(".rd-activity-view"), "wallpaper.css mencakup .rd-activity-view");
  assert.ok(wallpaperCss.includes(".rd-scroll-area"), "wallpaper.css mencakup .rd-scroll-area");
  assert.ok(wallpaperCss.includes(".rd-consultant-view"), "wallpaper.css mencakup .rd-consultant-view");
  assert.ok(wallpaperCss.includes(".task-hstrip"), "wallpaper.css mencakup .task-hstrip");

  // 2. Larangan fallback hardcoded hex #101018 di drawer.css
  assert.ok(!drawerCss.includes("#101018"), "drawer.css tidak boleh memuat hardcoded #101018");

  // 3. Right drawer header selaras dengan token var(--bg-drawer)
  assert.ok(
    drawerCss.includes(".right-drawer-header") &&
    drawerCss.includes("background: var(--bg-drawer)"),
    "right-drawer-header menggunakan var(--bg-drawer)"
  );

  // 4. Light theme mencakup activity dan scroll area di var(--bg-drawer)
  assert.ok(lightThemeCss.includes(".rd-activity-view"), "theme-light.css mencakup .rd-activity-view");
  assert.ok(lightThemeCss.includes(".rd-scroll-area"), "theme-light.css mencakup .rd-scroll-area");
  assert.ok(lightThemeCss.includes(".task-hstrip"), "theme-light.css mencakup .task-hstrip");
});
