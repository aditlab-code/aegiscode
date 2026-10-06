import test from "node:test";
import assert from "node:assert/strict";
import {
  loadWorkspaceContext,
  saveWorkspaceContext,
  clearWorkspaceContext,
  saveGlobalActiveProjectId,
  getGlobalActiveProjectId,
} from "./services/workspaceContextService.js";

// Mock localStorage lingkungan Node.js
function setupMockLocalStorage() {
  const store = new Map();
  globalThis.window = {
    localStorage: {
      getItem(key) {
        return store.has(key) ? store.get(key) : null;
      },
      setItem(key, val) {
        store.set(key, String(val));
      },
      removeItem(key) {
        store.delete(key);
      },
      clear() {
        store.clear();
      },
    },
  };
  return store;
}

test("workspaceContextService: returns default context when storage is empty", () => {
  setupMockLocalStorage();
  const ctx = loadWorkspaceContext("proj_test");
  assert.deepEqual(ctx.editor.tabs, []);
  assert.equal(ctx.editor.activeTab, "activity");
  assert.equal(ctx.layout.activeNav, "explorer");
  assert.equal(ctx.task.viewedTaskId, null);
});

test("workspaceContextService: saves and restores editor tabs and activeTab immediately", () => {
  setupMockLocalStorage();
  const tabs = [
    { path: "src/app/page.tsx", name: "page.tsx", isDiff: false },
    { path: "src/components/Toolbar.tsx", name: "Toolbar.tsx", isDiff: false },
  ];
  saveWorkspaceContext(
    "proj_1",
    {
      editor: {
        tabs,
        activeTab: "src/components/Toolbar.tsx",
      },
      task: {
        viewedTaskId: "task_12345",
      },
    },
    true // immediate save
  );

  const restored = loadWorkspaceContext("proj_1");
  assert.equal(restored.editor.tabs.length, 2);
  assert.equal(restored.editor.tabs[0].path, "src/app/page.tsx");
  assert.equal(restored.editor.activeTab, "src/components/Toolbar.tsx");
  assert.equal(restored.task.viewedTaskId, "task_12345");
});

test("workspaceContextService: isolates context between different projects", () => {
  setupMockLocalStorage();
  saveWorkspaceContext(
    "proj_A",
    {
      editor: {
        tabs: [{ path: "file_a.py", name: "file_a.py" }],
        activeTab: "file_a.py",
      },
      layout: {
        activeNav: "changes",
      },
    },
    true
  );

  saveWorkspaceContext(
    "proj_B",
    {
      editor: {
        tabs: [{ path: "file_b.ts", name: "file_b.ts" }],
        activeTab: "file_b.ts",
      },
      layout: {
        activeNav: "explorer",
      },
    },
    true
  );

  const ctxA = loadWorkspaceContext("proj_A");
  const ctxB = loadWorkspaceContext("proj_B");

  assert.equal(ctxA.editor.tabs[0].path, "file_a.py");
  assert.equal(ctxA.layout.activeNav, "changes");

  assert.equal(ctxB.editor.tabs[0].path, "file_b.ts");
  assert.equal(ctxB.layout.activeNav, "explorer");
});

test("workspaceContextService: safely handles corrupted JSON in localStorage", () => {
  const store = setupMockLocalStorage();
  store.set("aegis_workspace_context_proj_corrupt", "INVALID_JSON{{{{");

  const ctx = loadWorkspaceContext("proj_corrupt");
  assert.deepEqual(ctx.editor.tabs, []);
  assert.equal(ctx.editor.activeTab, "activity");
});

test("workspaceContextService: clearWorkspaceContext cleans up project storage", () => {
  setupMockLocalStorage();
  saveWorkspaceContext("proj_del", { editor: { activeTab: "foo.js" } }, true);
  assert.equal(loadWorkspaceContext("proj_del").editor.activeTab, "foo.js");

  clearWorkspaceContext("proj_del");
  assert.equal(loadWorkspaceContext("proj_del").editor.activeTab, "activity");
});

test("workspaceContextService: manages global active project id", () => {
  setupMockLocalStorage();
  assert.equal(getGlobalActiveProjectId(), null);

  saveGlobalActiveProjectId("project_xyz");
  assert.equal(getGlobalActiveProjectId(), "project_xyz");

  saveGlobalActiveProjectId(null);
  assert.equal(getGlobalActiveProjectId(), null);
});
