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

    monaco.editor.defineTheme(AEGIS_THEME, {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "comment", foreground: "565f89", fontStyle: "italic" },
        { token: "keyword", foreground: "bb9af7" },
        { token: "string", foreground: "9ece6a" },
        { token: "number", foreground: "ff9e64" },
        { token: "regexp", foreground: "b4f9f8" },
        { token: "type", foreground: "2ac3de" },
        { token: "class", foreground: "2ac3de" },
        { token: "function", foreground: "7aa2f7" },
        { token: "variable", foreground: "c0caf5" },
        { token: "constant", foreground: "ff9e64" },
        { token: "delimiter", foreground: "89ddff" },
        { token: "tag", foreground: "f7768e" },
        { token: "attribute.name", foreground: "73daca" },
        { token: "attribute.value", foreground: "9ece6a" },
      ],
      colors: {
        "editor.background": "#24283b",
        "editor.foreground": "#c0caf5",
        "editorGutter.background": "#24283b",
        "editorLineNumber.foreground": "#363b54",
        "editorLineNumber.activeForeground": "#7aa2f7",
        "editor.selectionBackground": "#515c7e4d",
        "editor.inactiveSelectionBackground": "#515c7e25",
        "editorCursor.foreground": "#c0caf5",
        "editorIndentGuide.background1": "#232433",
        "editorIndentGuide.activeBackground1": "#363b54",
        "minimap.background": "#1a1b26",
        "editorWidget.background": "#1f2335",
        "editorWidget.border": "#16161e",
        "scrollbarSlider.background": "#868bc415",
        "scrollbarSlider.hoverBackground": "#868bc425",
      },
    });

    monaco.editor.defineTheme(AEGIS_LIGHT_THEME, {
      base: "vs",
      inherit: true,
      rules: [
        { token: "comment", foreground: "9699a3", fontStyle: "italic" },
        { token: "keyword", foreground: "8c4351" },
        { token: "string", foreground: "485e30" },
        { token: "number", foreground: "8f5e15" },
        { token: "regexp", foreground: "0f4b6e" },
        { token: "type", foreground: "0f4b6e" },
        { token: "class", foreground: "0f4b6e" },
        { token: "function", foreground: "2959aa" },
        { token: "variable", foreground: "343b59" },
        { token: "constant", foreground: "8f5e15" },
        { token: "delimiter", foreground: "2959aa" },
        { token: "tag", foreground: "8c4351" },
        { token: "attribute.name", foreground: "2e7de9" },
        { token: "attribute.value", foreground: "485e30" },
      ],
      colors: {
        "editor.background": "#e6e7ed",
        "editor.foreground": "#343b59",
        "editorGutter.background": "#e6e7ed",
        "editorLineNumber.foreground": "#9da0ab",
        "editorLineNumber.activeForeground": "#2959aa",
        "editor.selectionBackground": "#acb0bf40",
        "editor.inactiveSelectionBackground": "#acb0bf33",
        "editorCursor.foreground": "#363c4d",
        "editorIndentGuide.background1": "#d0d4e3",
        "editorIndentGuide.activeBackground1": "#bdc1cf",
        "minimap.background": "#d6d8df",
        "editorWidget.background": "#e6e7ed",
        "editorWidget.border": "#c1c2c7",
        "scrollbarSlider.background": "#90929625",
        "scrollbarSlider.hoverBackground": "#90929640",
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
