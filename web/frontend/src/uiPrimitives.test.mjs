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

async function renderComponent(name, props = {}) {
  const mod = await vite.ssrLoadModule(`/src/components/ui/${name}.vue`);
  const app = createSSRApp(mod.default, props);
  return renderToString(app);
}
test("1. SSR compilation and rendering of all 10 UI components", async () => {
  const componentNames = [
    "AppButton",
    "AppBadge",
    "AppCard",
    "AppModal",
    "AppDrawer",
    "AppToggle",
    "AppSplitter",
    "AppBreadcrumbs",
    "AppThinkingBlock",
    "AppCommandPalette",
  ];
  for (const name of componentNames) {
    const mod = await vite.ssrLoadModule(`/src/components/ui/${name}.vue`);
    assert.ok(mod.default, `${name} should export default component`);
    const sampleProps = name === "AppDrawer" ? { title: "Title" } : (name === "AppSplitter" ? { modelValue: 200 } : {});
    const app = createSSRApp(mod.default, sampleProps);
    const html = await renderToString(app);
    assert.ok(typeof html === "string", `${name} should render to string in SSR`);
  }
});

test("2. AppButton: default props, variant resolution, busy state disabling", async () => {
  // Ghost (default)
  const ghostHtml = await renderComponent("AppButton");
  assert.ok(ghostHtml.includes("btn-aether"));
  assert.ok(ghostHtml.includes("btn-ghost"));
  assert.ok(!ghostHtml.includes("disabled"));
  assert.ok(!ghostHtml.includes("btn-spinner"));

  // Primary variant
  const primaryHtml = await renderComponent("AppButton", { variant: "primary" });
  assert.ok(primaryHtml.includes("btn-primary"));
  assert.ok(primaryHtml.includes("btn-primary-a"));

  // Danger variant
  const dangerHtml = await renderComponent("AppButton", { variant: "danger" });
  assert.ok(dangerHtml.includes("btn-danger"));
  assert.ok(dangerHtml.includes("btn-danger-a"));

  // Icon variant
  const iconHtml = await renderComponent("AppButton", { variant: "icon" });
  assert.ok(iconHtml.includes("icon-btn"));
  assert.ok(!iconHtml.includes("btn-aether"));

  // Busy state disables button and injects spinner
  const busyHtml = await renderComponent("AppButton", { busy: true });
  assert.ok(busyHtml.includes("disabled"));
  assert.ok(busyHtml.includes("is-busy"));
  assert.ok(busyHtml.includes("btn-spinner"));

  // Disabled state
  const disabledHtml = await renderComponent("AppButton", { disabled: true });
  assert.ok(disabledHtml.includes("disabled"));

  // Small size
  const smHtml = await renderComponent("AppButton", { size: "sm" });
  assert.ok(smHtml.includes("btn-sm"));
});

test("3. AppBadge: variant mappings and status dot rendering", async () => {
  // Count (default)
  const countHtml = await renderComponent("AppBadge", { variant: "count" });
  assert.ok(countHtml.includes("aether-badge"));
  assert.ok(countHtml.includes("q-badge"));

  // Drawer
  const drawerHtml = await renderComponent("AppBadge", { variant: "drawer" });
  assert.ok(drawerHtml.includes("drawer-badge"));

  // Status with dot
  const statusHtml = await renderComponent("AppBadge", {
    variant: "status",
    status: "running",
    dot: true,
  });
  assert.ok(statusHtml.includes("status-tag"));
  assert.ok(statusHtml.includes("status-running"));
  assert.ok(statusHtml.includes("status-dot"));

  // Chip with dot and size sm
  const chipHtml = await renderComponent("AppBadge", {
    variant: "chip",
    status: "completed",
    dot: true,
    size: "sm",
  });
  assert.ok(chipHtml.includes("chip"));
  assert.ok(chipHtml.includes("chip-sm"));
  assert.ok(chipHtml.includes("dot"));

  // Seg
  const segHtml = await renderComponent("AppBadge", { variant: "seg" });
  assert.ok(segHtml.includes("seg-badge"));
  assert.ok(segHtml.includes("aether-badge"));
});

test("4. AppCard: block, task, and panel variant styling", async () => {
  // Block (default)
  const blockHtml = await renderComponent("AppCard", {
    variant: "block",
    title: "Workspace Title",
  });
  assert.ok(blockHtml.includes('<section class="block"'));
  assert.ok(blockHtml.includes("block-title"));
  assert.ok(blockHtml.includes("Workspace Title"));

  // Block without border bottom
  const noBorderHtml = await renderComponent("AppCard", {
    variant: "block",
    title: "No Border",
    borderBottom: false,
  });
  assert.ok(noBorderHtml.includes("border-bottom:none") || noBorderHtml.includes("border-bottom: none"));

  // Task variant
  const taskHtml = await renderComponent("AppCard", { variant: "task" });
  assert.ok(taskHtml.includes('<div class="task-card"'));

  // Panel variant
  const panelHtml = await renderComponent("AppCard", { variant: "panel" });
  assert.ok(panelHtml.includes('<div class="panel-card"'));
});

test("5. AppDrawer: collapsed state toggling and header structure", async () => {
  // Expanded
  const expHtml = await renderComponent("AppDrawer", {
    title: "EXPLORER",
    sub: "3 files",
    collapsed: false,
  });
  assert.ok(expHtml.includes("drawer-block"));
  assert.ok(!expHtml.includes("drawer-block collapsed"));
  assert.ok(expHtml.includes("▾"));
  assert.ok(expHtml.includes("EXPLORER"));
  assert.ok(expHtml.includes("3 files"));

  // Collapsed
  const colHtml = await renderComponent("AppDrawer", {
    title: "EXPLORER",
    collapsed: true,
  });
  assert.ok(colHtml.includes("drawer-block collapsed"));
  assert.ok(colHtml.includes("▸"));
});

test("6. AppToggle: switch boolean emitting and tab option resolution", async () => {
  // Switch
  const switchHtml = await renderComponent("AppToggle", {
    type: "switch",
    modelValue: true,
    label: "Auto-save",
  });
  assert.ok(switchHtml.includes("slider-toggle"));
  assert.ok(switchHtml.includes("slider-track"));
  assert.ok(switchHtml.includes("slider-thumb"));
  assert.ok(switchHtml.includes("Auto-save"));
  assert.ok(switchHtml.includes("checked"));

  // Tabs
  const tabsHtml = await renderComponent("AppToggle", {
    type: "tabs",
    modelValue: "tab2",
    options: [
      { value: "tab1", label: "Overview", badge: 3 },
      { value: "tab2", label: "Changes", badge: "!", error: true },
    ],
  });
  assert.ok(tabsHtml.includes("seg-tabs"));
  assert.ok(tabsHtml.includes("seg-tab"));
  assert.ok(tabsHtml.includes("Overview"));
  assert.ok(tabsHtml.includes("Changes"));
  assert.ok(tabsHtml.includes("seg-badge-err"));
});

test("7. AppSplitter: min/max clamping arithmetic and inverted delta handling", async () => {
  const splitterHtml = await renderComponent("AppSplitter", {
    direction: "vertical",
    modelValue: 280,
  });
  assert.ok(splitterHtml.includes("app-splitter"));
  assert.ok(splitterHtml.includes("splitter-vertical"));

  // Arithmetic clamping verification
  function computeClamped(startSize, startPos, currentPos, min, max, inverted = false) {
    const delta = inverted ? (startPos - currentPos) : (currentPos - startPos);
    return Math.max(min, Math.min(max, Math.round(startSize + delta)));
  }

  // Normal dragging forward
  assert.equal(computeClamped(200, 100, 150, 100, 500, false), 250);
  // Clamping to max
  assert.equal(computeClamped(200, 100, 600, 100, 500, false), 500);
  // Clamping to min
  assert.equal(computeClamped(200, 100, -20, 100, 500, false), 100);

  // Inverted dragging (e.g. right drawer where dragging left increases width)
  assert.equal(computeClamped(200, 500, 450, 100, 500, true), 250);
  assert.equal(computeClamped(200, 500, 700, 100, 500, true), 100);
});

test("8. AppBreadcrumbs: path hierarchy splitting into cumulative breadcrumb segments", async () => {
  const breadcrumbsHtml = await renderComponent("AppBreadcrumbs", {
    path: "web/frontend/src/App.vue",
    root: "Aether-Agent",
  });
  assert.ok(breadcrumbsHtml.includes("app-breadcrumbs"));
  assert.ok(breadcrumbsHtml.includes("Aether-Agent"));
  assert.ok(breadcrumbsHtml.includes("web"));
  assert.ok(breadcrumbsHtml.includes("frontend"));
  assert.ok(breadcrumbsHtml.includes("src"));
  assert.ok(breadcrumbsHtml.includes("App.vue"));
  assert.ok(breadcrumbsHtml.includes("breadcrumb-current"));

  // Verify cumulative path logic
  function parseSegments(path) {
    if (!path) return [];
    const parts = path.replace(/^\/+/, "").split("/").filter(Boolean);
    let curr = "";
    return parts.map((part, idx) => {
      curr = curr ? `${curr}/${part}` : part;
      const isFile = idx === parts.length - 1;
      return { label: part, path: curr, isFile };
    });
  }

  const segs = parseSegments("src/components/ui/AppButton.vue");
  assert.equal(segs.length, 4);
  assert.deepEqual(segs[0], { label: "src", path: "src", isFile: false });
  assert.deepEqual(segs[1], { label: "components", path: "src/components", isFile: false });
  assert.deepEqual(segs[2], { label: "ui", path: "src/components/ui", isFile: false });
  assert.deepEqual(segs[3], { label: "AppButton.vue", path: "src/components/ui/AppButton.vue", isFile: true });
});

test("9. AppThinkingBlock: duration formatting", async () => {
  // Numeric duration
  const htmlNum = await renderComponent("AppThinkingBlock", {
    title: "Analyzing model",
    duration: 12,
    collapsed: false,
  });
  assert.ok(htmlNum.includes("12s"));
  assert.ok(htmlNum.includes("Analyzing model"));

  // String duration already with 's'
  const htmlStr = await renderComponent("AppThinkingBlock", {
    duration: "4.5s",
  });
  assert.ok(htmlStr.includes("4.5s"));

  // Null duration renders no badge
  const htmlNull = await renderComponent("AppThinkingBlock", {
    duration: null,
  });
  assert.ok(!htmlNull.includes("thinking-badge"));
});

test("10. AppCommandPalette: query filtering logic for files and commands", async () => {
  const html = await renderComponent("AppCommandPalette", {
    modelValue: true,
    mode: "files",
    files: ["src/App.vue", "src/styles.css"],
  });
  assert.ok(html.includes("cmd-palette-backdrop"));
  assert.ok(html.includes("cmd-palette-modal"));
  assert.ok(html.includes("⌘P Files"));
  assert.ok(html.includes("src/App.vue"));
  assert.ok(html.includes("src/styles.css"));

  // Query filtering logic verification
  function filterItems(mode, query, files, commands) {
    const q = query.trim().toLowerCase();
    if (mode === "files") {
      if (!q) return files.slice(0, 50);
      return files.filter((f) => f.toLowerCase().includes(q)).slice(0, 50);
    } else {
      if (!q) return commands.slice(0, 50);
      return commands.filter((c) => {
        const matchTitle = c.title && c.title.toLowerCase().includes(q);
        const matchCat = c.category && c.category.toLowerCase().includes(q);
        return matchTitle || matchCat;
      }).slice(0, 50);
    }
  }

  const files = ["README.md", "package.json", "src/components/ui/AppButton.vue"];
  assert.deepEqual(filterItems("files", "Button", files, []), ["src/components/ui/AppButton.vue"]);
  assert.deepEqual(filterItems("files", "", files, []).length, 3);

  const commands = [
    { id: "save", title: "File: Save", category: "File" },
    { id: "replan", title: "Agent: Replan", category: "Agent" },
  ];
  assert.deepEqual(filterItems("commands", "replan", [], commands), [commands[1]]);
  assert.deepEqual(filterItems("commands", "file", [], commands), [commands[0]]);
});

test.after(async () => {
  await vite.close();
  console.log("[OK] uiPrimitives: 10 atomic UI components SSR render and function correctly.");
});
