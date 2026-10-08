import { ref } from "vue";
import { listFiles } from "../api.js";

/**
 * In-memory reactive cache of relative workspace file paths with workspace isolation.
 */
export const workspaceFiles = ref([]);
export const filesLoading = ref(false);
let activeProjectId = null;
let requestSeq = 0;
let inflightPromise = null;

// Map cache per projectId (key: projectId atau "__default__")
const cacheByProject = new Map();

/**
 * Switch active project context for file cache.
 * @param {string|null} projectId
 */
export function setWorkspaceProject(projectId) {
  activeProjectId = projectId || null;
  requestSeq++;
  inflightPromise = null;
  const targetKey = activeProjectId || "__default__";
  const cached = cacheByProject.get(targetKey) || [];
  workspaceFiles.value = cached.slice();
}

/**
 * Retrieve current cached workspace files.
 * @param {string|null} [projectId=null]
 * @returns {Array<string>}
 */
export function getCachedFiles(projectId = null) {
  if (projectId !== null && projectId !== activeProjectId) {
    return cacheByProject.get(projectId) || [];
  }
  const targetKey = activeProjectId || "__default__";
  if (cacheByProject.has(targetKey)) {
    return cacheByProject.get(targetKey);
  }
  return workspaceFiles.value;
}

/**
 * Manually set or override cached workspace files.
 * @param {Array<string>} files
 * @param {string|null} [projectId=null]
 */
export function setCachedFiles(files, projectId = null) {
  const targetKey = (projectId !== null ? projectId : activeProjectId) || "__default__";
  const list = Array.isArray(files) ? files.slice() : [];
  cacheByProject.set(targetKey, list);
  if (!projectId || projectId === activeProjectId) {
    workspaceFiles.value = list;
  }
}

/**
 * Invalidate the cached workspace files.
 * @param {string|null} [projectId=null]
 */
export function invalidateFileCache(projectId = null) {
  requestSeq++;
  inflightPromise = null;
  if (projectId) {
    cacheByProject.delete(projectId);
    if (activeProjectId === projectId) {
      workspaceFiles.value = [];
    }
  } else {
    cacheByProject.clear();
    workspaceFiles.value = [];
  }
}

/**
 * Fetch and cache flat list of workspace files from the backend.
 * @param {boolean|string} [forceOrProjectId=false]
 * @param {boolean} [maybeForce=false]
 * @returns {Promise<Array<string>>}
 */
export async function fetchWorkspaceFiles(forceOrProjectId = false, maybeForce = false) {
  let targetProjectId = activeProjectId;
  let force = false;

  if (typeof forceOrProjectId === "string") {
    targetProjectId = forceOrProjectId;
    force = Boolean(maybeForce);
  } else {
    force = Boolean(forceOrProjectId);
  }

  const targetKey = targetProjectId || "__default__";

  if (!force) {
    if (cacheByProject.has(targetKey) && cacheByProject.get(targetKey).length > 0) {
      const cached = cacheByProject.get(targetKey);
      if (!targetProjectId || targetProjectId === activeProjectId) {
        workspaceFiles.value = cached;
      }
      return cached;
    }
    if (inflightPromise && (!targetProjectId || targetProjectId === activeProjectId)) {
      return inflightPromise;
    }
  }

  const thisSeq = ++requestSeq;
  filesLoading.value = true;
  const promise = (async () => {
    try {
      const data = await listFiles(".", true);
      // Abaikan bila requestSeq telah berganti (misal ganti project / invalidasi terjadi saat request inflight)
      if (thisSeq !== requestSeq) {
        return targetProjectId ? (cacheByProject.get(targetKey) || []) : workspaceFiles.value;
      }
      const entries = Array.isArray(data?.entries) ? data.entries : [];
      const paths = entries
        .map((e) => e?.path || e?.name)
        .filter(Boolean);

      cacheByProject.set(targetKey, paths);
      if (!targetProjectId || targetProjectId === activeProjectId) {
        workspaceFiles.value = paths;
      }
      return paths;
    } catch (e) {
      return targetProjectId ? (cacheByProject.get(targetKey) || []) : workspaceFiles.value;
    } finally {
      if (thisSeq === requestSeq) {
        filesLoading.value = false;
        inflightPromise = null;
      }
    }
  })();

  if (!targetProjectId || targetProjectId === activeProjectId) {
    inflightPromise = promise;
  }
  return promise;
}

/**
 * Return reactive ref to workspace files.
 */
export function useWorkspaceFiles() {
  return {
    workspaceFiles,
    filesLoading,
    fetchWorkspaceFiles,
    invalidateFileCache,
    getCachedFiles,
    setCachedFiles,
    setWorkspaceProject,
  };
}
