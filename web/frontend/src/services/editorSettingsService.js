/**
 * editorSettingsService.js — Centralized Text Editor Preferences for AETHER Workbench.
 *
 * Manages typography, layout, wrap, and minimap settings for Monaco Editor.
 * SSR-safe, client-persisted in localStorage with event broadcasting.
 */

export const EDITOR_SETTINGS_KEY = "aether-editor-settings";
export const EDITOR_SETTINGS_EVENT = "aether-editor-settings-change";

export const LOCAL_FONTS = Object.freeze([
  { label: "Default Coding Stack", value: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace" },
  { label: "Fira Code", value: "'Fira Code', monospace" },
  { label: "JetBrains Mono", value: "'JetBrains Mono', monospace" },
  { label: "Cascadia Code", value: "'Cascadia Code', monospace" },
  { label: "SF Mono", value: "'SF Mono', 'SF Pro', monospace" },
  { label: "Menlo", value: "Menlo, monospace" },
  { label: "Monaco", value: "Monaco, monospace" },
  { label: "Consolas", value: "Consolas, monospace" },
  { label: "Source Code Pro", value: "'Source Code Pro', monospace" },
  { label: "Ubuntu Mono", value: "'Ubuntu Mono', monospace" },
  { label: "Liberation Mono", value: "'Liberation Mono', monospace" },
]);

export const DEFAULT_EDITOR_SETTINGS = Object.freeze({
  fontSize: 13,
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace",
  wordWrap: "on",
  lineHeight: 20,
  minimap: {
    enabled: true,
    side: "right",
    renderCharacters: true,
    scale: 1,
  },
});

/**
 * Safely read stored editor settings across SSR and client contexts.
 * @returns {object} editor preferences
 */
export function getStoredEditorSettings() {
  if (typeof window === "undefined" || !window.localStorage) {
    return { ...DEFAULT_EDITOR_SETTINGS };
  }
  try {
    const raw = window.localStorage.getItem(EDITOR_SETTINGS_KEY);
    if (!raw) return { ...DEFAULT_EDITOR_SETTINGS };
    const parsed = JSON.parse(raw);
    return {
      fontSize: typeof parsed.fontSize === "number" ? parsed.fontSize : DEFAULT_EDITOR_SETTINGS.fontSize,
      fontFamily: typeof parsed.fontFamily === "string" && parsed.fontFamily ? parsed.fontFamily : DEFAULT_EDITOR_SETTINGS.fontFamily,
      wordWrap: ["on", "off", "wordWrapColumn", "bounded"].includes(parsed.wordWrap) ? parsed.wordWrap : DEFAULT_EDITOR_SETTINGS.wordWrap,
      lineHeight: typeof parsed.lineHeight === "number" ? parsed.lineHeight : DEFAULT_EDITOR_SETTINGS.lineHeight,
      minimap: {
        enabled: typeof parsed.minimap?.enabled === "boolean" ? parsed.minimap.enabled : DEFAULT_EDITOR_SETTINGS.minimap.enabled,
        side: ["right", "left"].includes(parsed.minimap?.side) ? parsed.minimap.side : DEFAULT_EDITOR_SETTINGS.minimap.side,
        renderCharacters: typeof parsed.minimap?.renderCharacters === "boolean" ? parsed.minimap.renderCharacters : DEFAULT_EDITOR_SETTINGS.minimap.renderCharacters,
        scale: typeof parsed.minimap?.scale === "number" ? parsed.minimap.scale : DEFAULT_EDITOR_SETTINGS.minimap.scale,
      },
    };
  } catch (_) {
    return { ...DEFAULT_EDITOR_SETTINGS };
  }
}

/**
 * Persist editor settings and broadcast update event to active editors.
 * @param {object} settings
 */
export function saveEditorSettings(settings) {
  const merged = { ...getStoredEditorSettings(), ...(settings || {}) };
  if (typeof window !== "undefined" && window.localStorage) {
    try {
      window.localStorage.setItem(EDITOR_SETTINGS_KEY, JSON.stringify(merged));
    } catch (_) {
      // Ignore quota errors in restricted mode
    }
    window.dispatchEvent(new CustomEvent(EDITOR_SETTINGS_EVENT, { detail: merged }));
  }
  return merged;
}

/**
 * Translate settings into Monaco Editor options object.
 * @param {object} settings
 * @returns {object}
 */
export function toMonacoOptions(settings) {
  const s = settings || getStoredEditorSettings();
  return {
    fontSize: s.fontSize,
    fontFamily: s.fontFamily,
    wordWrap: s.wordWrap,
    lineHeight: s.lineHeight,
    minimap: {
      enabled: s.minimap.enabled,
      side: s.minimap.side,
      renderCharacters: s.minimap.renderCharacters,
      scale: s.minimap.scale,
    },
  };
}
