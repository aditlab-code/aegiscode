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

    // Tokyo Night Dark
    monaco.editor.defineTheme("tokyo-night-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "comment", foreground: "565f89", fontStyle: "italic" },
        { token: "keyword", foreground: "bb9af7" },
        { token: "string", foreground: "9ece6a" },
        { token: "number", foreground: "ff9e64" },
        { token: "function", foreground: "7aa2f7" },
        { token: "variable", foreground: "c0caf5" },
        { token: "delimiter", foreground: "9aa5ce" },
      ],
      colors: {
        "editor.background": "#1a1b26",
        "editor.foreground": "#c0caf5",
        "editorGutter.background": "#1a1b26",
        "editorLineNumber.foreground": "#565f89",
        "editorLineNumber.activeForeground": "#7aa2f7",
        "editor.selectionBackground": "#7aa2f726",
        "minimap.background": "#16161e",
        "editorWidget.background": "#1f2335",
      },
    });

    // Tokyo Night Light
    monaco.editor.defineTheme("tokyo-night-light", {
      base: "vs",
      inherit: true,
      rules: [
        { token: "comment", foreground: "8990b3", fontStyle: "italic" },
        { token: "keyword", foreground: "5a4a78" },
        { token: "string", foreground: "485e30" },
        { token: "number", foreground: "8c6c3e" },
        { token: "function", foreground: "34548a" },
        { token: "variable", foreground: "343b58" },
        { token: "delimiter", foreground: "565a6e" },
      ],
      colors: {
        "editor.background": "#d5d6db",
        "editor.foreground": "#343b58",
        "editorGutter.background": "#d5d6db",
        "editorLineNumber.foreground": "#8990b3",
        "editorLineNumber.activeForeground": "#34548a",
        "editor.selectionBackground": "#34548a26",
        "minimap.background": "#cbccd1",
        "editorWidget.background": "#e1e2e7",
      },
    });

    // Nordic Dark
    monaco.editor.defineTheme("nord-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "comment", foreground: "4c566a", fontStyle: "italic" },
        { token: "keyword", foreground: "81a1c1" },
        { token: "string", foreground: "a3be8c" },
        { token: "number", foreground: "b48ead" },
        { token: "function", foreground: "88c0d0" },
        { token: "variable", foreground: "eceff4" },
        { token: "delimiter", foreground: "d8dee9" },
      ],
      colors: {
        "editor.background": "#2e3440",
        "editor.foreground": "#eceff4",
        "editorGutter.background": "#2e3440",
        "editorLineNumber.foreground": "#4c566a",
        "editorLineNumber.activeForeground": "#88c0d0",
        "editor.selectionBackground": "#88c0d026",
        "minimap.background": "#242933",
        "editorWidget.background": "#3b4252",
      },
    });

    // Nordic Light
    monaco.editor.defineTheme("nord-light", {
      base: "vs",
      inherit: true,
      rules: [
        { token: "comment", foreground: "7b88a1", fontStyle: "italic" },
        { token: "keyword", foreground: "81a1c1" },
        { token: "string", foreground: "678650" },
        { token: "number", foreground: "b48ead" },
        { token: "function", foreground: "5e81ac" },
        { token: "variable", foreground: "2e3440" },
        { token: "delimiter", foreground: "4c566a" },
      ],
      colors: {
        "editor.background": "#eceff4",
        "editor.foreground": "#2e3440",
        "editorGutter.background": "#eceff4",
        "editorLineNumber.foreground": "#7b88a1",
        "editorLineNumber.activeForeground": "#5e81ac",
        "editor.selectionBackground": "#5e81ac26",
        "minimap.background": "#e5e9f0",
        "editorWidget.background": "#e5e9f0",
      },
    });

    // Atom One Dark
    monaco.editor.defineTheme("atom-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "comment", foreground: "5c6370", fontStyle: "italic" },
        { token: "keyword", foreground: "c678dd" },
        { token: "string", foreground: "98c379" },
        { token: "number", foreground: "d19a66" },
        { token: "function", foreground: "61afef" },
        { token: "variable", foreground: "abb2bf" },
        { token: "delimiter", foreground: "828997" },
      ],
      colors: {
        "editor.background": "#282c34",
        "editor.foreground": "#abb2bf",
        "editorGutter.background": "#282c34",
        "editorLineNumber.foreground": "#5c6370",
        "editorLineNumber.activeForeground": "#61afef",
        "editor.selectionBackground": "#61afef26",
        "minimap.background": "#1e2227",
        "editorWidget.background": "#21252b",
      },
    });

    // Atom One Light
    monaco.editor.defineTheme("atom-light", {
      base: "vs",
      inherit: true,
      rules: [
        { token: "comment", foreground: "a0a1a7", fontStyle: "italic" },
        { token: "keyword", foreground: "a626a4" },
        { token: "string", foreground: "50a14f" },
        { token: "number", foreground: "c18401" },
        { token: "function", foreground: "4078f2" },
        { token: "variable", foreground: "383a42" },
        { token: "delimiter", foreground: "696c77" },
      ],
      colors: {
        "editor.background": "#fafafa",
        "editor.foreground": "#383a42",
        "editorGutter.background": "#fafafa",
        "editorLineNumber.foreground": "#a0a1a7",
        "editorLineNumber.activeForeground": "#4078f2",
        "editor.selectionBackground": "#4078f226",
        "minimap.background": "#f0f0f0",
        "editorWidget.background": "#f0f0f0",
      },
    });

    // Default aliases
    monaco.editor.defineTheme("default-dark", { base: "vs-dark", inherit: true, rules: [], colors: { "editor.background": "#181922" } });
    monaco.editor.defineTheme("default-light", { base: "vs", inherit: true, rules: [], colors: { "editor.background": "#eae5f4" } });

    if (monaco.languages && monaco.languages.json && monaco.languages.json.jsonDefaults) {
      monaco.languages.json.jsonDefaults.setDiagnosticsOptions({
        validate: true,
        allowComments: false,
        trailingCommas: "error",
      });
    }

    if (monaco.languages && monaco.languages.typescript) {
      const tsDefaults = monaco.languages.typescript.typescriptDefaults;
      const jsDefaults = monaco.languages.typescript.javascriptDefaults;
      if (tsDefaults) {
        tsDefaults.setDiagnosticsOptions({
          noSemanticValidation: true,
          noSyntaxValidation: true,
          noSuggestionDiagnostics: true,
        });
        if (tsDefaults.setCompilerOptions) {
          tsDefaults.setCompilerOptions({
            jsx: (monaco.languages.typescript.JsxEmit && monaco.languages.typescript.JsxEmit.ReactJSX) || 4,
            allowNonTsExtensions: true,
            target: (monaco.languages.typescript.ScriptTarget && monaco.languages.typescript.ScriptTarget.Latest) || 99,
          });
        }
      }
      if (jsDefaults) {
        jsDefaults.setDiagnosticsOptions({
          noSemanticValidation: true,
          noSyntaxValidation: true,
          noSuggestionDiagnostics: true,
        });
      }
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
