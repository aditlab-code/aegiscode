import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Helper membaca isi komponen
const readSrc = (relPath) => fs.readFileSync(path.join(__dirname, relPath), "utf8");
const between = (s, a, b) => s.slice(s.indexOf(a), s.indexOf(b, s.indexOf(a)));

test("BUG-01: switchToFile tidak melempar ReferenceError ketika model sudah ada di cache", async () => {
  const editorCode = readSrc("components/editor/CodeEditor.vue");
  const switchSource = between(editorCode, "async function switchToFile(", "\nasync function initEditor(");

  let syntaxCallback = null;
  const dummyModel = {
    getAlternativeVersionId: () => 1,
    getValue: () => "const x = 10;",
    onDidChangeContent: () => ({}),
  };

  const env = {
    loadSeq: 0,
    loading: { value: false },
    loadError: { value: "" },
    saveError: { value: "" },
    disposed: false,
    container: { value: {} },
    monaco: {
      editor: {
        setModelMarkers: () => {},
      },
    },
    editor: {
      setModel: () => {},
      focus: () => {},
    },
    model: null,
    savedVersionId: null,
    currentPath: { value: "" },
    dirty: { value: false },
    contentSub: null,
    markerSub: null,
    syntaxTimer: null,
    acquiredPaths: new Set(),
    props: { name: "test.js" },
    loadMonacoModule: async () => ({
      getMonaco: () => ({ editor: { setModelMarkers: () => {} } }),
    }),
    detachModelSubscriptions: () => {},
    // Simulasi entry SUDAH ADA di cache (kondisi yang sebelumnya memicu ReferenceError: lang is not defined)
    getEntry: () => ({ model: dummyModel, savedVersionId: 1 }),
    readFileContent: async () => ({ content: "const x = 10;" }),
    languageForFile: () => "javascript",
    getOrCreateModel: () => ({ model: dummyModel, savedVersionId: 1 }),
    emit: () => {},
    setTimeout: (fn, delay) => {
      if (delay === 200) syntaxCallback = fn;
      return 1;
    },
    clearTimeout: () => {},
    nextTick: async () => {},
    layout: () => {},
    validateCodeSyntax: (code, lang, filePath) => {
      // Pastikan lang terdefinisi dan bertipe string
      assert.equal(typeof lang, "string");
      assert.equal(lang, "javascript");
      return [];
    },
  };

  const switchFn = new Function(
    ...Object.keys(env),
    switchSource + ";return switchToFile;"
  )(...Object.values(env));

  // Panggil switchToFile dengan file JavaScript
  await switchFn("test.js");

  // Pastikan callback timer sintaks dapat dieksekusi tanpa ReferenceError
  assert.ok(syntaxCallback, "Callback timer sintaks harus terpasang");
  assert.doesNotThrow(() => {
    syntaxCallback();
  }, "Eksekusi pemeriksaan sintaks tidak boleh melempar ReferenceError");
});

test("BUG-02: save() berbasis snapshot versi mempertahankan dirty: true bila ada ketikan baru saat proses simpan lambat", async () => {
  const editorCode = readSrc("components/editor/CodeEditor.vue");
  const saveSource = between(editorCode, "async function save()", "\nfunction applyContent(");

  let currentText = "Konten Versi A";
  let currentVersion = 1;
  let persistedText = "";
  let resolveDiskWrite;
  const dirty = { value: true };
  let markedVersion = null;

  const fakeModel = {
    getValue: () => currentText,
    getAlternativeVersionId: () => currentVersion,
  };

  const env = {
    editor: {},
    saving: { value: false },
    props: { path: "main.py" },
    model: fakeModel,
    saveError: { value: "" },
    dirty,
    writeFileContent: async (path, content) => {
      persistedText = content;
      // Simulasi latency penulisan disk lambat
      await new Promise((resolve) => {
        resolveDiskWrite = resolve;
      });
    },
    markSaved: (path, ver) => {
      markedVersion = ver;
    },
    emit: () => {},
    savedVersionId: 1,
  };

  const saveFn = new Function(
    ...Object.keys(env),
    saveSource + ";return save;"
  )(...Object.values(env));

  // Mulai proses simpan
  const savePromise = saveFn();

  // Pengguna mengetik teks baru saat disk write sedang berlangsung
  currentText = "Konten Versi B (Ketikan baru)";
  currentVersion = 2;

  // Selesaikan operasi disk write
  resolveDiskWrite();
  const result = await savePromise;

  assert.equal(result, true, "Operasi simpan harus sukses");
  assert.equal(persistedText, "Konten Versi A", "Teks yang tertulis ke disk adalah snapshot awal");
  assert.equal(markedVersion, 1, "Versi yang ditandai tersimpan adalah versi 1 (snapshot)");
  assert.equal(dirty.value, true, "Status dirty WAJIB tetap bernilai true karena ada ketikan baru versi 2");
});

test("BUG-06: fetchWorkspaceFiles simultan mengembalikan hasil yang sama dan me-reset status loading", async () => {
  // Pasang mock browser globals sebelum pemanggilan fetch
  let resolveNetworkCall;
  let networkCalls = 0;
  globalThis.localStorage = {
    getItem: () => null,
    setItem: () => {},
    removeItem: () => {},
  };
  globalThis.fetch = async () => {
    networkCalls++;
    await new Promise((resolve) => {
      resolveNetworkCall = resolve;
    });
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ entries: [{ path: "src/main.js" }, { path: "src/utils.js" }] }),
    };
  };

  const fileCacheModule = await import("./services/fileCacheService.js");
  const { setWorkspaceProject, fetchWorkspaceFiles, filesLoading, invalidateFileCache } = fileCacheModule;

  invalidateFileCache();
  setWorkspaceProject("PROJECT_TEST");

  // Panggil dua kali secara bersamaan saat cache kosong (simulasi dedup inflight)
  const p1 = fetchWorkspaceFiles("PROJECT_TEST");
  const p2 = fetchWorkspaceFiles("PROJECT_TEST");

  assert.equal(filesLoading.value, true, "Status loading harus true saat request jaringan inflight");

  // Selesaikan request jaringan
  resolveNetworkCall();
  const [res1, res2] = await Promise.all([p1, p2]);

  assert.equal(networkCalls, 1, "Hanya tepat satu request jaringan yang dikirimkan untuk dua pemanggil simultan");
  assert.deepEqual(res1, ["src/main.js", "src/utils.js"], "Pemanggil pertama harus memperoleh hasil utuh");
  assert.deepEqual(res2, ["src/main.js", "src/utils.js"], "Pemanggil kedua harus memperoleh hasil utuh yang sama");
  assert.equal(filesLoading.value, false, "Status loading wajib kembali false setelah pemanggilan selesai");
});
