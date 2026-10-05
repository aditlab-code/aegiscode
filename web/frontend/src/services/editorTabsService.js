import { ref } from "vue";

/**
 * Helper to safely extract the tabs array from a ref or plain array.
 * @param {object} state
 * @returns {Array<object>}
 */
function getTabsList(state) {
  if (!state) return [];
  if (Array.isArray(state.tabs?.value)) return state.tabs.value;
  if (Array.isArray(state.tabs)) return state.tabs;
  return [];
}

/**
 * Helper to get the active tab key.
 * @param {object} state
 * @returns {string}
 */
function getActiveTabKey(state) {
  if (!state) return "activity";
  return state.activeTab?.value !== undefined
    ? state.activeTab.value
    : state.activeTab;
}

/**
 * Helper to update the active tab key.
 * @param {object} state
 * @param {string} key
 */
function setActiveTabKey(state, key) {
  if (!state) return;
  if (
    state.activeTab &&
    typeof state.activeTab === "object" &&
    "value" in state.activeTab
  ) {
    state.activeTab.value = key;
  } else {
    state.activeTab = key;
  }
}

/**
 * Initialize reactive state container for editor tabs.
 * @returns {{ tabs: import("vue").Ref<Array<{ path: string, name: string, dirty: boolean }>>, activeTab: import("vue").Ref<string> }}
 */
export function createEditorTabsState() {
  return {
    tabs: ref([]),
    activeTab: ref("activity"),
  };
}

/**
 * Open a tab by file object or path string, deduplicating existing tabs and activating it.
 * @param {object} state
 * @param {object|string} fileOrPath
 * @returns {object|null} The opened or existing tab object
 */
export function openTab(state, fileOrPath) {
  const path =
    fileOrPath && typeof fileOrPath === "object"
      ? fileOrPath.path || fileOrPath.file_path
      : String(fileOrPath || "");
  if (!path) return null;

  const isDiff = Boolean(
    (fileOrPath && typeof fileOrPath === "object" && fileOrPath.isDiff) ||
      path.startsWith("diff://")
  );
  const filePath =
    (fileOrPath && typeof fileOrPath === "object" && fileOrPath.filePath) ||
    (path.startsWith("diff://") ? path.slice(7) : path);

  const tabs = getTabsList(state);
  const defaultName = String(filePath || path).split("/").pop() || path;
  const name =
    (fileOrPath && typeof fileOrPath === "object" && fileOrPath.name) ||
    (isDiff ? `${defaultName} ↔ HEAD` : defaultName);

  let existing = tabs.find((t) => t.path === path);
  if (!existing) {
    const newTab = { path, filePath, name, dirty: false, isDiff };
    tabs.push(newTab);
    existing = tabs[tabs.length - 1];
  }
  setActiveTabKey(state, path);
  return existing;
}

/**
 * Open a diff tab for a given file comparing working tree against HEAD.
 * @param {object} state
 * @param {string|object} fileOrPath
 * @returns {object|null}
 */
export function openDiffTab(state, fileOrPath) {
  const rawPath =
    fileOrPath && typeof fileOrPath === "object"
      ? fileOrPath.filePath || fileOrPath.path || fileOrPath.file_path
      : String(fileOrPath || "");
  if (!rawPath) return null;
  const cleanPath = rawPath.startsWith("diff://") ? rawPath.slice(7) : rawPath;
  const baseName =
    (fileOrPath && typeof fileOrPath === "object" && fileOrPath.name) ||
    cleanPath.split("/").pop() ||
    cleanPath;

  return openTab(state, {
    path: `diff://${cleanPath}`,
    filePath: cleanPath,
    name: `${baseName} ↔ HEAD`,
    isDiff: true,
  });
}

/**
 * Close a tab with dirty check and adjacent tab activation.
 * @param {object} state
 * @param {string} path
 * @param {{ force?: boolean }} [options]
 * @returns {{ closed: boolean, needsConfirm?: boolean, tab?: object }}
 */
export function closeTab(state, path, { force = false } = {}) {
  const tabs = getTabsList(state);
  const idx = tabs.findIndex((t) => t.path === path);
  if (idx === -1) {
    return { closed: false };
  }
  const tab = tabs[idx];
  if (tab.dirty && !force) {
    return { closed: false, needsConfirm: true, tab };
  }

  tabs.splice(idx, 1);
  if (getActiveTabKey(state) === path) {
    if (tabs.length > 0) {
      const nextIdx = Math.max(0, idx - 1);
      setActiveTabKey(state, tabs[nextIdx].path);
    } else {
      setActiveTabKey(state, "activity");
    }
  }
  return { closed: true };
}

/**
 * Select active tab key.
 * @param {object} state
 * @param {string} tabKey
 */
export function selectTab(state, tabKey) {
  setActiveTabKey(state, tabKey);
}

/**
 * Update dirty flag for a tab.
 * @param {object} state
 * @param {string} path
 * @param {boolean} [dirty=true]
 * @returns {boolean} Whether tab was found and updated
 */
export function setTabDirty(state, path, dirty = true) {
  const tabs = getTabsList(state);
  const tab = tabs.find((t) => t.path === path);
  if (tab) {
    tab.dirty = Boolean(dirty);
    return true;
  }
  return false;
}

/**
 * Mark tab as clean / saved.
 * @param {object} state
 * @param {string} path
 * @returns {boolean}
 */
export function setTabSaved(state, path) {
  return setTabDirty(state, path, false);
}

/**
 * Check if any open tab has unsaved changes.
 * @param {object} state
 * @returns {boolean}
 */
export function hasDirtyTabs(state) {
  const tabs = getTabsList(state);
  return tabs.some((t) => Boolean(t.dirty));
}

/**
 * Get tab object corresponding to activeTab, or null if activity / not found.
 * @param {object} state
 * @returns {object|null}
 */
export function getActiveTab(state) {
  const currentKey = getActiveTabKey(state);
  if (currentKey === "activity" || !currentKey) return null;
  const tabs = getTabsList(state);
  return tabs.find((t) => t.path === currentKey) || null;
}
