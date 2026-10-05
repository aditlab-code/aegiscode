<script setup>
// Aegis Code Editor (Monaco) — modal editor di dalam Workbench.
//
// Dibuka dari File Explorer (klik file / klik kanan -> "Open with Editor") dan
// dari tombol Edit di panel CHANGES. Bukan route/halaman baru dan bukan
// subsystem file manager baru:
//   - daftar file & boundary workspace memakai Explorer/API yang sudah ada,
//   - isi file dibaca/ditulis lewat API file backend existing
//     (ReadFileTool/WriteFileTool Aegis; browser TIDAK menulis file),
//   - modal memakai pola .modal-backdrop/.modal Aegis existing.
//
// Lifecycle Monaco: dibuat saat modal dibuka, di-dispose saat modal ditutup
// (termasuk model + listener + ResizeObserver) supaya tidak ada instance atau
// listener yang menumpuk saat editor dibuka berulang kali untuk file berbeda.
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { readFileContent, writeFileContent } from "../api.js";
import { languageForFile, languageLabel } from "../editorLanguages.js";
import {
  getStoredEditorSettings,
  toMonacoOptions,
  EDITOR_SETTINGS_EVENT,
} from "../services/editorSettingsService.js";
import { validateCodeSyntax } from "../services/diagnosticService.js";

const props = defineProps({
  // Path relatif terhadap root project (dari Explorer, bukan path baru).
  path: { type: String, required: true },
  // Nama file (untuk judul header + deteksi language).
  name: { type: String, default: "" },
  // Mode embedded (terintegrasi di central workspace, bukan modal backdrop).
  embedded: { type: Boolean, default: true },
  // Instance identifier to support split tabs without model URI collision
  instanceId: { type: String, default: "primary" },
});

const emit = defineEmits(["close", "error", "saved", "dirty-change", "cursor-change", "markers-change", "syntax-change"]);

const container = ref(null);
const loading = ref(true);
const loadError = ref("");
const saveError = ref("");
const saving = ref(false);
// Dirty = isi Monaco berbeda dari versi terakhir yang berhasil dibaca/disimpan.
const dirty = ref(false);
const confirmOpen = ref(false);
const cursor = ref({ line: 1, column: 1 });

const instanceUid = `${props.instanceId}-${Math.random().toString(36).slice(2, 8)}`;

const fileName = computed(
  () => props.name || String(props.path || "").split("/").pop() || props.path
);
const language = computed(() => languageForFile(props.name || props.path));
const languageName = computed(() => languageLabel(language.value));

// Instance Monaco + model + listener (di-dispose saat unmount).
let monaco = null;
let editor = null;
let model = null;
let contentSub = null;
let cursorSub = null;
let markerSub = null;
let resizeObserver = null;
let themeObserver = null;
let settingsListener = null;
// "Versi tersimpan" model: dipakai untuk menentukan dirty tanpa string-diff
// (undo kembali ke kondisi tersimpan -> dirty false).
let savedVersionId = null;
// Ditandai saat unmount: mencegah mount Monaco setelah await import() selesai.
let disposed = false;

// Monaco dimuat LAZY (dynamic import): bundle utama Workbench tidak ikut
// membawa Monaco, dan render tanpa browser (SSR/verifier) tidak menyentuhnya.
let monacoModulePromise = null;
function loadMonacoModule() {
  if (!monacoModulePromise) {
    monacoModulePromise = import("../monacoSetup.js");
  }
  return monacoModulePromise;
}

function modelUri(path, instanceId = "") {
  const clean = String(path || "untitled")
    .split("/")
    .map((part) => encodeURIComponent(part))
    .join("/");
  const prefix = instanceId ? `${encodeURIComponent(instanceId)}/` : "";
  return monaco.Uri.parse(`inmemory://aegis/${prefix}${clean}`);
}

function layout() {
  if (editor) editor.layout();
}

// --- Load / mount ------------------------------------------------------------
async function load() {
  loading.value = true;
  loadError.value = "";
  saveError.value = "";
  try {
    const data = await readFileContent(props.path);
    const text = typeof data?.content === "string" ? data.content : "";
    await nextTick();
    await mountEditor(text);
  } catch (e) {
    loadError.value = e.message || "Gagal memuat file.";
    emit("error", loadError.value);
  } finally {
    loading.value = false;
    await nextTick();
    layout();
    setTimeout(() => layout(), 50);
  }
}

async function mountEditor(text) {
  if (!container.value) return;
  const mod = await loadMonacoModule();
  if (disposed || !container.value) return; // modal sudah ditutup saat menunggu
  monaco = mod.getMonaco();
  const uri = modelUri(props.path, instanceUid);
  const existingModel = monaco.editor.getModel(uri);
  if (existingModel) {
    existingModel.dispose();
  }
  model = monaco.editor.createModel(text, language.value, uri);
  const isLight = typeof document !== "undefined" && document.documentElement.dataset.theme === "light";
  const userEditorOpts = toMonacoOptions(getStoredEditorSettings());
  editor = monaco.editor.create(container.value, {
    ...mod.EDITOR_OPTIONS,
    ...userEditorOpts,
    automaticLayout: true,
    theme: isLight ? mod.AEGIS_LIGHT_THEME : mod.AEGIS_THEME,
    model,
  });

  settingsListener = (e) => {
    if (editor && e?.detail) {
      editor.updateOptions(toMonacoOptions(e.detail));
    }
  };
  if (typeof window !== "undefined") {
    window.addEventListener(EDITOR_SETTINGS_EVENT, settingsListener);
  }

  if (typeof MutationObserver !== "undefined" && typeof document !== "undefined") {
    themeObserver = new MutationObserver(() => {
      const lightNow = document.documentElement.dataset.theme === "light";
      monaco.editor.setTheme(lightNow ? mod.AEGIS_LIGHT_THEME : mod.AEGIS_THEME);
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
  }
  savedVersionId = model.getAlternativeVersionId();

  let syntaxTimer = null;
  function runSyntaxCheck() {
    if (syntaxTimer) clearTimeout(syntaxTimer);
    syntaxTimer = setTimeout(() => {
      if (!model || disposed) return;
      const text = model.getValue();
      const syntaxErrors = validateCodeSyntax(text, language.value, props.path);
      emit("syntax-change", { path: props.path, errors: syntaxErrors });
      if (monaco?.editor?.setModelMarkers) {
        const monacoMarkers = syntaxErrors.map((err) => ({
          severity: err.severity === "warning" ? 4 : 8,
          message: err.text,
          startLineNumber: err.line || 1,
          startColumn: err.col || 1,
          endLineNumber: err.line || 1,
          endColumn: (err.col || 1) + 15,
        }));
        monaco.editor.setModelMarkers(model, "aegis-syntax", monacoMarkers);
      }
    }, 200);
  }

  contentSub = model.onDidChangeContent(() => {
    dirty.value = model.getAlternativeVersionId() !== savedVersionId;
    emit("dirty-change", { path: props.path, dirty: dirty.value });
    runSyntaxCheck();
  });
  cursorSub = editor.onDidChangeCursorPosition((e) => {
    cursor.value = { line: e.position.lineNumber, column: e.position.column };
    emit("cursor-change", { line: e.position.lineNumber, column: e.position.column });
  });

  if (monaco?.editor?.onDidChangeMarkers) {
    markerSub = monaco.editor.onDidChangeMarkers((uris) => {
      if (!model || disposed) return;
      const uriStr = model.uri.toString();
      if (uris && uris.some((u) => u.toString() === uriStr)) {
        const markers = monaco.editor.getModelMarkers({ resource: model.uri });
        emit("markers-change", { path: props.path, markers });
      }
    });
    const initMarkers = monaco.editor.getModelMarkers({ resource: uri });
    if (initMarkers && initMarkers.length) {
      emit("markers-change", { path: props.path, markers: initMarkers });
    }
  }

  // Initial syntax scan
  runSyntaxCheck();

  if (typeof ResizeObserver !== "undefined") {
    resizeObserver = new ResizeObserver(() => layout());
    resizeObserver.observe(container.value);
  }
  window.addEventListener("resize", layout);
  // Siap dipakai langsung (keyboard/shortcut) tanpa klik tambahan.
  editor.focus();
  nextTick(() => layout());
  setTimeout(() => layout(), 60);
  setTimeout(() => layout(), 250);
}

function disposeEditor() {
  if (syntaxTimer) {
    clearTimeout(syntaxTimer);
    syntaxTimer = null;
  }
  if (contentSub) {
    contentSub.dispose();
    contentSub = null;
  }
  if (cursorSub) {
    cursorSub.dispose();
    cursorSub = null;
  }
  if (markerSub) {
    markerSub.dispose();
    markerSub = null;
  }
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (themeObserver) {
    themeObserver.disconnect();
    themeObserver = null;
  }
  if (settingsListener) {
    window.removeEventListener(EDITOR_SETTINGS_EVENT, settingsListener);
    settingsListener = null;
  }
  window.removeEventListener("resize", layout);
  window.removeEventListener("keydown", onDocumentKeydown);
  if (editor) {
    editor.dispose();
    editor = null;
  }
  if (model) {
    model.dispose();
    model = null;
  }
}

// --- Save --------------------------------------------------------------------
async function save() {
  if (!editor || saving.value) return false;
  const value = editor.getValue();
  saving.value = true;
  saveError.value = "";
  try {
    await writeFileContent(props.path, value);
    // Hanya anggap "bersih" bila isi editor tidak berubah selama proses simpan.
    if (editor.getValue() === value) {
      savedVersionId = model.getAlternativeVersionId();
      dirty.value = false;
      emit("dirty-change", { path: props.path, dirty: false });
    }
    emit("saved", { path: props.path });
    return true;
  } catch (e) {
    // Simpan gagal: file TIDAK dianggap tersimpan, isi editor dipertahankan.
    saveError.value = e.message || "Gagal menyimpan file.";
    emit("error", saveError.value);
    return false;
  } finally {
    saving.value = false;
  }
}

function applyContent(text) {
  if (model) {
    model.setValue(text ?? "");
    if (editor) editor.focus();
  }
}

// --- Close (aturan unsaved changes) -----------------------------------------
function requestClose() {
  if (saving.value) return;
  if (!dirty.value) {
    emit("close");
    return;
  }
  confirmOpen.value = true;
}

async function confirmSave() {
  const ok = await save();
  if (!ok) {
    // Save gagal -> editor tetap terbuka (feedback error di footer editor).
    confirmOpen.value = false;
    return;
  }
  confirmOpen.value = false;
  emit("close");
}

function confirmDiscard() {
  confirmOpen.value = false;
  emit("close");
}

function confirmCancel() {
  confirmOpen.value = false;
}

// Escape & Ctrl/Cmd+S mengikuti aturan unsaved changes yang sama (tidak ada
// jalur yang menutup editor tanpa konfirmasi saat dirty).
function onDocumentKeydown(e) {
  if (confirmOpen.value) {
    if (e.key === "Escape") {
      e.preventDefault();
      confirmCancel();
    }
    return;
  }
  if (e.key === "Escape") {
    e.preventDefault();
    requestClose();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && (e.key === "s" || e.key === "S")) {
    e.preventDefault();
    save();
  }
}

onMounted(() => {
  window.addEventListener("keydown", onDocumentKeydown);
  load();
});

onBeforeUnmount(() => {
  disposed = true;
  disposeEditor();
});

function revealPosition(line, column = 1) {
  if (editor && model) {
    const l = Math.max(1, parseInt(line, 10) || 1);
    const c = Math.max(1, parseInt(column, 10) || 1);
    editor.revealPositionInCenter({ lineNumber: l, column: c });
    editor.setPosition({ lineNumber: l, column: c });
    editor.focus();
  }
}

defineExpose({
  requestClose,
  save,
  dirty,
  applyContent,
  layout,
  revealPosition,
  reload: load,
});
</script>

<template>
  <!-- Embedded mode: rendering terintegrasi di dalam central workspace tanpa modal overlay -->
  <div v-if="embedded" class="ed-root-embedded">
    <div class="ed-body">
      <!-- Container Monaco selalu ada di DOM; pesan load/error menimpanya. -->
      <div ref="container" class="ed-monaco"></div>
      <div v-if="loading" class="ed-msg">Loading file…</div>
      <div v-else-if="loadError" class="ed-msg ed-err">{{ loadError }}</div>
    </div>

    <div class="ed-status">
      <span class="ed-lang">{{ languageName }}</span>
      <span class="ed-sep">|</span>
      <span class="ed-enc">UTF-8</span>
      <span class="ed-right">
        <span v-if="saveError" class="ed-err-inline" :title="saveError">{{ saveError }}</span>
        <span class="ed-pos">Ln {{ cursor.line }}, Col {{ cursor.column }}</span>
      </span>
    </div>

    <!-- Confirmation: unsaved changes -->
    <div v-if="confirmOpen" class="modal-backdrop" @click.self="confirmCancel">
      <div class="modal ed-confirm" role="dialog" aria-modal="true">
        <div class="modal-title">Unsaved Changes</div>
        <div class="modal-body">File ini memiliki perubahan yang belum disimpan.</div>
        <div class="modal-actions">
          <button class="btn-primary" type="button" :disabled="saving" @click="confirmSave">
            {{ saving ? "Saving…" : "Save" }}
          </button>
          <button class="btn-danger" type="button" :disabled="saving" @click="confirmDiscard">Discard</button>
          <button class="btn-ghost" type="button" :disabled="saving" @click="confirmCancel">Cancel</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Fallback modal bila dipanggil secara non-embedded -->
  <div v-else class="modal-backdrop" @click.self="requestClose">
    <div class="modal editor-m" role="dialog" aria-modal="true">
      <div class="ed-head">
        <span class="ed-ico">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
        </span>
        <span class="ed-title" :title="path">{{ fileName }}</span>
        <span class="ed-dot" :class="{ on: dirty }" :title="dirty ? 'Unsaved changes' : 'Saved'"></span>
        <span class="ed-path mono" :title="path">{{ path }}</span>
        <div class="ed-actions">
          <span class="ed-state" :class="{ on: dirty }">{{ dirty ? "Unsaved" : "Saved" }}</span>
          <button
            class="btn-primary ed-save"
            type="button"
            :disabled="saving || loading || Boolean(loadError)"
            :title="'Save (Ctrl+S)'"
            @click="save"
          >
            {{ saving ? "Saving…" : "Save" }}
          </button>
          <button class="close-x" type="button" title="Close" @click="requestClose">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </div>
      </div>

      <div class="ed-body">
        <!-- Container Monaco selalu ada di DOM; pesan load/error menimpanya. -->
        <div ref="container" class="ed-monaco"></div>
        <div v-if="loading" class="ed-msg">Loading file…</div>
        <div v-else-if="loadError" class="ed-msg ed-err">{{ loadError }}</div>
      </div>

      <div class="ed-status">
        <span class="ed-lang">{{ languageName }}</span>
        <span class="ed-sep">|</span>
        <span class="ed-enc">UTF-8</span>
        <span class="ed-right">
          <span v-if="saveError" class="ed-err-inline" :title="saveError">{{ saveError }}</span>
          <span class="ed-pos">Ln {{ cursor.line }}, Col {{ cursor.column }}</span>
        </span>
      </div>
    </div>

    <!-- Confirmation: unsaved changes -->
    <div v-if="confirmOpen" class="modal-backdrop" @click.self="confirmCancel">
      <div class="modal ed-confirm" role="dialog" aria-modal="true">
        <div class="modal-title">Unsaved Changes</div>
        <div class="modal-body">File ini memiliki perubahan yang belum disimpan.</div>
        <div class="modal-actions">
          <button class="btn-primary" type="button" :disabled="saving" @click="confirmSave">
            {{ saving ? "Saving…" : "Save" }}
          </button>
          <button class="btn-danger" type="button" :disabled="saving" @click="confirmDiscard">Discard</button>
          <button class="btn-ghost" type="button" :disabled="saving" @click="confirmCancel">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>
