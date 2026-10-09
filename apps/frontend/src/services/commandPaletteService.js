import { ref } from "vue";

/**
 * Check if pattern is a subsequence of string (fuzzy matching).
 * @param {string} pattern
 * @param {string} str
 * @returns {boolean}
 */
function isSubsequence(pattern, str) {
  let pIdx = 0;
  for (let i = 0; i < str.length && pIdx < pattern.length; i++) {
    if (str[i] === pattern[pIdx]) {
      pIdx++;
    }
  }
  return pIdx === pattern.length;
}

/**
 * Filter list of file paths by query using substring and subsequence fuzzy search.
 * @param {string} query
 * @param {Array<string>} files
 * @param {number} [maxResults=50]
 * @returns {Array<string>}
 */
export function filterFiles(query, files = [], maxResults = 50) {
  if (!Array.isArray(files)) return [];
  const q = String(query || "").trim().toLowerCase();
  if (!q) {
    return files.slice(0, maxResults);
  }

  const results = [];
  for (const f of files) {
    const fLower = String(f || "").toLowerCase();
    if (fLower.includes(q) || isSubsequence(q, fLower)) {
      results.push(f);
      if (results.length >= maxResults) break;
    }
  }
  return results;
}

/**
 * Filter list of command items by query against title and category.
 * @param {string} query
 * @param {Array<object>} commands
 * @returns {Array<object>}
 */
export function filterCommands(query, commands = []) {
  if (!Array.isArray(commands)) return [];
  const q = String(query || "").trim().toLowerCase();
  if (!q) {
    return commands.slice(0, 50);
  }

  return commands
    .filter((c) => {
      if (!c) return false;
      const title = String(c.title || "").toLowerCase();
      const category = String(c.category || "").toLowerCase();
      return (
        title.includes(q) ||
        category.includes(q) ||
        isSubsequence(q, title) ||
        isSubsequence(q, category)
      );
    })
    .slice(0, 50);
}

/**
 * Match a KeyboardEvent against a shortcut string spec (e.g. 'Cmd+P', 'Ctrl+`', 'Cmd+Shift+P').
 * @param {KeyboardEvent} event
 * @param {string} shortcut
 * @returns {boolean}
 */
export function matchesShortcut(event, shortcut) {
  if (!event || !shortcut) return false;
  const parts = String(shortcut)
    .split("+")
    .map((s) => s.trim().toLowerCase());
  const key = parts[parts.length - 1];

  const wantsMetaOrCtrl =
    parts.includes("cmd") || parts.includes("ctrl") || parts.includes("command");
  const wantsShift = parts.includes("shift");
  const wantsAlt =
    parts.includes("alt") || parts.includes("opt") || parts.includes("option");

  const hasMetaOrCtrl = Boolean(event.metaKey || event.ctrlKey);
  const hasShift = Boolean(event.shiftKey);
  const hasAlt = Boolean(event.altKey);

  if (wantsMetaOrCtrl !== hasMetaOrCtrl) return false;
  if (wantsShift !== hasShift) return false;
  if (wantsAlt !== hasAlt) return false;

  const eventKey = String(event.key || "").toLowerCase();
  return eventKey === key;
}

/**
 * Return standard default IDE command definitions with optional handler bindings.
 * @param {Record<string, Function>} [handlers={}]
 * @returns {Array<object>}
 */
export function getDefaultCommands(handlers = {}) {
  return [
    {
      id: "workbench.action.quickOpen",
      title: "Files: Quick Open",
      category: "Files",
      shortcut: "Cmd+P",
      handler: handlers["workbench.action.quickOpen"] || handlers.quickOpen,
      icon: "file",
    },
    {
      id: "workbench.action.showCommands",
      title: "Commands: Show All Commands",
      category: "Commands",
      shortcut: "Cmd+K",
      handler:
        handlers["workbench.action.showCommands"] || handlers.showCommands,
      icon: "terminal",
    },
    {
      id: "workbench.action.toggleTerminal",
      title: "View: Toggle Terminal Dock",
      category: "View",
      shortcut: "Ctrl+`",
      handler:
        handlers["workbench.action.toggleTerminal"] || handlers.toggleTerminal,
      icon: "layout",
    },
    {
      id: "workbench.action.toggleSidebar",
      title: "View: Toggle Primary Sidebar",
      category: "View",
      shortcut: "Cmd+B",
      handler:
        handlers["workbench.action.toggleSidebar"] || handlers.toggleSidebar,
      icon: "sidebar",
    },
    {
      id: "workbench.action.toggleRightAssistant",
      title: "View: Toggle AI Assistant",
      category: "View",
      shortcut: "Cmd+J",
      handler:
        handlers["workbench.action.toggleRightAssistant"] ||
        handlers.toggleRightAssistant,
      icon: "sparkle",
    },
    {
      id: "workbench.action.saveFile",
      title: "File: Save Current File",
      category: "File",
      shortcut: "Cmd+S",
      handler: handlers["workbench.action.saveFile"] || handlers.saveFile,
      icon: "save",
    },
    {
      id: "workbench.action.toggleTheme",
      title: "Preferences: Toggle Theme",
      category: "Preferences",
      shortcut: "",
      handler: handlers["workbench.action.toggleTheme"] || handlers.toggleTheme,
      icon: "theme",
    },
    {
      id: "workbench.action.toggleWallpaper",
      title: "Preferences: Toggle Background Wallpaper",
      category: "Preferences",
      shortcut: "",
      handler:
        handlers["workbench.action.toggleWallpaper"] || handlers.toggleWallpaper,
      icon: "layout",
    },
  ];
}

/**
 * Create a reactive command registry.
 * @returns {{
 *   commands: import("vue").Ref<Array<object>>,
 *   registerCommand: (cmd: object) => void,
 *   unregisterCommand: (id: string) => void,
 *   getCommands: () => Array<object>,
 *   executeCommand: (id: string, ...args: any[]) => any
 * }}
 */
export function createCommandRegistry() {
  const commands = ref([]);

  function registerCommand(cmd) {
    if (!cmd || !cmd.id) return;
    const list = commands.value;
    const idx = list.findIndex((c) => c.id === cmd.id);
    if (idx !== -1) {
      list[idx] = { ...list[idx], ...cmd };
    } else {
      list.push({ ...cmd });
    }
  }

  function unregisterCommand(id) {
    const list = commands.value;
    const idx = list.findIndex((c) => c.id === id);
    if (idx !== -1) {
      list.splice(idx, 1);
    }
  }

  function getCommands() {
    return commands.value;
  }

  function executeCommand(id, ...args) {
    const cmd = commands.value.find((c) => c.id === id);
    if (!cmd) return null;
    if (typeof cmd.handler === "function") {
      return cmd.handler(...args);
    }
    return null;
  }

  return {
    commands,
    registerCommand,
    unregisterCommand,
    getCommands,
    executeCommand,
  };
}

/**
 * Bind global keyboard shortcuts to handlers with SSR-safe cleanup.
 * @param {Array<{ shortcut: string, handler: Function }> | Record<string, Function>} shortcutMap
 * @param {EventTarget} [target=typeof window !== 'undefined' ? window : null]
 * @returns {() => void} Cleanup unbind function
 */
export function bindGlobalShortcuts(
  shortcutMap,
  target = typeof window !== "undefined" ? window : null
) {
  if (!target || typeof target.addEventListener !== "function") {
    return () => {};
  }

  const entries = Array.isArray(shortcutMap)
    ? shortcutMap
    : Object.entries(shortcutMap || {}).map(([shortcut, handler]) => ({
        shortcut,
        handler,
      }));

  function listener(event) {
    for (const item of entries) {
      if (item && item.shortcut && matchesShortcut(event, item.shortcut)) {
        if (typeof item.handler === "function") {
          item.handler(event);
        }
      }
    }
  }

  target.addEventListener("keydown", listener);
  return () => {
    target.removeEventListener("keydown", listener);
  };
}
