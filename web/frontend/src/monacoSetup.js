// AETHER Code Editor: setup Monaco Editor (sekali saja, lazy).
//
// Module ini HANYA di-import secara dinamis saat editor pertama kali dibuka
// (lihat components/CodeEditor.vue). Alasannya:
//   - bundle utama Workbench tidak ikut membawa Monaco (~MB),
//   - render tanpa browser (SSR/verifier) tidak menyentuh Worker/DOM.
//
// Yang diurus di sini:
//   1. Worker Monaco (bundler-aware via `?worker` dari Vite).
//   2. Theme "aether-dark" agar warna editor konsisten dengan visual AETHER.
//
// Tidak ada LSP / language server / subsystem kedua: hanya konfigurasi Monaco.

import * as monaco from "monaco-editor";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import JsonWorker from "monaco-editor/esm/vs/language/json/json.worker?worker";
import CssWorker from "monaco-editor/esm/vs/language/css/css.worker?worker";
import HtmlWorker from "monaco-editor/esm/vs/language/html/html.worker?worker";
import TsWorker from "monaco-editor/esm/vs/language/typescript/ts.worker?worker";

/** Nama theme Monaco AegisCode (dark, konsisten dengan --bg-panel/--accent). */
export const AEGIS_THEME = "aegis-dark";
/** Nama theme Monaco AegisCode (light, konsisten dengan [data-theme="light"]). */
export const AEGIS_LIGHT_THEME = "aegis-light";

export const AETHER_THEME = AEGIS_THEME;
export const AETHER_LIGHT_THEME = AEGIS_LIGHT_THEME;

/** Opsi editor default. Fitur bawaan Monaco (folding, find/replace, multi
 *  cursor, minimap, shortcut standar, autocomplete language service) aktif
 *  secara default; di sini hanya dipastikan eksplisit. */
export const EDITOR_OPTIONS = {
  theme: AEGIS_THEME,
  automaticLayout: false, // layout diurus resize handler sendiri (anti leak)
  minimap: { enabled: true },
  folding: true,
  lineNumbers: "on",
  renderWhitespace: "selection",
  fontSize: 13,
  fontFamily:
    "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace",
  tabSize: 2,
  scrollBeyondLastLine: false,
  smoothScrolling: true,
  cursorBlinking: "smooth",
  multiCursorModifier: "alt",
  find: { addExtraSpaceOnTop: false },
  fixedOverflowWidgets: true,
};

let configured = false;

/**
 * Konfigurasi worker + theme (idempotent) lalu kembalikan namespace Monaco.
 *
 * @returns {typeof import("monaco-editor")} namespace Monaco siap dipakai.
 */
export function getMonaco() {
  if (!configured) {
    // Worker: Monaco memilih worker berdasarkan label bahasa. Label yang tidak
    // punya worker khusus memakai editor.worker (syntax highlighting dsb).
    self.MonacoEnvironment = {
      getWorker(_moduleId, label) {
        switch (label) {
          case "json":
            return new JsonWorker();
          case "css":
          case "scss":
          case "less":
            return new CssWorker();
          case "html":
          case "handlebars":
          case "razor":
            return new HtmlWorker();
          case "typescript":
          case "javascript":
            return new TsWorker();
          default:
            return new EditorWorker();
        }
      },
    };

    monaco.editor.defineTheme(AETHER_THEME, {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "comment", foreground: "928374", fontStyle: "italic" },
        { token: "keyword", foreground: "fb4934" },
        { token: "string", foreground: "b8bb26" },
        { token: "number", foreground: "d3869b" },
        { token: "regexp", foreground: "fe8019" },
        { token: "type", foreground: "fabd2f" },
        { token: "class", foreground: "fabd2f" },
        { token: "function", foreground: "8ec07c" },
        { token: "variable", foreground: "83a598" },
        { token: "constant", foreground: "d3869b" },
        { token: "delimiter", foreground: "ebdbb2" },
        { token: "tag", foreground: "83a598" },
        { token: "attribute.name", foreground: "fabd2f" },
        { token: "attribute.value", foreground: "b8bb26" },
      ],
      colors: {
        "editor.background": "#282828",
        "editor.foreground": "#ebdbb2",
        "editorGutter.background": "#282828",
        "editorLineNumber.foreground": "#7c6f64",
        "editorLineNumber.activeForeground": "#8ec07c",
        "editor.selectionBackground": "#50494580",
        "editor.inactiveSelectionBackground": "#3c383680",
        "editorCursor.foreground": "#ebdbb2",
        "editorIndentGuide.background1": "#3c3836",
        "editorIndentGuide.activeBackground1": "#7c6f64",
        "minimap.background": "#1d2021",
        "editorWidget.background": "#32302f",
        "editorWidget.border": "#504945",
        "scrollbarSlider.background": "#50494560",
        "scrollbarSlider.hoverBackground": "#7c6f6480",
      },
    });

    monaco.editor.defineTheme(AETHER_LIGHT_THEME, {
      base: "vs",
      inherit: true,
      rules: [
        { token: "comment", foreground: "928374", fontStyle: "italic" },
        { token: "keyword", foreground: "9d0006" },
        { token: "string", foreground: "79740e" },
        { token: "number", foreground: "8f3f71" },
        { token: "regexp", foreground: "af3a03" },
        { token: "type", foreground: "b57614" },
        { token: "class", foreground: "b57614" },
        { token: "function", foreground: "427b58" },
        { token: "variable", foreground: "076678" },
        { token: "constant", foreground: "8f3f71" },
        { token: "delimiter", foreground: "3c3836" },
        { token: "tag", foreground: "076678" },
        { token: "attribute.name", foreground: "b57614" },
        { token: "attribute.value", foreground: "79740e" },
      ],
      colors: {
        "editor.background": "#fbf1c7",
        "editor.foreground": "#3c3836",
        "editorGutter.background": "#fbf1c7",
        "editorLineNumber.foreground": "#a89984",
        "editorLineNumber.activeForeground": "#427b58",
        "editor.selectionBackground": "#d5c4a180",
        "editor.inactiveSelectionBackground": "#ebdbb280",
        "editorCursor.foreground": "#3c3836",
        "editorIndentGuide.background1": "#ebdbb2",
        "editorIndentGuide.activeBackground1": "#a89984",
        "minimap.background": "#f9f5d7",
        "editorWidget.background": "#f2e5bc",
        "editorWidget.border": "#d5c4a1",
        "scrollbarSlider.background": "#d5c4a160",
        "scrollbarSlider.hoverBackground": "#bdae9380",
      },
    });

    if (monaco.languages && monaco.languages.json && monaco.languages.json.jsonDefaults) {
      monaco.languages.json.jsonDefaults.setDiagnosticsOptions({
        validate: true,
        allowComments: false,
        trailingCommas: "error",
      });
    }

    if (monaco.languages && !monaco.languages.getLanguages().some((l) => l.id === "gitignore")) {
      monaco.languages.register({ id: "gitignore" });
      monaco.languages.setMonarchTokensProvider("gitignore", {
        tokenizer: {
          root: [
            [/^\s*#.*$/, "comment"],
            [/^!.*$/, "keyword"],
            [/\*\*|\*/, "operator"],
          ],
        },
      });
    }

    configured = true;
  }
  return monaco;
}
