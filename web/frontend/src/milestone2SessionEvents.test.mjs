import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const readSrc = (relPath) => fs.readFileSync(path.join(__dirname, relPath), "utf8");
const between = (s, a, b) => s.slice(s.indexOf(a), s.indexOf(b, s.indexOf(a)));

test("AI-06: resumeSessionFromId out-of-order response tidak menimpa sesi baru", async () => {
  const chatCode = readSrc("components/ConsultantChat.vue");
  const resumeSource = between(
    chatCode,
    "async function resumeSessionFromId(id) {",
    "\nasync function createNewSession()"
  );

  let waiters = {};
  const messages = { value: [] };
  const env = {
    getConsultantSession: (id) => new Promise((resolve) => {
      waiters[id] = resolve;
    }),
    props: { projectId: "proj-1" },
    messages,
    scrollToBottom: () => {},
  };

  const resumeFn = new Function(
    ...Object.keys(env),
    `let resumeSessionSeq = 0;\n${resumeSource}\nreturn resumeSessionFromId;`
  )(...Object.values(env));

  // Panggil sesi A lalu segera panggil sesi B
  const pA = resumeFn("SESSION_A");
  const pB = resumeFn("SESSION_B");

  // Selesaikan sesi B terlebih dahulu
  waiters["SESSION_B"]({ turns: [{ role: "user", text: "Pesan Sesi B" }] });
  await pB;
  assert.equal(messages.value[0].text, "Pesan Sesi B");

  // Sekarang selesaikan respons sesi A yang terlambat
  waiters["SESSION_A"]({ turns: [{ role: "user", text: "Pesan Sesi A (Usang)" }] });
  await pA;

  // Pesan di antarmuka harus TETAP memuat Pesan Sesi B (tidak tertimpa sesi A)
  assert.equal(messages.value[0].text, "Pesan Sesi B", "Respons sesi lama A tidak boleh menimpa sesi B");
});

test("BUG-03: onFilesPicked membatasi pemilihan batch gambar tepat di batas 8 lampiran", async () => {
  // Pastikan kedua komponen mengimpor dan menggunakan useAttachmentPipeline
  for (const componentFile of ["TaskComposer.vue", "ConsultantChat.vue"]) {
    const code = readSrc(`components/${componentFile}`);
    assert.ok(
      code.includes("useAttachmentPipeline"),
      `${componentFile} wajib mengintegrasikan useAttachmentPipeline`
    );
  }

  const { useAttachmentPipeline } = await import("./composables/useAttachmentPipeline.js");
  const pipeline = useAttachmentPipeline();

  const readers = [];
  globalThis.FileReader = class MockFileReader {
    constructor() {
      readers.push(this);
    }
    readAsDataURL() {
      this.result = "data:image/png;base64,YQ==";
    }
  };

  const mockFiles = Array.from({ length: 10 }, (_, i) => ({
    type: "image/png",
    name: `img_${i}.png`,
  }));

  pipeline.onFilesPicked({ target: { files: mockFiles, value: "" } });
  readers.forEach((r) => r.onload && r.onload());

  assert.equal(
    pipeline.attachments.value.length,
    8,
    "onFilesPicked wajib membatasi total lampiran tepat 8 meskipun dipilih 10 berkas"
  );
});

test("BUG-04: diagnosticService tidak mengeluarkan false SyntaxError pada triple quotes multiline Python dan template literal", async () => {
  const { validateCodeSyntax } = await import("./services/diagnosticService.js");

  // Python triple quotes dengan tanda kurung di baris kedua
  const pyCode = 's = """\n(\n"""\nx = 10\n';
  const pyErrors = validateCodeSyntax(pyCode, "python", "script.py");
  assert.deepEqual(pyErrors, [], "String multiline Python tidak boleh menghasilkan error kurung");

  // JavaScript template literal dengan tanda kurung multiline
  const jsCode = "const template = `\n(\n`;\nconst y = 20;\n";
  const jsErrors = validateCodeSyntax(jsCode, "javascript", "app.js");
  assert.deepEqual(jsErrors, [], "Template literal JS tidak boleh menghasilkan error kurung");

  // Validasi bahwa kurung yang benar-benar tidak tertutup tetap terdeteksi
  const brokenCode = "def test():\n    x = (1 + 2\n";
  const brokenErrors = validateCodeSyntax(brokenCode, "python", "broken.py");
  assert.ok(brokenErrors.length > 0, "Kurung yang benar-benar terbuka wajib terdeteksi");
});

test("BUG-05: penutupan socket lama tidak menghapus referensi socket terminal proyek baru", () => {
  const terminalCode = readSrc("components/TerminalView.vue");
  const socketSource = between(terminalCode, "function initPtySocket() {", "\nwatch(");

  const sockets = [];
  class MockSocket {
    constructor(url) {
      this.url = url;
      sockets.push(this);
    }
    close() {}
  }

  const env = {
    window: {
      location: { protocol: "http:", host: "localhost" },
      WebSocket: MockSocket,
    },
    localStorage: { getItem: () => "" },
    props: { projectId: "proj-alpha" },
  };

  const setup = new Function(
    ...Object.keys(env),
    `let isBrowser = true;
     let socket = null;
     let fitAddon = null;
     let term = null;
     function syncDimensions() {}
     ${socketSource}
     return {
       init: initPtySocket,
       reset: () => { socket = null; },
       get: () => socket,
     };`
  )(...Object.values(env));

  // Inisialisasi socket proyek A
  setup.init();
  const oldSocket = setup.get();
  assert.ok(oldSocket);

  // Simulasi pergantian proyek: watch menutup socket lama, reset, dan inisialisasi socket baru B
  oldSocket.close();
  setup.reset();
  env.props.projectId = "proj-beta";
  setup.init();
  const newSocket = setup.get();
  assert.ok(newSocket);
  assert.notEqual(newSocket, oldSocket);

  // Sekarang callback onclose dari socket A tiba belakangan
  oldSocket.onclose();

  // Socket aktif harus TETAP newSocket (tidak ter-null)
  assert.equal(setup.get(), newSocket, "Socket baru tidak boleh menjadi null karena event penutupan socket lama");
});

test("BUG-07: getCachedFiles('UNSEEN') mengembalikan [] saat cache miss proyek non-aktif", async () => {
  const { setWorkspaceProject, setCachedFiles, getCachedFiles, invalidateFileCache } = await import(
    "./services/fileCacheService.js"
  );

  invalidateFileCache();
  setWorkspaceProject("PROJECT_ACTIVE");
  setCachedFiles(["file_a.py", "file_b.py"], "PROJECT_ACTIVE");

  // Minta cache untuk proyek yang belum pernah dicache
  const unseenFiles = getCachedFiles("UNSEEN_PROJECT");
  assert.deepEqual(
    unseenFiles,
    [],
    "Cache miss untuk proyek yang tidak dikenal wajib mengembalikan array kosong"
  );

  // Pastikan berkas proyek aktif tetap utuh
  assert.deepEqual(getCachedFiles("PROJECT_ACTIVE"), ["file_a.py", "file_b.py"]);
});

test("BUG-08: useWorkbenchLiveEvents mendeteksi penggantian riwayat dengan panjang sama", async () => {
  const liveCode = readSrc("composables/useWorkbenchLiveEvents.js")
    .replace(/^import .*;$/gm, "")
    .replace(/export /g, "");

  const callbacks = [];
  const props = { activityEvents: [], outputLines: [], problems: [] };
  const modifiedFiles = [];

  const useLive = new Function(
    "ref",
    "computed",
    "watch",
    "classifyDiagnostic",
    `${liveCode}\nreturn useWorkbenchLiveEvents;`
  )(
    (v) => ({ value: v }),
    (f) => ({ get value() { return f(); } }),
    (source, fn) => callbacks.push(fn),
    () => ({ type: "info" })
  );

  useLive(props, {
    onFileModified: (p) => modifiedFiles.push(p),
  });

  const makeEvent = (id, path) => ({
    event_id: id,
    type: "tool_completed",
    payload: { tool: "write_file", path, success: true },
  });

  // Kirim array berisi 1 event untuk Task 1
  callbacks[0]([makeEvent("evt-1", "src/fileA.js")]);
  assert.deepEqual(modifiedFiles, ["src/fileA.js"]);

  // Ganti dengan array baru berisi 1 event untuk Task 2 (panjang array sama: 1)
  callbacks[0]([makeEvent("evt-2", "src/fileB.js")]);

  // Event baru wajib diproses
  assert.deepEqual(
    modifiedFiles,
    ["src/fileA.js", "src/fileB.js"],
    "Event fileB pada riwayat baru harus diproses meskipun panjang riwayat sama"
  );
});

test("BUG-09: useWorkbenchLiveEvents mempertahankan masalah dengan pesan sama di berkas/baris berbeda", async () => {
  const liveCode = readSrc("composables/useWorkbenchLiveEvents.js")
    .replace(/^import .*;$/gm, "")
    .replace(/export /g, "");

  const props = {
    activityEvents: [],
    outputLines: [],
    problems: [
      { text: "Syntax error: Unexpected token", file: "src/ComponentA.vue", line: 10, col: 5 },
      { text: "Syntax error: Unexpected token", file: "src/ComponentB.vue", line: 42, col: 1 },
    ],
  };

  const useLive = new Function(
    "ref",
    "computed",
    "watch",
    "classifyDiagnostic",
    `${liveCode}\nreturn useWorkbenchLiveEvents;`
  )(
    (v) => ({ value: v }),
    (f) => ({ get value() { return f(); } }),
    () => {},
    () => ({ type: "info" })
  );

  const instance = useLive(props);
  const effective = instance.effectiveProblems.value;

  assert.equal(
    effective.length,
    2,
    "Dua masalah dengan pesan sama di lokasi berbeda WAJIB tampil sebagai 2 masalah terpisah"
  );
});
