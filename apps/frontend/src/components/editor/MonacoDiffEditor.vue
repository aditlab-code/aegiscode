<script setup>
// Aegis Monaco Diff Editor — Side-by-Side & Inline Git Diff (#Fase 1.2).
//
// Menampilkan perbandingan working tree vs HEAD secara interaktif:
//   - original model (kiri): konten dari Git HEAD (read-only),
//   - modified model (kanan): konten working tree saat ini di disk,
//   - toggle tampilan side-by-side vs inline diff,
//   - editing langsung di sisi modified dengan shortcut Save (Cmd+S / Ctrl+S),
//   - lifecycle bersih: dispose diff editor, models, listener, & ResizeObserver.
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  getProjectGitDiff,
  stageProjectGitChanges,
  unstageProjectGitChanges,
} from "../../api.js";
import { languageForFile, languageLabel } from "../../editorLanguages.js";
import {
  getStoredEditorSettings,
  toMonacoOptions,
  EDITOR_SETTINGS_EVENT,
} from "../../services/editorSettingsService.js";

const props = defineProps({
  path: { type: String, required: true },
  filePath: { type: String, default: "" },
  name: { type: String, default: "" },
  project: { type: Object, default: null },
  embedded: { type: Boolean, default: true },
  instanceId: { type: String, default: "primary" },
});

const emit = defineEmits(["close", "error", "edit-file", "discard", "stage-change", "git-refresh"]);

const container = ref(null);
const loading = ref(true);
const loadError = ref("");
const sideBySide = ref(true);
const statusLabel = ref("modified");

const isStaged = ref(false);
const stagingBusy = ref(false);
const cleanFilePath = computed(() => {
  if (props.filePath) return props.filePath;
  const p = props.path || "";
  return p.startsWith("diff://") ? p.slice(7) : p;
});

const instanceUid = `${props.instanceId}-${Math.random().toString(36).slice(2, 8)}`;

const fileName = computed(() => {
  return props.name || cleanFilePath.value.split("/").pop() || cleanFilePath.value;
});

const language = computed(() => languageForFile(cleanFilePath.value));
const languageName = computed(() => languageLabel(language.value));

let monaco = null;
let diffEditor = null;
let originalModel = null;
let modifiedModel = null;
let contentSub = null;
let resizeObserver = null;
let themeObserver = null;
let settingsListener = null;
let savedVersionId = null;
let disposed = false;

let monacoModulePromise = null;
function loadMonacoModule() {
  if (!monacoModulePromise) {
    monacoModulePromise = import("../../monacoSetup.js");
  }
  return monacoModulePromise;
}

function modelUri(path, suffix = "", instanceId = "") {
  const clean = String(path || "untitled")
    .split("/")
    .map((part) => encodeURIComponent(part))
    .join("/");
  const prefix = instanceId ? `${encodeURIComponent(instanceId)}/` : "";
  return monaco.Uri.parse(`inmemory://aegis-diff/${prefix}${clean}${suffix}`);
}

function layout() {
  if (diffEditor) diffEditor.layout();
}

async function load() {
  loading.value = true;
  loadError.value = "";

  const projectId = props.project?.id || props.project?.project_id;
  if (!projectId) {
    loadError.value = "Project active tidak ditemukan.";
    loading.value = false;
    return;
  }

  try {
    const data = await getProjectGitDiff(projectId, cleanFilePath.value);
    const origText = typeof data?.original === "string" ? data.original : "";
    const modText = typeof data?.modified === "string" ? data.modified : "";
    statusLabel.value = data?.status || "modified";
    isStaged.value = Boolean(data?.staged);
    await nextTick();
    await mountDiffEditor(origText, modText);
  } catch (e) {
    loadError.value = e.message || "Gagal memuat diff.";
    emit("error", loadError.value);
  } finally {
    loading.value = false;
    await nextTick();
    layout();
    setTimeout(() => layout(), 50);
  }
}

async function toggleStage() {
  const projectId = props.project?.id || props.project?.project_id;
  if (!projectId || stagingBusy.value) return;
  stagingBusy.value = true;
  try {
    if (isStaged.value) {
      await unstageProjectGitChanges(projectId, cleanFilePath.value);
      isStaged.value = false;
      emit("stage-change", { path: cleanFilePath.value, unstage: true });
    } else {
      await stageProjectGitChanges(projectId, cleanFilePath.value);
      isStaged.value = true;
      emit("stage-change", { path: cleanFilePath.value, unstage: false });
    }
    emit("git-refresh");
  } catch (err) {
    console.error("Failed to toggle stage status:", err);
  } finally {
    stagingBusy.value = false;
  }
}

async function mountDiffEditor(originalText, modifiedText) {
  if (!container.value) return;
  const mod = await loadMonacoModule();
  if (disposed || !container.value) return;

  monaco = mod.getMonaco();

  // Bersihkan model lama bila ada
  const origUri = modelUri(cleanFilePath.value, ".orig", instanceUid);
  const modUri = modelUri(cleanFilePath.value, ".mod", instanceUid);
  const oldOrig = monaco.editor.getModel(origUri);
  if (oldOrig) oldOrig.dispose();
  const oldMod = monaco.editor.getModel(modUri);
  if (oldMod) oldMod.dispose();

  originalModel = monaco.editor.createModel(originalText, language.value, origUri);
  modifiedModel = monaco.editor.createModel(modifiedText, language.value, modUri);

  const preset = typeof document !== "undefined" ? document.documentElement.dataset.themePreset : "";
  const isLight =
    typeof document !== "undefined" &&
    document.documentElement.dataset.theme === "light";
  const userEditorOpts = toMonacoOptions(getStoredEditorSettings());

  const KNOWN_MONACO_PRESETS = [
    "tokyo-night-dark", "tokyo-night-light",
    "nord-dark", "nord-light",
    "atom-dark", "atom-light",
    "default-dark", "default-light",
  ];

  function resolveMonacoTheme(p, light) {
    if (p === "high-contrast-dark") return "hc-black";
    if (p === "high-contrast-light") return "hc-light";
    if (p && KNOWN_MONACO_PRESETS.includes(p)) return p;
    return light ? mod.AEGIS_LIGHT_THEME : mod.AEGIS_THEME;
  }

  if (diffEditor) {
    diffEditor.dispose();
    diffEditor = null;
  }

  // Monaco Diff Editor: Strictly READ-ONLY per architecture decision
  diffEditor = monaco.editor.createDiffEditor(container.value, {
    ...mod.EDITOR_OPTIONS,
    ...userEditorOpts,
    theme: resolveMonacoTheme(preset, isLight),
    originalEditable: false,
    readOnly: true,
    renderSideBySide: sideBySide.value,
    automaticLayout: true,
  });

  diffEditor.setModel({
    original: originalModel,
    modified: modifiedModel,
  });
  diffEditor.layout();

  settingsListener = (e) => {
    if (diffEditor && e?.detail) {
      diffEditor.updateOptions(toMonacoOptions(e.detail));
    }
  };
  if (typeof window !== "undefined") {
    window.addEventListener(EDITOR_SETTINGS_EVENT, settingsListener);
  }

  if (typeof MutationObserver !== "undefined" && typeof document !== "undefined") {
    themeObserver = new MutationObserver(() => {
      const p = document.documentElement.dataset.themePreset;
      const lightNow = document.documentElement.dataset.theme === "light";
      monaco.editor.setTheme(resolveMonacoTheme(p, lightNow));
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme", "data-theme-preset"],
    });
  }

  if (typeof ResizeObserver !== "undefined" && container.value) {
    resizeObserver = new ResizeObserver(() => layout());
    resizeObserver.observe(container.value);
  }
}

function setSideBySide(val) {
  sideBySide.value = val;
  if (diffEditor) {
    diffEditor.updateOptions({ renderSideBySide: sideBySide.value });
    layout();
  }
}

function toggleSideBySide() {
  setSideBySide(!sideBySide.value);
}

const confirmDiscard = ref(false);
const discarding = ref(false);

function onExecuteDiscard() {
  discarding.value = true;
  emit("discard", cleanFilePath.value);
}

function onGlobalKeyDown(e) {
  if (e.key === "Escape" && confirmDiscard.value) {
    e.stopPropagation();
    confirmDiscard.value = false;
  }
}

function onGlobalClick(e) {
  if (confirmDiscard.value && !e.target.closest(".diff-discard-inline-confirm")) {
    confirmDiscard.value = false;
  }
}

onMounted(() => {
  disposed = false;
  load();
  if (typeof window !== "undefined") {
    window.addEventListener("keydown", onGlobalKeyDown);
    window.addEventListener("click", onGlobalClick);
  }
});

onBeforeUnmount(() => {
  disposed = true;
  if (typeof window !== "undefined") {
    window.removeEventListener("keydown", onGlobalKeyDown);
    window.removeEventListener("click", onGlobalClick);
    if (settingsListener) {
      window.removeEventListener(EDITOR_SETTINGS_EVENT, settingsListener);
    }
  }
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (themeObserver) {
    themeObserver.disconnect();
    themeObserver = null;
  }
  if (originalModel) {
    originalModel.dispose();
    originalModel = null;
  }
  if (modifiedModel) {
    modifiedModel.dispose();
    modifiedModel = null;
  }
  if (diffEditor) {
    diffEditor.dispose();
    diffEditor = null;
  }
});

defineExpose({ layout });
</script>

<template>
  <div class="monaco-diff-container" :class="{ embedded }">
    <!-- Toolbar Header -->
    <div class="diff-header-bar">
      <div class="diff-title-group">
        <span class="diff-split-icon" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <path d="M12 3v18"/>
          </svg>
        </span>
        <span class="diff-file-name">{{ fileName }}</span>
        <span class="diff-tag-pill" :class="'tag-' + statusLabel.toLowerCase()">
          {{ statusLabel.toUpperCase() }}
        </span>
        <span v-if="isStaged" class="diff-tag-pill tag-staged" title="Staged in Git index">
          STAGED
        </span>
        <span class="diff-ref-indicator">HEAD ↔ Working Tree</span>
        <span class="diff-readonly-pill" title="This diff comparison is read-only. Click Edit File to edit in Code Editor.">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
          </svg>
          <span>READ-ONLY</span>
        </span>
      </div>

      <div class="diff-actions-group">
        <!-- Split / Inline Mode Switcher -->
        <div class="diff-view-mode-group">
          <button
            type="button"
            class="diff-mode-btn"
            :class="{ active: sideBySide }"
            title="Side-by-Side (Split) View"
            @click="setSideBySide(true)"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2"/>
              <path d="M12 3v18"/>
            </svg>
            <span>Split</span>
          </button>
          <button
            type="button"
            class="diff-mode-btn"
            :class="{ active: !sideBySide }"
            title="Inline Unified Diff"
            @click="setSideBySide(false)"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2"/>
              <path d="M3 12h18"/>
            </svg>
            <span>Inline</span>
          </button>
        </div>

        <!-- Approval action (Stage / Unstage toggle) -->
        <button
          type="button"
          class="diff-btn diff-stage-btn"
          :class="{ 'is-staged': isStaged }"
          :title="isStaged ? 'Unstage Changes' : 'Stage Changes (Approve)'"
          :aria-label="isStaged ? 'Unstage Changes' : 'Stage Changes (Approve)'"
          :disabled="stagingBusy || loading"
          @click.stop="toggleStage"
        >
          <svg v-if="isStaged" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </button>

        <!-- Edit in Code Editor shortcut (for non-deleted files) -->
        <button
          v-if="statusLabel !== 'deleted'"
          type="button"
          class="diff-btn diff-edit-btn"
          title="Edit File"
          aria-label="Edit File"
          @click="emit('edit-file', cleanFilePath)"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 20h9"/>
            <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>
          </svg>
        </button>

        <!-- Discard Changes button / Inline In-Place Confirmation -->
        <div v-if="confirmDiscard" class="diff-discard-inline-confirm" @click.stop>
          <span class="diff-confirm-msg">Discard changes?</span>
          <button
            type="button"
            class="diff-btn diff-btn-danger"
            :disabled="discarding"
            title="Confirm discard to HEAD"
            @click.stop="onExecuteDiscard"
          >
            <span>{{ discarding ? "Discarding…" : "Discard" }}</span>
          </button>
          <button
            type="button"
            class="diff-btn diff-btn-ghost"
            :disabled="discarding"
            title="Cancel discard"
            @click.stop="confirmDiscard = false"
          >
            <span>Cancel</span>
          </button>
        </div>
        <button
          v-else
          type="button"
          class="diff-btn diff-discard-btn"
          title="Discard Changes"
          aria-label="Discard Changes"
          @click.stop="confirmDiscard = true"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
            <path d="M3 3v5h5"/>
          </svg>
        </button>

        <button
          type="button"
          class="diff-btn"
          title="Refresh Diff"
          aria-label="Refresh Diff"
          :disabled="loading"
          @click="load"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12a9 9 0 1 1-2.6-6.4M21 4v5h-5"/>
          </svg>
        </button>

        <button
          type="button"
          class="diff-close-btn"
          title="Close Diff (Esc)"
          aria-label="Close Diff"
          @click="emit('close')"
        >
          ×
        </button>
      </div>
    </div>

    <!-- Body: Monaco Diff Viewport & State Overlays -->
    <div class="diff-body">
      <!-- Monaco Diff Canvas: Always kept in DOM, never hidden via display:none -->
      <div ref="container" class="diff-monaco"></div>

      <!-- Loading State Overlay -->
      <div v-if="loading" class="diff-msg">
        <span class="diff-spinner" aria-hidden="true"></span>
        <span>Loading diff comparison…</span>
      </div>

      <!-- Error State Overlay -->
      <div v-else-if="loadError" class="diff-msg diff-err">
        <div class="diff-err-title">Failed to load diff</div>
        <div class="diff-err-text">{{ loadError }}</div>
        <button type="button" class="diff-btn" @click="load">Retry</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.monaco-diff-container {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  background: var(--bg-deep);
  overflow: hidden;
  position: relative;
}

.diff-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 32px;
  min-height: 32px;
  padding: 0 10px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-soft, rgba(255, 255, 255, 0.08));
  font-size: 11.5px;
}

.diff-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.diff-split-icon {
  color: var(--accent);
  display: flex;
  align-items: center;
}

.diff-file-name {
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.diff-tag-pill {
  font-size: 9.5px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.diff-tag-pill.tag-modified {
  background: rgba(234, 179, 8, 0.15);
  color: var(--warn);
}
.diff-tag-pill.tag-untracked {
  background: rgba(16, 185, 129, 0.15);
  color: var(--ok);
}
.diff-tag-pill.tag-deleted {
  background: rgba(239, 68, 68, 0.15);
  color: var(--err);
}

.diff-ref-indicator {
  font-size: 10.5px;
  color: var(--text-faint);
  white-space: nowrap;
}

.diff-readonly-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 9px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--text-faint);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.1));
  letter-spacing: 0.04em;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.diff-actions-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.diff-view-mode-group {
  display: inline-flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.08));
  border-radius: 4px;
  padding: 1px;
  gap: 1px;
}

.diff-mode-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 7px;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-faint);
  background: transparent;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.12s ease;
}

.diff-mode-btn:hover {
  color: var(--text);
}

.diff-mode-btn.active {
  color: var(--bg);
  background: var(--accent);
}

.diff-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 500;
  color: var(--muted);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.08));
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.12s ease;
}
.diff-btn:hover {
  color: var(--text);
  background: rgba(255, 255, 255, 0.08);
  border-color: var(--border, rgba(255, 255, 255, 0.15));
}
.diff-edit-btn {
  color: var(--accent);
  background: rgba(168, 85, 247, 0.12);
  border-color: rgba(168, 85, 247, 0.3);
}
.diff-edit-btn:hover {
  color: var(--bg);
  background: var(--accent);
  border-color: var(--accent);
}
.diff-discard-btn {
  color: var(--err);
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.25);
}
.diff-discard-btn:hover {
  color: var(--bg);
  background: var(--err);
  border-color: var(--err);
}

.diff-discard-inline-confirm {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 6px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.35);
  border-radius: 4px;
}

.diff-confirm-msg {
  font-size: 11px;
  font-weight: 600;
  color: var(--err);
  padding-right: 2px;
}

.diff-btn-danger {
  color: var(--bg);
  background: var(--err);
  border-color: var(--err);
  font-weight: 600;
  padding: 2px 7px;
}
.diff-btn-danger:hover:not(:disabled) {
  background: var(--err);
  border-color: var(--err);
}
.diff-btn-danger:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.diff-btn-ghost {
  color: var(--text-faint);
  background: transparent;
  border-color: transparent;
  padding: 2px 6px;
}
.diff-btn-ghost:hover:not(:disabled) {
  color: var(--text);
  background: rgba(255, 255, 255, 0.08);
}

.diff-close-btn {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  background: transparent;
  border: none;
  font-size: 14px;
  color: var(--text-faint);
  cursor: pointer;
  border-radius: 3px;
}
.diff-close-btn:hover {
  color: var(--text);
  background: rgba(255, 255, 255, 0.08);
}

.diff-body {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  height: 100%;
  width: 100%;
  overflow: hidden;
}

.diff-monaco {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.diff-msg {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--text-faint);
  background: var(--bg-deep);
  z-index: 10;
}

.diff-msg.diff-err {
  color: var(--err);
  background: rgba(20, 18, 30, 0.95);
}

.diff-err-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--err);
}

.diff-err-text {
  max-width: 420px;
  word-break: break-word;
  color: var(--muted);
}

.diff-spinner {
  width: 22px;
  height: 22px;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: diff-spin 0.8s linear infinite;
}

@keyframes diff-spin {
  to { transform: rotate(360deg); }
}

.diff-btn.diff-stage-btn {
  color: var(--text-faint);
}

.diff-btn.diff-stage-btn:hover:not(:disabled) {
  color: var(--ok);
  background: rgba(158, 206, 106, 0.14);
  border-color: rgba(158, 206, 106, 0.35);
}

.diff-btn.diff-stage-btn.is-staged {
  color: var(--ok);
  background: rgba(158, 206, 106, 0.12);
  border-color: rgba(158, 206, 106, 0.3);
}

.diff-btn.diff-stage-btn.is-staged:hover:not(:disabled) {
  color: var(--accent);
  background: var(--bg-hover);
  border-color: var(--border);
}

.diff-tag-pill.tag-staged {
  background: rgba(158, 206, 106, 0.14);
  color: var(--ok);
  border: 1px solid rgba(158, 206, 106, 0.3);
}
</style>
