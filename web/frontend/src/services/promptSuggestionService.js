import { ref, nextTick } from "vue";
import { filterFiles } from "./commandPaletteService.js";
import { getCachedFiles, fetchWorkspaceFiles } from "./fileCacheService.js";

/**
 * Prompt Templates & Autocomplete Suggestion Service.
 * Implements Roadmap Item #5 (Mention popover @file, template prompt /shortcuts, history recall).
 */

export const PROMPT_TEMPLATES = [
  {
    id: "fix",
    command: "/fix",
    label: "Quick Fix",
    description: "Fix bug or error in specified component",
    template: "Fix the following issue: ",
  },
  {
    id: "test",
    command: "/test",
    label: "Write & Run Tests",
    description: "Write and execute unit or integration tests",
    template: "Write and run comprehensive tests for: ",
  },
  {
    id: "audit",
    command: "/audit",
    label: "Security & Quality Audit",
    description: "Audit security vulnerabilities, bottlenecks, and code cleanliness",
    template: "Perform a security, performance, and code quality audit of: ",
  },
  {
    id: "refactor",
    command: "/refactor",
    label: "Lean Refactoring",
    description: "Refactor and simplify code adhering strictly to YAGNI",
    template: "Refactor and simplify the following code: ",
  },
];

/**
 * Filter template suggestions by query.
 * @param {string} query
 * @param {Array<object>} [templates=PROMPT_TEMPLATES]
 * @returns {Array<object>}
 */
export function filterTemplates(query, templates = PROMPT_TEMPLATES) {
  const q = String(query || "").trim().toLowerCase();
  const cleanQ = q.startsWith("/") ? q.slice(1) : q;
  if (!cleanQ) {
    return templates.slice();
  }

  return templates.filter((t) => {
    const id = (t.id || "").toLowerCase();
    const cmd = (t.command || "").toLowerCase();
    const label = (t.label || "").toLowerCase();
    const desc = (t.description || "").toLowerCase();
    return (
      id.includes(cleanQ) ||
      cmd.includes(cleanQ) ||
      label.includes(cleanQ) ||
      desc.includes(cleanQ)
    );
  });
}

/**
 * Parse textarea content and cursor position to detect active @mention or /template trigger.
 * @param {string} text
 * @param {number} cursorPos
 * @returns {{ active: boolean, type?: 'mention' | 'template', query?: string, triggerChar?: string, start?: number, end?: number }}
 */
export function parseAutocompleteTrigger(text, cursorPos) {
  if (typeof text !== "string" || cursorPos === undefined || cursorPos === null) {
    return { active: false };
  }

  const safeCursor = Math.max(0, Math.min(cursorPos, text.length));
  const beforeCursor = text.slice(0, safeCursor);

  // 1. Check for @mention: @ preceded by start, whitespace, or bracket
  const lastAt = beforeCursor.lastIndexOf("@");
  if (lastAt !== -1) {
    const charBeforeAt = lastAt > 0 ? beforeCursor[lastAt - 1] : " ";
    const isValidBoundary = /[\s\(\[\{,\n\r]/.test(charBeforeAt);
    const mentionSlice = beforeCursor.slice(lastAt + 1);

    // No whitespace allowed inside the active mention query
    if (isValidBoundary && !/\s/.test(mentionSlice)) {
      return {
        active: true,
        type: "mention",
        triggerChar: "@",
        query: mentionSlice,
        start: lastAt,
        end: safeCursor,
      };
    }
  }

  // 2. Check for /template: / at start of line or preceded by whitespace/newline
  const lastSlash = beforeCursor.lastIndexOf("/");
  if (lastSlash !== -1) {
    const charBeforeSlash = lastSlash > 0 ? beforeCursor[lastSlash - 1] : "\n";
    const isValidBoundary = /[\s\n\r]/.test(charBeforeSlash);
    const templateSlice = beforeCursor.slice(lastSlash + 1);

    // No whitespace allowed inside the active template query
    if (isValidBoundary && !/\s/.test(templateSlice)) {
      return {
        active: true,
        type: "template",
        triggerChar: "/",
        query: templateSlice,
        start: lastSlash,
        end: safeCursor,
      };
    }
  }

  return { active: false };
}

/**
 * Apply suggestion insertion into text.
 * @param {string} text
 * @param {{ start: number, end: number, type: string }} trigger
 * @param {string|object} suggestion
 * @returns {{ newText: string, newCursorPos: number }}
 */
export function applySuggestion(text, trigger, suggestion) {
  if (!trigger || trigger.start === undefined || trigger.end === undefined) {
    return { newText: text, newCursorPos: text.length };
  }

  let insertContent = "";
  if (trigger.type === "mention") {
    const filePath = typeof suggestion === "string" ? suggestion : (suggestion?.path || suggestion?.name || "");
    insertContent = `@${filePath} `;
  } else if (trigger.type === "template") {
    insertContent = typeof suggestion === "string"
      ? suggestion
      : (suggestion?.template || `${suggestion?.command || ""} `);
  }

  const prefix = text.slice(0, trigger.start);
  let suffix = text.slice(trigger.end);
  if (insertContent.endsWith(" ") && suffix.startsWith(" ")) {
    suffix = suffix.slice(1);
  }
  const newText = prefix + insertContent + suffix;
  const newCursorPos = prefix.length + insertContent.length;

  return {
    newText,
    newCursorPos,
  };
}

/**
 * Create a prompt history manager with draft preservation and localStorage sync.
 * @param {{ storageKey: string, maxEntries?: number }} options
 */
export function createHistoryManager({ storageKey, maxEntries = 50 }) {
  let history = [];

  // Initialize from storage if available
  if (typeof window !== "undefined" && window.localStorage && storageKey) {
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          history = parsed.slice(0, maxEntries);
        }
      }
    } catch (e) {
      history = [];
    }
  }

  let currentIndex = -1;
  let savedDraft = "";

  function saveToStorage() {
    if (typeof window !== "undefined" && window.localStorage && storageKey) {
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(history.slice(0, maxEntries)));
      } catch (e) {
        // Storage quota or error; ignore silently
      }
    }
  }

  function push(prompt) {
    const val = String(prompt || "").trim();
    if (!val) return;

    // Deduplicate consecutive repeats
    if (history[0] !== val) {
      history.unshift(val);
      if (history.length > maxEntries) {
        history = history.slice(0, maxEntries);
      }
      saveToStorage();
    }
    currentIndex = -1;
    savedDraft = "";
  }

  function navigate(direction, currentText = "") {
    if (!history.length) return null;

    if (direction === "up") {
      if (currentIndex === -1) {
        savedDraft = currentText;
      }
      if (currentIndex < history.length - 1) {
        currentIndex++;
        return history[currentIndex];
      }
      return history[currentIndex]; // At oldest entry
    }

    if (direction === "down") {
      if (currentIndex > 0) {
        currentIndex--;
        return history[currentIndex];
      }
      if (currentIndex === 0) {
        currentIndex = -1;
        return savedDraft;
      }
      return null; // Already at live draft
    }

    return null;
  }

  function reset() {
    currentIndex = -1;
    savedDraft = "";
  }

  function getHistory() {
    return history.slice();
  }

  function setHistory(items) {
    if (Array.isArray(items)) {
      history = items.slice(0, maxEntries);
      saveToStorage();
    }
  }

  function seedHistory(items) {
    if (!Array.isArray(items)) return;
    let modified = false;
    for (const item of items) {
      const val = String(
        typeof item === "string"
          ? item
          : item?.task || item?.text || item?.prompt || item?.title || ""
      ).trim();
      if (!val) continue;
      if (!history.includes(val)) {
        history.push(val);
        modified = true;
      }
    }
    if (history.length > maxEntries) {
      history = history.slice(0, maxEntries);
    }
    if (modified) {
      saveToStorage();
    }
  }

  return {
    push,
    navigate,
    reset,
    getHistory,
    setHistory,
    seedHistory,
    get currentIndex() {
      return currentIndex;
    },
  };
}

/**
 * Reactive composable for managing prompt autocomplete (@file & /template) and history recall.
 * @param {{ storageKey?: string, onUpdateText?: (newText: string) => void }} [options={}]
 */
export function usePromptAutocomplete({ storageKey = "", onUpdateText = null } = {}) {
  const popoverVisible = ref(false);
  const popoverType = ref("mention"); // "mention" | "template"
  const popoverItems = ref([]);
  const popoverIndex = ref(0);
  const activeTrigger = ref(null);

  const historyManager = createHistoryManager({ storageKey });

  // Background warm-up of workspace files cache in browser environment
  if (typeof window !== "undefined") {
    const cached = getCachedFiles();
    if (!cached || !cached.length) {
      fetchWorkspaceFiles().catch(() => {});
    }
  }

  async function updateSuggestions(text, cursorPos) {
    const trigger = parseAutocompleteTrigger(text, cursorPos);
    if (!trigger.active) {
      popoverVisible.value = false;
      activeTrigger.value = null;
      return;
    }

    activeTrigger.value = trigger;
    if (trigger.type === "mention") {
      popoverType.value = "mention";
      let files = getCachedFiles();
      if (!files || !files.length) {
        files = await fetchWorkspaceFiles();
      }
      popoverItems.value = filterFiles(trigger.query, files, 20);
      popoverVisible.value = true;
      popoverIndex.value = 0;
    } else if (trigger.type === "template") {
      popoverType.value = "template";
      popoverItems.value = filterTemplates(trigger.query);
      popoverVisible.value = true;
      popoverIndex.value = 0;
    }
  }

  function applySelectedItem(item, currentText, textareaEl) {
    if (!activeTrigger.value || !item) return currentText;
    const { newText, newCursorPos } = applySuggestion(currentText, activeTrigger.value, item);
    popoverVisible.value = false;
    activeTrigger.value = null;

    if (typeof onUpdateText === "function") {
      onUpdateText(newText);
    }

    nextTick(() => {
      if (textareaEl) {
        textareaEl.focus();
        textareaEl.setSelectionRange(newCursorPos, newCursorPos);
      }
    });

    return newText;
  }

  function handleKeydown(event, currentText, textareaEl) {
    // 1. If popover is active, intercept navigation / selection / dismissal
    if (popoverVisible.value) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        const len = popoverItems.value.length;
        if (len > 0) {
          popoverIndex.value = (popoverIndex.value + 1) % len;
        }
        return { handled: true };
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        const len = popoverItems.value.length;
        if (len > 0) {
          popoverIndex.value = (popoverIndex.value - 1 + len) % len;
        }
        return { handled: true };
      }
      if (event.key === "Enter" || event.key === "Tab") {
        if (popoverItems.value.length > 0) {
          event.preventDefault();
          const selected = popoverItems.value[popoverIndex.value] || popoverItems.value[0];
          const newText = applySelectedItem(selected, currentText, textareaEl);
          return { handled: true, text: newText };
        }
      }
      if (event.key === "Escape") {
        event.preventDefault();
        popoverVisible.value = false;
        activeTrigger.value = null;
        return { handled: true };
      }
    }

    // 2. If popover is NOT active, handle History Quick-Recall (ArrowUp / ArrowDown)
    const cursorPos = textareaEl ? textareaEl.selectionStart : 0;
    const isAtStart = cursorPos === 0 || !String(currentText || "").trim();
    const isAtEnd = cursorPos === String(currentText || "").length || !String(currentText || "").trim();

    if (event.key === "ArrowUp" && isAtStart) {
      const recalled = historyManager.navigate("up", currentText);
      if (recalled !== null && recalled !== undefined) {
        event.preventDefault();
        if (typeof onUpdateText === "function") {
          onUpdateText(recalled);
        }
        nextTick(() => {
          if (textareaEl) {
            textareaEl.focus();
            textareaEl.setSelectionRange(recalled.length, recalled.length);
          }
        });
        return { handled: true, text: recalled };
      }
    }

    if (event.key === "ArrowDown" && isAtEnd) {
      const recalled = historyManager.navigate("down", currentText);
      if (recalled !== null && recalled !== undefined) {
        event.preventDefault();
        if (typeof onUpdateText === "function") {
          onUpdateText(recalled);
        }
        nextTick(() => {
          if (textareaEl) {
            textareaEl.focus();
            textareaEl.setSelectionRange(recalled.length, recalled.length);
          }
        });
        return { handled: true, text: recalled };
      }
    }

    return { handled: false };
  }

  function pushHistory(text) {
    historyManager.push(text);
  }

  function closePopover() {
    popoverVisible.value = false;
    activeTrigger.value = null;
  }

  function seedHistory(items) {
    historyManager.seedHistory(items);
  }

  return {
    popoverVisible,
    popoverType,
    popoverItems,
    popoverIndex,
    activeTrigger,
    historyManager,
    updateSuggestions,
    applySelectedItem,
    handleKeydown,
    pushHistory,
    seedHistory,
    closePopover,
  };
}

