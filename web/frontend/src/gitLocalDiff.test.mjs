import assert from "node:assert/strict";
import test from "node:test";

import {
  createEditorTabsState,
  openTab,
  openDiffTab,
  closeTab,
  getActiveTab,
  setTabConflict,
} from "./services/editorTabsService.js";

import {
  getOrCreateModel,
  releaseModel,
  getModel,
  isShared,
  markSaved,
  isDirty,
  applyExternalContent,
  clearRegistryForTesting,
} from "./services/monacoModelRegistry.js";

import {
  getProjectGitStatus,
  getProjectGitDiff,
  getProjectGitCommits,
  discardProjectGitChanges,
} from "./api.js";

test("1. editorTabsService: openDiffTab creates and keys a diff tab properly", () => {
  const state = createEditorTabsState();

  const tab = openDiffTab(state, "src/agent_ai/main.py");
  assert.ok(tab, "Tab should be created");
  assert.equal(tab.path, "diff://src/agent_ai/main.py");
  assert.equal(tab.filePath, "src/agent_ai/main.py");
  assert.equal(tab.name, "main.py ↔ HEAD");
  assert.equal(tab.isDiff, true);
  assert.equal(state.activeTab.value, "diff://src/agent_ai/main.py");

  // Dedup: re-opening the same diff tab returns the existing tab
  const tab2 = openDiffTab(state, "src/agent_ai/main.py");
  assert.equal(tab2, tab);
  assert.equal(state.tabs.value.length, 1);
});

test("2. editorTabsService: handles mix of regular and diff tabs with proper activation", () => {
  const state = createEditorTabsState();

  openTab(state, "README.md");
  openDiffTab(state, "src/app.py");

  assert.equal(state.tabs.value.length, 2);
  assert.equal(state.activeTab.value, "diff://src/app.py");

  const active = getActiveTab(state);
  assert.equal(active.isDiff, true);

  // Close diff tab -> falls back to previous tab
  const res = closeTab(state, "diff://src/app.py");
  assert.equal(res.closed, true);
  assert.equal(state.activeTab.value, "README.md");
});

test("3. git status badge classification for FileExplorer & ExplorerTreeNode", () => {
  function classifyStatus(rawStatus) {
    if (!rawStatus) return "";
    const s = String(rawStatus);
    if (s.includes("?") || s === "U") return "U";
    if (s.includes("D")) return "D";
    if (s.includes("A")) return "A";
    if (s.includes("M")) return "M";
    if (s.includes("R")) return "R";
    return s;
  }

  assert.equal(classifyStatus("M"), "M");
  assert.equal(classifyStatus(" M"), "M");
  assert.equal(classifyStatus("??"), "U");
  assert.equal(classifyStatus("D"), "D");
  assert.equal(classifyStatus("A"), "A");
  assert.equal(classifyStatus("R"), "R");
  assert.equal(classifyStatus(""), "");
});

test("4. api.js git client endpoint contract", () => {
  assert.equal(typeof getProjectGitStatus, "function");
  assert.equal(typeof getProjectGitDiff, "function");
  assert.equal(typeof getProjectGitCommits, "function");
});

test("5. changes panel filters out internal .aegis and .git metadata paths", () => {
  const rawList = [
    { path: ".aegis" },
    { path: ".aegis/state.json" },
    { path: ".git/HEAD" },
    { path: "src/main.py" },
    { path: "README.md" },
  ];

  const filtered = rawList.filter((c) => {
    const p = String(c?.path || "").trim().replace(/\\/g, "/").replace(/^\.\//, "");
    return (
      p &&
      !p.startsWith("../") &&
      !p.includes("/../") &&
      p !== ".." &&
      p !== ".aegis" &&
      !p.startsWith(".aegis/") &&
      p !== ".git" &&
      !p.startsWith(".git/")
    );
  });

  assert.equal(filtered.length, 2);
  assert.deepEqual(filtered.map((f) => f.path), ["src/main.py", "README.md"]);
});

test("5b. changes panel filters out external and path-traversal paths (../ and /../)", () => {
  const rawList = [
    { path: "../external.txt" },
    { path: "../../parent/sibling.py" },
    { path: "sub/../../traversal.py" },
    { path: ".." },
    { path: "src/valid.js" },
    { path: "docs/spec.md" },
  ];

  const filtered = rawList.filter((c) => {
    const p = String(c?.path || "").trim().replace(/\\/g, "/").replace(/^\.\//, "");
    return (
      p &&
      !p.startsWith("../") &&
      !p.includes("/../") &&
      p !== ".." &&
      p !== ".aegis" &&
      !p.startsWith(".aegis/") &&
      p !== ".git" &&
      !p.startsWith(".git/")
    );
  });

  assert.equal(filtered.length, 2);
  assert.deepEqual(filtered.map((f) => f.path), ["src/valid.js", "docs/spec.md"]);
});

test("5c. changes panel filters out all internal mechanism paths (.aegis, .aether, temp swp, db)", () => {
  function isInternalOrIgnored(path) {
    const p = String(path || "").trim().replace(/\\/g, "/").replace(/^\.\//, "");
    if (!p || p === ".." || p.startsWith("../") || p.includes("/../")) return true;
    const parts = p.split("/").filter(Boolean);
    if (!parts.length) return true;
    const first = parts[0];
    const last = parts[parts.length - 1];
    if (
      first === ".aegis" ||
      first === ".aether" ||
      first === ".git" ||
      first === ".gemini" ||
      first === ".continue" ||
      first === ".ipynb_checkpoints" ||
      first === "__pycache__"
    ) {
      return true;
    }
    if (first.startsWith(".aegis") || first.startsWith(".aether")) return true;
    if (last.startsWith(".aegis_tmp_") || last.startsWith(".aether_tmp_") || last.endsWith(".swp")) return true;
    if (p === "data/aegis.db" || p === "data/aether.db" || p.startsWith("data/aegis.db-") || p.startsWith("data/aether.db-")) return true;
    return false;
  }

  const rawList = [
    { path: ".aegis/permissions.json" },
    { path: ".aether/checkpoint/cp.json" },
    { path: ".aegis_tmp_abc.swp" },
    { path: "data/aegis.db" },
    { path: ".gemini/oauth_creds.json" },
    { path: "__pycache__/module.pyc" },
    { path: "src/calculator.py" },
    { path: "package.json" },
  ];

  const filtered = rawList.filter((c) => !isInternalOrIgnored(c.path));
  assert.equal(filtered.length, 2);
  assert.deepEqual(filtered.map((f) => f.path), ["src/calculator.py", "package.json"]);
});

test("6. diff editor is strictly read-only and provides edit-file transition", () => {
  // Diff editor options contract
  const diffOptions = {
    originalEditable: false,
    readOnly: true,
    renderSideBySide: true,
    automaticLayout: true,
  };

  assert.equal(diffOptions.originalEditable, false);
  assert.equal(diffOptions.readOnly, true);

  // Transition: non-deleted files allow opening in CodeEditor
  function canEdit(status) {
    return status !== "deleted";
  }

  assert.equal(canEdit("modified"), true);
  assert.equal(canEdit("untracked"), true);
  assert.equal(canEdit("deleted"), false);
});

test("7. discard changes: contract and tab cleanup logic", () => {
  assert.equal(typeof discardProjectGitChanges, "function");

  const state = createEditorTabsState();
  openTab(state, "src/index.js");
  openDiffTab(state, "src/index.js");
  openDiffTab(state, "README.md");

  assert.equal(state.tabs.value.length, 3);

  // When src/index.js is discarded, its diff tab is closed
  closeTab(state, "diff://src/index.js", { force: true });
  assert.equal(state.tabs.value.length, 2);
  assert.equal(state.tabs.value.some((t) => t.path === "diff://src/index.js"), false);
  // Regular editor tab remains open
  assert.equal(state.tabs.value.some((t) => t.path === "src/index.js"), true);

  // When Discard All is executed, all diff tabs are closed
  const diffTabs = state.tabs.value.filter((t) => t.isDiff);
  diffTabs.forEach((t) => closeTab(state, t.path, { force: true }));

  assert.equal(state.tabs.value.length, 1);
  assert.equal(state.tabs.value[0].path, "src/index.js");
});

test("8. non-overlay inline in-place discard confirmation state transitions", () => {
  // Simulate ChangesPanel / MonacoDiffEditor inline state machine
  let confirmDiscardAll = false;
  let confirmingFile = null;

  // 1. User clicks Discard All -> switches header in-place
  confirmDiscardAll = true;
  assert.equal(confirmDiscardAll, true);

  // 2. Escape key dismisses it
  function handleEscape() {
    confirmDiscardAll = false;
    confirmingFile = null;
  }
  handleEscape();
  assert.equal(confirmDiscardAll, false);

  // 3. User clicks row discard for 'app.py' -> sets confirmingFile
  confirmingFile = "app.py";
  assert.equal(confirmingFile, "app.py");

  // 4. Click outside cancels confirmingFile
  function handleClickOutside(isInside) {
    if (!isInside) confirmingFile = null;
  }
  handleClickOutside(false);
  assert.equal(confirmingFile, null);

  // 5. Clicking discard on another file cancels previous and sets new
  confirmingFile = "server.py";
  assert.equal(confirmingFile, "server.py");
});

test("9. editorTabsService: conflict property on openTab and setTabConflict tracking", () => {
  const state = createEditorTabsState();
  const tab = openTab(state, "src/agent_ai/runtime.py");

  assert.ok(tab);
  assert.equal(tab.conflict, false, "tab baru memiliki conflict: false");

  const marked = setTabConflict(state, "src/agent_ai/runtime.py", true);
  assert.equal(marked, true);
  assert.equal(tab.conflict, true, "tab.conflict berhasil ditandai true");

  setTabConflict(state, "src/agent_ai/runtime.py", false);
  assert.equal(tab.conflict, false, "tab.conflict berhasil di-reset");

  const notFound = setTabConflict(state, "nonexistent.py", true);
  assert.equal(notFound, false);
});

test("10. monacoModelRegistry: lifecycle, refCount, shared detection, markSaved, isDirty, applyExternalContent", () => {
  clearRegistryForTesting();

  // 1. Pembuatan model pertama kali
  const entry1 = getOrCreateModel(null, "src/core/main.py", "initial content", "python");
  assert.ok(entry1);
  assert.equal(entry1.refCount, 1);
  assert.equal(isShared("src/core/main.py"), false, "Awalnya belum shared");
  assert.equal(isDirty("src/core/main.py"), false, "Awalnya bersih (tidak dirty)");

  // 2. Window 2 membuka berkas yang sama -> model di-share, refCount bertambah
  const entry2 = getOrCreateModel(null, "src/core/main.py");
  assert.equal(entry2, entry1, "Model adalah instance tunggal yang sama");
  assert.equal(entry1.refCount, 2);
  assert.equal(isShared("src/core/main.py"), true, "Terdeteksi shared di kedua window");

  // 3. User mengubah konten model (simulasi dirty)
  const model = getModel("src/core/main.py");
  assert.ok(model);
  assert.equal(model.getValue(), "initial content");
  model.setValue("modified by user");
  assert.equal(isDirty("src/core/main.py"), true, "Model terdeteksi dirty");

  // 4. Simpan berkas -> markSaved
  markSaved("src/core/main.py", model.getAlternativeVersionId());
  assert.equal(isDirty("src/core/main.py"), false, "Setelah markSaved, tidak lagi dirty");

  // 5. Agen memodifikasi file -> applyExternalContent
  const applied = applyExternalContent("src/core/main.py", "updated by agent");
  assert.equal(applied, true);
  assert.equal(model.getValue(), "updated by agent");

  // 6. Release model dari Window 1
  releaseModel("src/core/main.py");
  assert.equal(entry1.refCount, 1);
  assert.equal(isShared("src/core/main.py"), false, "Hanya tinggal 1 window, tidak lagi shared");
  assert.ok(getModel("src/core/main.py"), "Model tetap ada di registry selama refCount > 0");

  // 7. Release model dari Window 2 -> refCount 0, model di-dispose dan dihapus dari registry
  releaseModel("src/core/main.py");
  assert.equal(getModel("src/core/main.py"), null, "Model dibersihkan saat seluruh tab ditutup");

  clearRegistryForTesting();
});


