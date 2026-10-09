// Registry terpusat Monaco ITextModel.
// Satu model per path, shared antar-pane (Window 1 & Window 2).
// Model dibuat sekali dan dipertahankan selama tab masih terbuka di salah satu window.

const registry = new Map();
// registry: path -> { model, refCount, savedVersionId, language }

/**
 * Generate URI inmemory kanonis tanpa random suffix agar berkas yang sama
 * memiliki model memori tunggal yang konsisten di semua pane.
 * @param {object} monaco
 * @param {string} path
 * @returns {object|string}
 */
export function canonicalUri(monaco, path) {
  const clean = String(path || "untitled")
    .split("/")
    .map(encodeURIComponent)
    .join("/");
  if (monaco?.Uri?.parse) {
    return monaco.Uri.parse(`inmemory://aegis/${clean}`);
  }
  return `inmemory://aegis/${clean}`;
}

/**
 * Mendapatkan model yang ada atau membuat model baru untuk path tertentu.
 * @param {object} monaco
 * @param {string} path
 * @param {string} text
 * @param {string} language
 * @returns {object} { model, refCount, savedVersionId, language }
 */
export function getOrCreateModel(monaco, path, text = "", language = "plaintext") {
  if (registry.has(path)) {
    const entry = registry.get(path);
    entry.refCount++;
    return entry;
  }

  const uri = canonicalUri(monaco, path);
  let existing = null;
  if (monaco?.editor?.getModel) {
    existing = monaco.editor.getModel(uri);
    if (existing) {
      existing.dispose();
    }
  }

  let model = null;
  if (monaco?.editor?.createModel) {
    model = monaco.editor.createModel(text, language, uri);
  } else {
    // Objek fallback / mock untuk pengujian lingkungan tanpa Monaco penuh
    let currentVersion = 1;
    let content = text ?? "";
    model = {
      uri,
      getValue: () => content,
      setValue: (v) => {
        content = v ?? "";
        currentVersion++;
      },
      getAlternativeVersionId: () => currentVersion,
      getFullModelRange: () => ({
        startLineNumber: 1,
        startColumn: 1,
        endLineNumber: 1,
        endColumn: 1,
      }),
      pushEditOperations: (_before, edits, _cursor) => {
        if (edits && edits[0]) {
          content = edits[0].text ?? "";
        }
        currentVersion++;
      },
      dispose: () => {},
    };
  }

  const entry = {
    model,
    refCount: 1,
    savedVersionId: model?.getAlternativeVersionId ? model.getAlternativeVersionId() : 1,
    language,
  };
  registry.set(path, entry);
  return entry;
}

/**
 * Melepas referensi model saat tab ditutup atau berpindah file.
 * Model hanya di-dispose jika refCount mencapai 0.
 * @param {string} path
 */
export function releaseModel(path) {
  const entry = registry.get(path);
  if (!entry) return;
  entry.refCount = Math.max(0, entry.refCount - 1);
  if (entry.refCount === 0) {
    if (entry.model && typeof entry.model.dispose === "function") {
      entry.model.dispose();
    }
    registry.delete(path);
  }
}

/**
 * Mendapatkan entry registry untuk path tertentu.
 * @param {string} path
 * @returns {object|null}
 */
export function getEntry(path) {
  return registry.get(path) ?? null;
}

/**
 * Mendapatkan ITextModel untuk path tertentu.
 * @param {string} path
 * @returns {object|null}
 */
export function getModel(path) {
  return registry.get(path)?.model ?? null;
}

/**
 * Memeriksa apakah model dibuka di lebih dari satu window/pane.
 * @param {string} path
 * @returns {boolean}
 */
export function isShared(path) {
  return (registry.get(path)?.refCount ?? 0) > 1;
}

/**
 * Memperbarui savedVersionId saat berkas disimpan.
 * @param {string} path
 * @param {number} versionId
 */
export function markSaved(path, versionId) {
  const entry = registry.get(path);
  if (entry) {
    entry.savedVersionId = versionId;
  }
}

/**
 * Memeriksa apakah isi model saat ini berbeda dari versi yang tersimpan.
 * @param {string} path
 * @returns {boolean}
 */
export function isDirty(path) {
  const entry = registry.get(path);
  if (!entry || !entry.model || typeof entry.model.getAlternativeVersionId !== "function") {
    return false;
  }
  return entry.model.getAlternativeVersionId() !== entry.savedVersionId;
}

/**
 * Menerapkan konten dari luar (agen AI / disk reload) menggunakan pushEditOperations
 * agar riwayat undo/redo pengguna tetap terjaga.
 * @param {string} path
 * @param {string} newText
 * @returns {boolean}
 */
export function applyExternalContent(path, newText) {
  const entry = registry.get(path);
  if (!entry || !entry.model) return false;
  const model = entry.model;
  if (
    typeof model.pushEditOperations === "function" &&
    typeof model.getFullModelRange === "function"
  ) {
    const fullRange = model.getFullModelRange();
    model.pushEditOperations(
      [],
      [{ range: fullRange, text: newText ?? "" }],
      () => null
    );
  } else if (typeof model.setValue === "function") {
    model.setValue(newText ?? "");
  }
  return true;
}

/**
 * Mengembalikan snapshot kondisi seluruh registry untuk keperluan pengujian dan audit kesehatan.
 * @returns {Array<{ path: string, refCount: number, isDirty: boolean }>}
 */
export function getRegistrySnapshot() {
  const snapshot = [];
  for (const [path, entry] of registry.entries()) {
    snapshot.push({
      path,
      refCount: entry.refCount,
      isDirty: isDirty(path),
    });
  }
  return snapshot;
}

/**
 * Membersihkan seluruh registry untuk keperluan unit test.
 */
export function clearRegistryForTesting() {
  for (const entry of registry.values()) {
    if (entry.model && typeof entry.model.dispose === "function") {
      entry.model.dispose();
    }
  }
  registry.clear();
}
