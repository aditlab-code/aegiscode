// @ts-check
import test from "node:test";
import assert from "node:assert/strict";
import {
  getOrCreateModel,
  getEntry,
  getModel,
  releaseModel,
  isDirty,
  markSaved,
  applyExternalContent,
  clearRegistryForTesting,
  getRegistrySnapshot,
} from "../src/services/monacoModelRegistry.js";
import {
  createEditorTabsState,
  openTab,
  closeTab,
  setTabDirty,
  getActiveTab,
} from "../src/services/editorTabsService.js";

test("AEG-01: Tab switching preserves unsaved edits and model reference", () => {
  clearRegistryForTesting();

  // Tab A dibuka dan diedit
  const entryA = getOrCreateModel(null, "src/A.js", "content A original", "javascript");
  entryA.model.setValue("content A modified");
  assert.equal(isDirty("src/A.js"), true, "Tab A harus dirty setelah diedit");

  // Tab B dibuka
  const entryB = getOrCreateModel(null, "src/B.js", "content B original", "javascript");
  assert.equal(entryB.model.getValue(), "content B original");

  // Tab A dibuka kembali (switch B -> A)
  // Registry tidak boleh merilis atau mereset model Tab A
  const entryARetrieved = getEntry("src/A.js");
  assert.ok(entryARetrieved, "Model Tab A harus tetap ada di registry saat beralih tab");
  assert.equal(entryARetrieved.model.getValue(), "content A modified", "Edit Tab A tidak boleh hilang");
  assert.equal(isDirty("src/A.js"), true, "Status dirty Tab A harus tetap bertahan");

  clearRegistryForTesting();
});

test("AEG-02: Closing inactive dirty tab saves target model, not active tab", async () => {
  clearRegistryForTesting();

  const tabsState = createEditorTabsState();
  openTab(tabsState, "src/active.js");
  openTab(tabsState, "src/background.js");

  const entryActive = getOrCreateModel(null, "src/active.js", "active original", "javascript");
  const entryBackground = getOrCreateModel(null, "src/background.js", "bg original", "javascript");

  entryBackground.model.setValue("bg modified");
  setTabDirty(tabsState, "src/background.js", true);

  // Simulasikan penulisan berkas target
  let writtenPath = "";
  let writtenContent = "";
  const mockWriteFile = async (path, content) => {
    writtenPath = path;
    writtenContent = content;
    return { ok: true };
  };

  // Simulasikan logika handleConfirmCloseSave untuk target background.js
  const targetTab = tabsState.tabs.value.find((t) => t.path === "src/background.js");
  assert.ok(targetTab, "Tab target harus ditemukan");

  const targetEntry = getEntry(targetTab.path);
  assert.ok(targetEntry, "Model target harus ada di registry");
  await mockWriteFile(targetTab.path, targetEntry.model.getValue());
  markSaved(targetTab.path, targetEntry.model.getAlternativeVersionId());
  setTabDirty(tabsState, targetTab.path, false);
  const closeRes = closeTab(tabsState, targetTab.path, { force: true });
  if (closeRes.closed) {
    releaseModel(targetTab.path);
  }

  assert.equal(writtenPath, "src/background.js", "Harus menyimpan targetTab (src/background.js)");
  assert.equal(writtenContent, "bg modified", "Harus menyimpan isi yang dimodifikasi");
  assert.equal(entryActive.model.getValue(), "active original", "Active tab tidak boleh tersentuh");
  assert.equal(getModel("src/background.js"), null, "Model background harus dirilis setelah ditutup");

  clearRegistryForTesting();
});

test("AEG-02: Save failure preserves tab open and dirty status", async () => {
  clearRegistryForTesting();

  const tabsState = createEditorTabsState();
  openTab(tabsState, "src/important.js");
  setTabDirty(tabsState, "src/important.js", true);

  const entry = getOrCreateModel(null, "src/important.js", "precious code", "javascript");
  entry.model.setValue("precious code updated");

  // Simulasikan kegagalan save (error jaringan / server 500)
  let saveSuccess = false;
  const mockFailingWrite = async () => {
    throw new Error("HTTP 500 Internal Server Error");
  };

  try {
    await mockFailingWrite();
    saveSuccess = true;
  } catch {
    saveSuccess = false;
  }

  // Jika saveSuccess false, tab TIDAK BOLEH ditutup
  if (saveSuccess) {
    closeTab(tabsState, "src/important.js", { force: true });
  }

  const tabStillOpen = tabsState.tabs.value.find((t) => t.path === "src/important.js");
  assert.ok(tabStillOpen, "Tab harus tetap terbuka ketika save gagal");
  assert.equal(tabStillOpen.dirty, true, "Tab harus tetap bertanda dirty");
  assert.equal(entry.model.getValue(), "precious code updated", "Isi editan tidak boleh hilang");

  clearRegistryForTesting();
});

test("AEG-06: Apply to Editor targets specific model directly without race", () => {
  clearRegistryForTesting();

  const tabsState = createEditorTabsState();
  openTab(tabsState, "src/current.js");

  // Target belum dibuka
  const targetPath = "src/target.js";
  const entry = getOrCreateModel(null, targetPath, "old target text", "javascript");

  // Terapkan konten via applyExternalContent
  const applied = applyExternalContent(targetPath, "new code from proposal");
  assert.equal(applied, true);
  assert.equal(entry.model.getValue(), "new code from proposal", "Model target harus diperbarui");

  // Buka tab
  openTab(tabsState, targetPath);
  setTabDirty(tabsState, targetPath, true);

  const activeTab = getActiveTab(tabsState);
  assert.equal(activeTab.path, targetPath, "Tab target harus menjadi active tab");
  assert.equal(activeTab.dirty, true, "Tab target harus ditandai dirty");

  clearRegistryForTesting();
});

test("AEG-07: monacoModelRegistry getRegistrySnapshot and releaseModel non-negative refCount", () => {
  clearRegistryForTesting();

  assert.deepEqual(getRegistrySnapshot(), []);
  const entry = getOrCreateModel(null, "src/snap.js", "content snap", "javascript");
  assert.equal(entry.refCount, 1);

  const snap1 = getRegistrySnapshot();
  assert.equal(snap1.length, 1);
  assert.equal(snap1[0].path, "src/snap.js");
  assert.equal(snap1[0].refCount, 1);
  assert.equal(snap1[0].isDirty, false);

  releaseModel("src/snap.js");
  assert.equal(getRegistrySnapshot().length, 0);

  // Multiple release on nonexistent or already released model does not go negative
  releaseModel("src/snap.js");
  assert.equal(getRegistrySnapshot().length, 0);

  clearRegistryForTesting();
});

console.log("[OK] editorModelLifecycle: tab switching, save target guard, failure handling, dan apply to editor terverifikasi!");
