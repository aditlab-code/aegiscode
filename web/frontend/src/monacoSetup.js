// Aegis Code Editor: setup Monaco Editor (sekali saja, lazy).
//
// Module ini HANYA di-import secara dinamis saat editor pertama kali dibuka
// (lihat components/CodeEditor.vue). Alasannya:
//   - bundle utama Workbench tidak ikut membawa Monaco (~MB),
//   - render tanpa browser (SSR/verifier) tidak menyentuh Worker/DOM.
//
// Yang diurus di sini:
//   1. Worker Monaco (bundler-aware via `?worker` dari Vite).
//   2. Theme "aegis-dark" agar warna editor konsisten dengan visual AegisCode.
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
  fontFamily: "'JetBrains Mono', monospace",
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

    monaco.editor.defineTheme(AEGIS_THEME, {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "comment", foreground: "8c849a", fontStyle: "italic" },
        { token: "keyword", foreground: "c1a4df" },
        { token: "string", foreground: "a2c9a3" },
        { token: "number", foreground: "fdba74" },
        { token: "regexp", foreground: "91b8d7" },
        { token: "type", foreground: "91b8d7" },
        { token: "class", foreground: "91b8d7" },
        { token: "function", foreground: "b5a1ed" },
        { token: "variable", foreground: "dedee9" },
        { token: "constant", foreground: "fdba74" },
        { token: "delimiter", foreground: "bcbcca" },
        { token: "tag", foreground: "f472b6" },
        { token: "attribute.name", foreground: "c1a4df" },
        { token: "attribute.value", foreground: "a2c9a3" },
      ],
      colors: {
        "editor.background": "#1b1c26",
        "editor.foreground": "#dedee9",
        "editorGutter.background": "#1b1c26",
        "editorLineNumber.foreground": "#8c849a",
        "editorLineNumber.activeForeground": "#b5a1ed",
        "editor.selectionBackground": "#b5a1ed26",
        "editor.inactiveSelectionBackground": "#b5a1ed14",
        "editorCursor.foreground": "#dedee9",
        "editor.lineHighlightBackground": "#ffffff06",
        "editorIndentGuide.background1": "#ffffff0f",
        "editorIndentGuide.activeBackground1": "#ffffff20",
        "minimap.background": "#181922",
        "editorWidget.background": "#292a36",
        "editorWidget.border": "#ffffff20",
        "scrollbarSlider.background": "#ffffff10",
        "scrollbarSlider.hoverBackground": "#ffffff20",
      },
    });

    monaco.editor.defineTheme(AEGIS_LIGHT_THEME, {
      base: "vs",
      inherit: true,
      rules: [
        { token: "comment", foreground: "95899f", fontStyle: "italic" },
        { token: "keyword", foreground: "9a60ad" },
        { token: "string", foreground: "628c5a" },
        { token: "number", foreground: "c2410c" },
        { token: "regexp", foreground: "4e7f9b" },
        { token: "type", foreground: "4e7f9b" },
        { token: "class", foreground: "4e7f9b" },
        { token: "function", foreground: "8261bb" },
        { token: "variable", foreground: "333044" },
        { token: "constant", foreground: "c2410c" },
        { token: "delimiter", foreground: "555168" },
        { token: "tag", foreground: "db2777" },
        { token: "attribute.name", foreground: "9a60ad" },
        { token: "attribute.value", foreground: "628c5a" },
      ],
      colors: {
        "editor.background": "#f8f6fc",
        "editor.foreground": "#333044",
        "editorGutter.background": "#f8f6fc",
        "editorLineNumber.foreground": "#95899f",
        "editorLineNumber.activeForeground": "#8261bb",
        "editor.selectionBackground": "#8261bb22",
        "editor.inactiveSelectionBackground": "#8261bb12",
        "editorCursor.foreground": "#333044",
        "editor.lineHighlightBackground": "#8261bb08",
        "editorIndentGuide.background1": "#49406115",
        "editorIndentGuide.activeBackground1": "#49406130",
        "minimap.background": "#f0edf7",
        "editorWidget.background": "#f5f3fa",
        "editorWidget.border": "#49406120",
        "scrollbarSlider.background": "#49406110",
        "scrollbarSlider.hoverBackground": "#49406120",
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
