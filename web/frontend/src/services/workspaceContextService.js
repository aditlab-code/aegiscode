/**
 * workspaceContextService.js
 *
 * Mengelola persistensi dan pemulihan konteks UI per-proyek (tabs editor,
 * tab aktif, layout dock/sidebar, dan task yang sedang diinspeksi) saat
 * halaman browser di-refresh (Cmd+R / F5).
 */

const STORAGE_PREFIX = "aegis_workspace_context_";
const GLOBAL_PROJECT_KEY = "aegis_last_active_project_id";

const DEFAULT_CONTEXT = {
  editor: {
    tabs: [],
    activeTab: "activity",
  },
  layout: {
    activeNav: "explorer",
    sidebarOpen: true,
    rightDrawerOpen: true,
    assistantTab: "agents",
    bottomDockOpen: false,
    dockActiveTab: "terminal",
    dockHeight: 220,
  },
  task: {
    viewedTaskId: null,
  },
  consultant: {
    activeSessionId: null,
  },
};

// Map timer debounce per project
const _debounceTimers = new Map();

/**
 * Validasi apakah lingkungan browser mendukung localStorage.
 * @returns {boolean}
 */
export function isStorageAvailable() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

/**
 * Format key penyimpanan untuk project tertentu.
 * @param {string} projectId
 * @returns {string}
 */
function storageKey(projectId) {
  return `${STORAGE_PREFIX}${projectId}`;
}

/**
 * Muat konteks UI untuk project tertentu dari localStorage.
 * @param {string} projectId
 * @returns {typeof DEFAULT_CONTEXT}
 */
export function loadWorkspaceContext(projectId) {
  if (!projectId || !isStorageAvailable()) {
    return JSON.parse(JSON.stringify(DEFAULT_CONTEXT));
  }

  try {
    const raw = window.localStorage.getItem(storageKey(projectId));
    if (!raw) return JSON.parse(JSON.stringify(DEFAULT_CONTEXT));
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") {
      return JSON.parse(JSON.stringify(DEFAULT_CONTEXT));
    }

    return {
      editor: {
        tabs: Array.isArray(parsed.editor?.tabs) ? parsed.editor.tabs : [],
        activeTab: parsed.editor?.activeTab || "activity",
      },
      layout: {
        activeNav: parsed.layout?.activeNav || "explorer",
        sidebarOpen: parsed.layout?.sidebarOpen !== false,
        rightDrawerOpen: parsed.layout?.rightDrawerOpen !== false,
        assistantTab: parsed.layout?.assistantTab || "agents",
        bottomDockOpen: Boolean(parsed.layout?.bottomDockOpen),
        dockActiveTab: parsed.layout?.dockActiveTab || "terminal",
        dockHeight: typeof parsed.layout?.dockHeight === "number" ? parsed.layout.dockHeight : 220,
      },
      task: {
        viewedTaskId: parsed.task?.viewedTaskId || null,
      },
      consultant: {
        activeSessionId: parsed.consultant?.activeSessionId || null,
      },
    };
  } catch (err) {
    console.warn("Gagal membaca workspace context dari localStorage:", err);
    return JSON.parse(JSON.stringify(DEFAULT_CONTEXT));
  }
}

/**
 * Simpan konteks UI untuk project tertentu ke localStorage secara aman.
 * @param {string} projectId
 * @param {Partial<typeof DEFAULT_CONTEXT>} partialContext
 * @param {boolean} [immediate=false] - bila true, abaikan debounce
 */
export function saveWorkspaceContext(projectId, partialContext, immediate = false) {
  if (!projectId || !isStorageAvailable()) return;

  const performSave = () => {
    try {
      const existing = loadWorkspaceContext(projectId);
      const merged = {
        editor: {
          ...existing.editor,
          ...(partialContext.editor || {}),
        },
        layout: {
          ...existing.layout,
          ...(partialContext.layout || {}),
        },
        task: {
          ...existing.task,
          ...(partialContext.task || {}),
        },
        consultant: {
          ...existing.consultant,
          ...(partialContext.consultant || {}),
        },
      };

      window.localStorage.setItem(storageKey(projectId), JSON.stringify(merged));
    } catch (err) {
      console.warn("Gagal menyimpan workspace context ke localStorage:", err);
    }
  };

  if (immediate) {
    if (_debounceTimers.has(projectId)) {
      clearTimeout(_debounceTimers.get(projectId));
      _debounceTimers.delete(projectId);
    }
    performSave();
    return;
  }

  // Debounce 250ms untuk menghindari I/O berlebihan saat user interaktif
  if (_debounceTimers.has(projectId)) {
    clearTimeout(_debounceTimers.get(projectId));
  }
  const timer = setTimeout(() => {
    _debounceTimers.delete(projectId);
    performSave();
  }, 250);
  _debounceTimers.set(projectId, timer);
}

/**
 * Hapus konteks project saat project ditutup atau dihapus.
 * @param {string} projectId
 */
export function clearWorkspaceContext(projectId) {
  if (!projectId || !isStorageAvailable()) return;
  if (_debounceTimers.has(projectId)) {
    clearTimeout(_debounceTimers.get(projectId));
    _debounceTimers.delete(projectId);
  }
  try {
    window.localStorage.removeItem(storageKey(projectId));
  } catch (_) {}
}

/**
 * Simpan ID project aktif global.
 * @param {string} projectId
 */
export function saveGlobalActiveProjectId(projectId) {
  if (!isStorageAvailable()) return;
  try {
    if (projectId) {
      window.localStorage.setItem(GLOBAL_PROJECT_KEY, projectId);
    } else {
      window.localStorage.removeItem(GLOBAL_PROJECT_KEY);
    }
  } catch (_) {}
}

/**
 * Ambil ID project aktif global terakhir.
 * @returns {string|null}
 */
export function getGlobalActiveProjectId() {
  if (!isStorageAvailable()) return null;
  try {
    return window.localStorage.getItem(GLOBAL_PROJECT_KEY) || null;
  } catch (_) {
    return null;
  }
}
