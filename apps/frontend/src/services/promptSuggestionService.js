import { ref, nextTick } from "vue";
import { filterFiles } from "./commandPaletteService.js";
import { getCachedFiles, fetchWorkspaceFiles } from "./fileCacheService.js";

/**
 * Prompt Templates & Autocomplete Suggestion Service.
 * Implements Roadmap Item #5 (Mention popover @file, template prompt /shortcuts, history recall).
 */

export const DEFAULT_SKILL_TEMPLATES = [
  {
    id: "spec",
    command: "/spec",
    skillId: "spec-driven-development",
    label: "Spec-Driven Development",
    description: "Buat spesifikasi terstruktur sebelum menulis kode",
    template: "/spec [Jelaskan spesifikasi fitur/sistem]: ",
  },
  {
    id: "plan",
    command: "/plan",
    skillId: "planning-and-task-breakdown",
    label: "Planning & Task Breakdown",
    description: "Pecah pekerjaan menjadi tugas terurut dan terverifikasi",
    template: "/plan [Rincian scope/arsitektur]: ",
  },
  {
    id: "build",
    command: "/build",
    skillId: "incremental-implementation",
    label: "Incremental Implementation",
    description: "Implementasi perubahan bertahap dalam irisan tipis terverifikasi",
    template: "/build [Komponen/tugas yang diimplementasikan]: ",
  },
  {
    id: "test",
    command: "/test",
    skillId: "test-driven-development",
    label: "Test-Driven Development",
    description: "Tegakkan siklus red-green-refactor dan pastikan 100% tes lolos",
    template: "/test [Modul/skenario yang diuji]: ",
  },
  {
    id: "interview-me",
    command: "/interview-me",
    skillId: "interview-me",
    label: "Interview Me (Grill-Me)",
    description: "Ekstraksi kebutuhan dan intensi mendalam melalui tanya jawab bertahap",
    template: "/interview-me [Ide/kebutuhan yang ingin diekstrak]: ",
  },
  {
    id: "review",
    command: "/review",
    skillId: "code-review-and-quality",
    label: "Code Review & Quality",
    description: "Evaluasi kualitas kode multi-axis (5 dimensi)",
    template: "/review [Berkas/diff yang direview]: ",
  },
  {
    id: "constraints",
    command: "/constraints",
    skillId: "constraint-driven-development",
    label: "Constraint-Driven Development",
    description: "Tetapkan standar kualitas proyek sebagai kontrak di CONSTRAINTS.md",
    template: "/constraints [Standar kualitas/aturan batas]: ",
  },
  {
    id: "code-simplify",
    command: "/code-simplify",
    skillId: "code-simplification",
    label: "Code Simplification",
    description: "Sederhanakan kode untuk kejelasan tanpa mengubah perilaku fungsi",
    template: "/code-simplify [Kode/fungsi yang disederhanakan]: ",
  },
  {
    id: "ship",
    command: "/ship",
    skillId: "shipping-and-launch",
    label: "Shipping & Launch",
    description: "Persiapan rilis produksi dan verifikasi pre-launch checklist",
    template: "/ship [Target rilis/lingkungan deploy]: ",
  },
];

export let PROMPT_TEMPLATES = [...DEFAULT_SKILL_TEMPLATES];

let cachedDynamicSkills = null;

/**
 * Fetch dynamic skill templates from backend API.
 * @param {string} [workspacePath=""]
 * @returns {Promise<Array<object>>}
 */
export async function fetchSkillTemplates(workspacePath = "") {
  try {
    const url = workspacePath
      ? `/api/skills/catalog?workspace=${encodeURIComponent(workspacePath)}`
      : "/api/skills/catalog";
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) {
      return PROMPT_TEMPLATES;
    }
    const data = await res.json();
    if (data && Array.isArray(data.skills) && data.skills.length > 0) {
      const dynamicList = data.skills.map((s) => ({
        id: s.id || s.skill_id,
        command: s.command || `/${s.id || s.skill_id}`,
        skillId: s.skill_id,
        label: s.name || s.skill_id,
        description: s.description || "",
        template: s.template || `${s.command || `/${s.id}`} [Instruksi]: `,
      }));
      cachedDynamicSkills = dynamicList;
      PROMPT_TEMPLATES = dynamicList;
      return dynamicList;
    }
  } catch (_err) {
    // Non-blocking fallback to default skill templates
  }
  return PROMPT_TEMPLATES;
}

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
    let mentionSlice = beforeCursor.slice(lastAt + 1);
    const hasBracket = mentionSlice.startsWith("[");
    if (hasBracket) {
      mentionSlice = mentionSlice.slice(1);
    }

    // No whitespace allowed inside the active mention query
    if (isValidBoundary && !/\s/.test(mentionSlice)) {
      return {
        active: true,
        type: "mention",
        triggerChar: hasBracket ? "@[" : "@",
        query: mentionSlice,
        start: lastAt,
        end: safeCursor,
        hasBracket,
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
 * @param {{ start: number, end: number, type: string, hasBracket?: boolean }} trigger
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
    if (trigger.hasBracket) {
      insertContent = `@[${filePath}] `;
    } else {
      insertContent = `@${filePath} `;
    }
  } else if (trigger.type === "template") {
    insertContent = typeof suggestion === "string"
      ? suggestion
      : (suggestion?.template || `${suggestion?.command || ""} `);
  }

  const prefix = text.slice(0, trigger.start);
  let suffix = text.slice(trigger.end);
  if (trigger.hasBracket && suffix.startsWith("]")) {
    suffix = suffix.slice(1);
  }
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
    if (!cachedDynamicSkills) {
      fetchSkillTemplates().catch(() => {});
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
      popoverItems.value = filterTemplates(trigger.query, PROMPT_TEMPLATES);
      popoverVisible.value = true;
      popoverIndex.value = 0;

      // Lazy re-sync dynamic skills jika belum di-cache
      if (!cachedDynamicSkills && typeof window !== "undefined") {
        fetchSkillTemplates()
          .then((latest) => {
            if (activeTrigger.value && activeTrigger.value.type === "template") {
              popoverItems.value = filterTemplates(activeTrigger.value.query, latest);
            }
          })
          .catch(() => {});
      }
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

