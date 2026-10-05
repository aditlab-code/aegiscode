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
      rules: [],
      colors: {
        "editor.background": "#14121e",
        "editorGutter.background": "#14121e",
        "editorLineNumber.foreground": "#756e8b",
        "editorLineNumber.activeForeground": "#34d399",
        "editor.selectionBackground": "#a855f73d",
        "editorCursor.foreground": "#34d399",
        "editorIndentGuide.background1": "#2b263b",
        "editorIndentGuide.activeBackground1": "#a855f7",
        "minimap.background": "#0f0e15",
        "editorWidget.background": "#16151f",
        "editorWidget.border": "#38324a",
        "scrollbarSlider.background": "#5b4f7a50",
        "scrollbarSlider.hoverBackground": "#5b4f7a80",
      },
    });

    monaco.editor.defineTheme(AETHER_LIGHT_THEME, {
      base: "vs",
      inherit: true,
      rules: [],
      colors: {
        "editor.background": "#fdfbf7",
        "editorGutter.background": "#fdfbf7",
        "editorLineNumber.foreground": "#785e4c",
        "editorLineNumber.activeForeground": "#b45309",
        "editor.selectionBackground": "#d9770628",
        "editorCursor.foreground": "#180c06",
        "editorIndentGuide.background1": "#dcd1c3",
        "editorIndentGuide.activeBackground1": "#d97706",
        "minimap.background": "#f4ede4",
        "editorWidget.background": "#fbf8f2",
        "editorWidget.border": "#c8bba9",
        "scrollbarSlider.background": "#c8bba960",
        "scrollbarSlider.hoverBackground": "#9a602c80",
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
