// @ts-check
import test from "node:test";
import assert from "node:assert/strict";

// Setup browser globals mock before importing modules
const storage = new Map();
globalThis.localStorage = {
  getItem: (k) => (storage.has(k) ? storage.get(k) : null),
  setItem: (k, v) => storage.set(k, String(v)),
  removeItem: (k) => storage.delete(k),
  clear: () => storage.clear(),
};

let mockFetchHandler = async () => ({
  ok: true,
  status: 200,
  text: async () => JSON.stringify({ entries: [] }),
});

globalThis.fetch = async (url, options) => mockFetchHandler(url, options);

const {
  setWorkspaceProject,
  getCachedFiles,
  setCachedFiles,
  invalidateFileCache,
  fetchWorkspaceFiles,
  useWorkspaceFiles,
} = await import("../src/services/fileCacheService.js");

test("AEG-03 & AEG-12: Workspace file cache isolates data between different projects", async () => {
  invalidateFileCache();

  // Set project A
  setWorkspaceProject("proj-alpha");
  setCachedFiles(["src/alpha_main.py", "src/alpha_utils.py"], "proj-alpha");

  // Set project B
  setWorkspaceProject("proj-beta");
  setCachedFiles(["src/beta_index.js", "src/beta_service.js"], "proj-beta");

  // Periksa cache project A
  const filesA = getCachedFiles("proj-alpha");
  assert.deepEqual(filesA, ["src/alpha_main.py", "src/alpha_utils.py"]);

  // Periksa cache project B
  const filesB = getCachedFiles("proj-beta");
  assert.deepEqual(filesB, ["src/beta_index.js", "src/beta_service.js"]);

  // Beralih kembali ke project A
  setWorkspaceProject("proj-alpha");
  const { workspaceFiles } = useWorkspaceFiles();
  assert.deepEqual(workspaceFiles.value, ["src/alpha_main.py", "src/alpha_utils.py"]);

  // Invalidasi hanya project A
  invalidateFileCache("proj-alpha");
  assert.deepEqual(getCachedFiles("proj-alpha"), []);
  // Project B harus tetap utuh
  assert.deepEqual(getCachedFiles("proj-beta"), ["src/beta_index.js", "src/beta_service.js"]);

  invalidateFileCache();
});

test("AEG-12: Inflight request from old project does not overwrite new project cache upon switch", async () => {
  invalidateFileCache();

  let resolveProjectA;
  const slowPromiseA = new Promise((resolve) => {
    resolveProjectA = resolve;
  });

  // Project A aktif dan memicu fetch yang lambat
  setWorkspaceProject("proj-slow-a");

  mockFetchHandler = async () => {
    await slowPromiseA;
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({
        entries: [{ path: "slow_a_file.txt" }]
      }),
    };
  };

  const inflightFetchA = fetchWorkspaceFiles(true);

  // Pengguna segera berpindah ke Project B sebelum fetch A selesai
  setWorkspaceProject("proj-fast-b");
  setCachedFiles(["fast_b_file.txt"], "proj-fast-b");

  const { workspaceFiles } = useWorkspaceFiles();
  assert.deepEqual(workspaceFiles.value, ["fast_b_file.txt"], "Project B harus menampilkan file Project B");

  // Sekarang selesaikan fetch lambat Project A
  resolveProjectA();
  await inflightFetchA;

  // Nilai aktif workspaceFiles TIDAK BOLEH tertimpa oleh respons lama Project A
  assert.deepEqual(workspaceFiles.value, ["fast_b_file.txt"], "workspaceFiles tidak boleh tercemar oleh respons project lama");
  assert.deepEqual(getCachedFiles("proj-fast-b"), ["fast_b_file.txt"]);

  invalidateFileCache();
});

test("AEG-03: Switching project without cached files resets active workspaceFiles", () => {
  invalidateFileCache();

  setWorkspaceProject("proj-1");
  setCachedFiles(["file1.txt"], "proj-1");

  const { workspaceFiles } = useWorkspaceFiles();
  assert.deepEqual(workspaceFiles.value, ["file1.txt"]);

  // Berpindah ke project baru yang belum memiliki cache
  setWorkspaceProject("proj-2");
  assert.deepEqual(workspaceFiles.value, [], "Project baru yang belum di-cache harus bernilai array kosong");

  invalidateFileCache();
});

console.log("[OK] workspaceIsolation: isolasi cache antar-project dan pencegahan race condition terverifikasi!");
