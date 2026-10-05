import { ref } from "vue";
import { listFiles } from "../api.js";

/**
 * In-memory reactive cache of relative workspace file paths.
 */
const workspaceFiles = ref([]);
const filesLoading = ref(false);
let inflightPromise = null;

/**
 * Retrieve current cached workspace files.
 * @returns {Array<string>}
 */
export function getCachedFiles() {
  return workspaceFiles.value;
}

/**
 * Manually set or override cached workspace files.
 * @param {Array<string>} files
 */
export function setCachedFiles(files) {
  workspaceFiles.value = Array.isArray(files) ? files.slice() : [];
}

/**
 * Invalidate the cached workspace files.
 */
export function invalidateFileCache() {
  workspaceFiles.value = [];
  inflightPromise = null;
}

/**
 * Fetch and cache flat list of workspace files from the backend.
 * @param {boolean} [force=false]
 * @returns {Promise<Array<string>>}
 */
export async function fetchWorkspaceFiles(force = false) {
  if (!force && workspaceFiles.value.length > 0) {
    return workspaceFiles.value;
  }
  if (inflightPromise) {
    return inflightPromise;
  }

  filesLoading.value = true;
  inflightPromise = (async () => {
    try {
      const data = await listFiles(".", true);
      const entries = Array.isArray(data?.entries) ? data.entries : [];
      const paths = entries
        .map((e) => e?.path || e?.name)
        .filter(Boolean);
      workspaceFiles.value = paths;
      return paths;
    } catch (e) {
      // In case of error (e.g. no active project or offline), retain whatever we had or return empty
      return workspaceFiles.value;
    } finally {
      filesLoading.value = false;
      inflightPromise = null;
    }
  })();

  return inflightPromise;
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
  };
}
