<script setup>
// File Explorer (#52 rework). Menampilkan file project aktif (read-only).
// Data dari ListFilesTool AETHER via gateway (#50). TIDAK ada abstraksi
// filesystem baru di frontend. Root = active project root (bukan ".").
import { computed, ref, watch } from "vue";
import { listFiles, getProjectGitStatus } from "../api.js";
// Node tree RECURSIVE (menggantikan rendering 2-level hard-coded). Komponen ini
// merender satu baris lalu memanggil dirinya sendiri untuk anak-anaknya, jadi
// kedalaman folder tidak lagi dibatasi di template.
import ExplorerTreeNode from "./ExplorerTreeNode.vue";

const props = defineProps({
  project: { type: Object, default: null },
  // Penanda refresh dari parent (mis. setelah agent selesai membuat file).
  refreshKey: { type: Number, default: 0 },
  // Perubahan filesystem LIVE (event change_detected) selagi Agent berjalan.
  // Bukan full reload: hanya direktori terdampak yang di-refresh, state
  // expanded/selected dipertahankan.
  liveChange: { type: Object, default: null },
  // Active open tabs from Monaco editor
  openTabs: { type: Array, default: () => [] },
  activeTabPath: { type: String, default: "" },
  openTabs2: { type: Array, default: () => [] },
  activeTabPath2: { type: String, default: "" },
  splitActive: { type: Boolean, default: false },
  activePane: { type: String, default: "pane1" },
});

const entries = ref([]);
const currentPath = ref(".");
const loading = ref(false);
const error = ref("");
// Folder yang di-expand: map path -> entries anak.
const expanded = ref({});
// Path file terpilih (selected state).
const selected = ref("");
// Git Status Map: relativePath -> status code ('M', 'U', 'D', 'A', etc.)
const gitStatusMap = ref({});
// Collapsible section (AETHER Workbench right column).
// Default: EXPLORER TERBUKA. State hanya di frontend selama sesi aktif.
const collapsed = ref(false);
function toggleCollapse() {
  collapsed.value = !collapsed.value;
}
const openEditorsCollapsed = ref(false);
function toggleOpenEditors() {
  openEditorsCollapsed.value = !openEditorsCollapsed.value;
}
const groupCollapsed = ref({
  tab1: false,
  tab2: false,
});
function toggleGroup(groupKey) {
  groupCollapsed.value[groupKey] = !groupCollapsed.value[groupKey];
}
const totalOpenTabsCount = computed(() => {
  return props.splitActive
    ? props.openTabs.length + props.openTabs2.length
    : props.openTabs.length;
});
function collapseAllFolders() {
  expanded.value = {};
}
// Context menu state.
const contextMenu = ref(null);
const contextOpen = ref(false);

// Nama folder internal AETHER yang disembunyikan dari UI Explorer.
const HIDDEN_NAMES = new Set([".aether"]);

function visibleEntries(list) {
  return (list || []).filter((e) => !HIDDEN_NAMES.has(e.name));
}

const rootLabel = computed(() => (props.project && props.project.name) || "project");

// --- File type icon / color mapping ---

const FILE_ICONS = {
  // Python
  py: "python",
  // HTML
  html: "html", htm: "html",
  // JavaScript
  js: "javascript", jsx: "javascript",
  // TypeScript
  ts: "typescript", tsx: "typescript",
  // Vue
  vue: "vue",
  // CSS
  css: "css", scss: "css", sass: "css",
  // JSON
  json: "json",
  // YAML
  yaml: "yaml", yml: "yaml",
  // Markdown
  md: "markdown", markdown: "markdown",
  // Text
  txt: "text",
  // XML
  xml: "xml",
  // SQL
  sql: "sql",
  // Shell
  sh: "shell", bash: "shell", zsh: "shell", fish: "shell",
  // Windows batch
  bat: "batch", cmd: "batch", ps1: "batch",
  // PHP
  php: "php",
  // Java
  java: "java",
  // C/C++
  c: "cpp", h: "cpp", cpp: "cpp", hpp: "cpp",
  // C#
  cs: "csharp",
  // Go
  go: "go",
  // Rust
  rs: "rust",
  // Ruby
  rb: "ruby",
  // TOML
  toml: "toml",
  // INI / Config
  ini: "config", conf: "config",
  // Environment
  env: "env",
  // Images (Gruvbox Material Purple)
  png: "image", jpg: "image", jpeg: "image", gif: "image", svg: "image", webp: "image", ico: "image",
  // Archives (Gruvbox Material Yellow)
  zip: "archive", tar: "archive", gz: "archive", "7z": "archive", rar: "archive", tgz: "archive",
  // Locks (Gruvbox Material Red)
  lock: "lock", lockb: "lock",
};

const FILE_COLORS = {
  python:     "#22a06b",   // green
  html:       "#2d7ab8",   // blue
  javascript: "#c9880e",   // amber
  typescript: "#2d7ab8",   // blue
  vue:        "#22a06b",   // green
  css:        "#5ebd87",   // green-muted (replaces violet #c4b5fd)
  json:       "#c9880e",   // amber
  yaml:       "#c96aa0",   // muted pink
  markdown:   "#9b98b0",   // text-dim
  text:       "#6a6880",   // text-faint
  xml:        "#d4703a",   // orange
  sql:        "#2d7ab8",   // blue (replaces #818cf8)
  shell:      "#22a06b",   // green
  batch:      "#2d7ab8",   // blue
  php:        "#5ebd87",   // green (replaces #c084fc)
  java:       "#d96b7a",   // rose
  cpp:        "#5aacd4",   // sky blue
  csharp:     "#5ebd87",   // green (replaces #c084fc)
  go:         "#2d7d4e",   // accent green
  rust:       "#d4703a",   // orange
  ruby:       "#d96b7a",   // rose
  toml:       "#d4703a",
  config:     "#6a6880",
  env:        "#22a06b",
  // Gruvbox Material palette extensions
  image:      "#b16286",   // purple
  archive:    "#d79921",   // yellow
  lock:       "#cc241d",   // red
  docker:     "#458588",   // blue/aqua
  dockerfile: "#458588",   // blue/aqua
  package:    "#b16286",   // purple
  git:        "#af3a03",   // orange
  gitignore:  "#af3a03",   // orange
};

function fileTypeIcon(name) {
  // Check special filenames first.
  const lower = name.toLowerCase();
  if (lower === "readme.md" || lower === "readme.markdown") return "markdown";
  if (lower === "license" || lower === "license.md" || lower === "license.txt") return "license";
  if (lower === ".gitignore" || lower === ".gitattributes" || lower === ".gitmodules") return "git";
  if (lower === ".env") return "env";
  if (lower === ".env.example") return "env-example";
  if (lower === "dockerfile" || lower.startsWith("dockerfile.") || lower === "docker-compose.yml" || lower === "docker-compose.yaml" || lower === ".dockerignore") return "docker";
  if (lower === "makefile") return "makefile";
  if (lower === "pyproject.toml") return "pyproject";
  if (lower === "package.json") return "package";
  if (lower === "package-lock.json" || lower === "yarn.lock" || lower === "pnpm-lock.yaml" || lower === "bun.lockb") return "lock";
  if (lower === "requirements.txt") return "requirements";

  const dot = name.lastIndexOf(".");
  if (dot < 0) return "generic";
  const ext = name.slice(dot + 1).toLowerCase();
  return FILE_ICONS[ext] || "generic";
}

function fileTypeColor(name) {
  const icon = fileTypeIcon(name);
  return FILE_COLORS[icon] || null;
}

// Path helpers.
function childPath(base, name) {
  return base === "." || !base ? name : `${base}/${name}`;
}

function absoluteFromRel(rel) {
  if (!props.project) return rel;
  const root = props.project.root || props.project.path || "";
  if (!rel || rel === ".") return root;
  return `${root}/${rel}`;
}

async function loadGitStatus() {
  const pId = props.project?.id || props.project?.project_id;
  if (!pId) {
    gitStatusMap.value = {};
    return;
  }
  try {
    const res = await getProjectGitStatus(pId);
    const map = {};
    if (res?.is_repository && Array.isArray(res.files)) {
      for (const f of res.files) {
        if (f?.path && f?.status) {
          map[normalizeRel(f.path)] = f.status;
        }
      }
    }
    gitStatusMap.value = map;
  } catch (e) {
    gitStatusMap.value = {};
  }
}

// Explorer helpers.
async function load(path = ".") {
  if (!props.project) return;
  loading.value = true;
  error.value = "";
  try {
    const data = await listFiles(path);
    entries.value = visibleEntries(data.entries);
    currentPath.value = data.path || path;
    loadGitStatus();
  } catch (e) {
    error.value = e.message || "Gagal memuat file.";
    entries.value = [];
  } finally {
    loading.value = false;
  }
}

const emit = defineEmits([
  "open-file",
  "open-file-editor",
  "select-tab",
  "close-tab",
  "clear-tabs",
]);

function openFile(fullPath, name) {
  selected.value = fullPath;
  emit("open-file", { path: fullPath, name });
}

// Expand/collapse SATU folder secara INDEPENDEN (map path -> anak).
// Tidak ada batas kedalaman: anak folder mana pun bisa di-expand/collapse.
async function toggleDirByPath(full) {
  if (expanded.value[full]) {
    const next = { ...expanded.value };
    delete next[full];
    expanded.value = next;
    return;
  }
  try {
    const data = await listFiles(full);
    expanded.value = { ...expanded.value, [full]: visibleEntries(data.entries) };
  } catch (e) {
    error.value = e.message || "Gagal memuat folder.";
  }
}

// --- Live filesystem update (event change_detected) -------------------------
// Normalisasi path relatif (posix, tanpa "./" & trailing slash).
function normalizeRel(p) {
  if (!p) return "";
  let s = String(p).replace(/\\/g, "/");
  while (s.startsWith("./")) s = s.slice(2);
  return s.replace(/\/+$/, "");
}

// Direktori induk dari path relatif ("." bila di root).
function parentDirOf(rel) {
  const s = normalizeRel(rel);
  const idx = s.lastIndexOf("/");
  return idx <= 0 ? "." : s.slice(0, idx);
}

// Refresh SATU direktori tanpa mereset state expand/selected.
// - "." (root) selalu di-refresh.
// - folder lain hanya di-refresh bila sedang terbuka (ada di `expanded`).
async function reloadDir(path) {
  if (!props.project) return;
  const key = path || ".";
  if (key === "." || key === currentPath.value) {
    try {
      const data = await listFiles(currentPath.value || ".");
      entries.value = visibleEntries(data.entries);
      currentPath.value = data.path || currentPath.value;
    } catch (e) {
      // Biarkan listing lama bila gagal.
    }
    return;
  }
  if (!(key in expanded.value)) return;
  try {
    const data = await listFiles(key);
    expanded.value = { ...expanded.value, [key]: visibleEntries(data.entries) };
  } catch (e) {
    // Folder bisa saja sudah tidak ada (delete/move).
    const next = { ...expanded.value };
    delete next[key];
    expanded.value = next;
  }
}

// Pindahkan key `expanded` dari prefix lama ke prefix baru (move/rename).
function remapExpanded(oldPrefix, newPrefix) {
  if (!oldPrefix) return;
  const next = {};
  let changed = false;
  for (const [k, v] of Object.entries(expanded.value)) {
    if (k === oldPrefix || k.startsWith(oldPrefix + "/")) {
      next[newPrefix + k.slice(oldPrefix.length)] = v;
      changed = true;
    } else {
      next[k] = v;
    }
  }
  if (changed) expanded.value = next;
}

async function applyLiveChange(change) {
  if (!change || !change.path) return;
  const kind = String(change.kind || "").toLowerCase();
  const newPath = normalizeRel(change.path);
  if (kind.includes("move") || kind.includes("renam")) {
    const oldPath = normalizeRel(change.old_path || "");
    if (oldPath) {
      remapExpanded(oldPath, newPath);
      if (
        selected.value &&
        (selected.value === oldPath || selected.value.startsWith(oldPath + "/"))
      ) {
        selected.value = newPath + selected.value.slice(oldPath.length);
      }
    }
    await reloadDir(parentDirOf(oldPath || newPath));
    await reloadDir(parentDirOf(newPath));
    return;
  }
  await reloadDir(parentDirOf(newPath));
}

// Handler dari node tree recursive (ExplorerTreeNode).
function handleToggle(full) {
  toggleDirByPath(full);
}

function handleOpen(full, name) {
  openFile(full, name);
}

function up() {
  if (currentPath.value === "." || !currentPath.value) return;
  const parts = currentPath.value.split("/");
  parts.pop();
  load(parts.length ? parts.join("/") : ".");
}

// --- Context Menu ---
// fullPath = path penuh node (dari ExplorerTreeNode), jadi menu tetap benar
// pada kedalaman berapa pun (bukan dihitung dari root saja).
function onContextMenu(e, entry, fullPath, kind) {
  e.preventDefault();
  stopPropagation(e);
  const menuW = 180;
  const menuH = 280;
  let x = e.clientX;
  let y = e.clientY;
  if (x + menuW > window.innerWidth) x = window.innerWidth - menuW - 4;
  if (y + menuH > window.innerHeight) y = window.innerHeight - menuH - 4;
  if (x < 4) x = 4;
  if (y < 4) y = 4;
  contextMenu.value = { x, y, entry, type: kind, path: fullPath };
  contextOpen.value = true;
}

function stopPropagation(e) {
  e.stopPropagation();
}

function closeContextMenu() {
  contextOpen.value = false;
  contextMenu.value = null;
}

// Path penuh node yang jadi target context menu (dari ExplorerTreeNode).
function ctxTargetPath(entry) {
  const m = contextMenu.value;
  if (m && m.path) return m.path;
  return childPath(currentPath.value, entry.name);
}

function ctxOpen(entry) {
  const full = ctxTargetPath(entry);
  closeContextMenu();
  if (entry.type === 'dir') {
    toggleDirByPath(full);
  } else {
    openFile(full, entry.name);
  }
}

function ctxOpenWithEditor(entry) {
  const full = ctxTargetPath(entry);
  closeContextMenu();
  emit("open-file-editor", {
    path: full,
    name: entry.name,
  });
}

function ctxCopyPath(entry) {
  const rel = ctxTargetPath(entry);
  closeContextMenu();
  navigator.clipboard.writeText(rel).catch(() => {});
}

function ctxCopyFullPath(entry) {
  const abs = absoluteFromRel(ctxTargetPath(entry));
  closeContextMenu();
  navigator.clipboard.writeText(abs).catch(() => {});
}

function ctxReveal(entry) {
  const abs = absoluteFromRel(ctxTargetPath(entry));
  closeContextMenu();
  revealInExplorer(abs);
}

async function revealInExplorer(path) {
  try {
    const resp = await fetch("/api/reveal-in-explorer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      error.value = data.error?.message || "Gagal membuka Explorer.";
    }
  } catch (e) {
    error.value = e.message || "Gagal membuka Explorer.";
  }
}

function ctxRename(entry) {
  closeContextMenu();
  error.value = "Rename is not yet available.";
}

function ctxDelete(entry) {
  const rel = ctxTargetPath(entry);
  closeContextMenu();
  if (!confirm(`Hapus "${entry.name}" dari project?`)) return;
  deleteEntry(rel, entry.type);
}

async function deleteEntry(relPath, type) {
  try {
    const resp = await fetch("/api/delete-entry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: relPath, type }),
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      error.value = data.error?.message || "Gagal menghapus.";
    } else {
      await load(currentPath.value);
    }
  } catch (e) {
    error.value = e.message || "Gagal menghapus.";
  }
}

// Close context menu on outside click / escape.
function onDocumentClick(e) {
  if (contextOpen.value && !e.target.closest(".ctx-menu")) {
    closeContextMenu();
  }
}

function onDocumentKeydown(e) {
  if (e.key === "Escape" && contextOpen.value) {
    closeContextMenu();
  }
}

watch(
  () => [props.project && (props.project.id || props.project.project_id), props.refreshKey],
  () => {
    expanded.value = {};
    load(".");
    loadGitStatus();
  },
  { immediate: true }
);

// Live change dari event SSE (Agent masih berjalan) -> update incremental.
watch(
  () => (props.liveChange ? props.liveChange.seq : 0),
  () => {
    applyLiveChange(props.liveChange);
    loadGitStatus();
  }
);
</script>

<template>
  <div class="file-explorer-container">
    <!-- 1. OPEN EDITORS Section -->
    <section v-if="totalOpenTabsCount > 0" class="block open-editors-block" :class="{ collapsed: openEditorsCollapsed }">
      <div class="drawer-sec-head oe-head" @click="toggleOpenEditors">
        <span class="sec-caret" aria-hidden="true">{{ openEditorsCollapsed ? "▸" : "▾" }}</span>
        <span class="drawer-sec-title">OPEN EDITORS</span>
        <div class="drawer-sec-actions">
          <span class="drawer-badge oe-badge">{{ totalOpenTabsCount }}</span>
          <button
            class="ex-icon-btn oe-clear-btn"
            type="button"
            title="Close All Editors (Clear tabs)"
            aria-label="Clear All Tabs"
            @click.stop="emit('clear-tabs')"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M18 6 6 18"/><path d="m6 6 12 12"/>
            </svg>
          </button>
        </div>
      </div>

      <div v-show="!openEditorsCollapsed" class="open-editors-list">
        <!-- Dual groups when split is active -->
        <template v-if="splitActive">
          <!-- Group Tab 1 -->
          <div class="oe-group" :class="{ 'is-active-pane': activePane === 'pane1' }">
            <div class="oe-group-header" @click.stop="toggleGroup('tab1')">
              <span class="sec-caret" aria-hidden="true">{{ groupCollapsed.tab1 ? "▸" : "▾" }}</span>
              <span class="oe-group-title">Tab 1</span>
              <span class="drawer-badge oe-group-badge">{{ openTabs.length }}</span>
            </div>
            <div v-show="!groupCollapsed.tab1" class="oe-group-items">
              <div
                v-for="tab in openTabs"
                :key="'p1-' + tab.path"
                class="oe-item-row"
                :class="{ active: tab.path === activeTabPath && activePane === 'pane1', dirty: tab.dirty }"
                @click="emit('select-tab', tab.path, 'pane1')"
              >
                <span class="oe-icon" :style="{ color: fileTypeColor(tab.name) }">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <path d="M14 2v6h6" />
                  </svg>
                </span>
                <span class="oe-name" :title="tab.path">{{ tab.name }}</span>
                <span
                  v-if="gitStatusMap[normalizeRel(tab.filePath || tab.path)]"
                  class="oe-git-badge"
                  :class="'git-' + String(gitStatusMap[normalizeRel(tab.filePath || tab.path)]).toLowerCase()"
                  :title="gitStatusMap[normalizeRel(tab.filePath || tab.path)]"
                >
                  {{ gitStatusMap[normalizeRel(tab.filePath || tab.path)] }}
                </span>
                <span v-if="tab.dirty" class="oe-dirty-dot" title="Unsaved changes">●</span>
                <button
                  type="button"
                  class="oe-close-btn"
                  title="Close Tab"
                  aria-label="Close Tab"
                  @click.stop="emit('close-tab', tab.path, 'pane1')"
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
              <div v-if="openTabs.length === 0" class="oe-empty-hint">No open tabs in Tab 1</div>
            </div>
          </div>

          <!-- Group Tab 2 -->
          <div class="oe-group" :class="{ 'is-active-pane': activePane === 'pane2' }">
            <div class="oe-group-header" @click.stop="toggleGroup('tab2')">
              <span class="sec-caret" aria-hidden="true">{{ groupCollapsed.tab2 ? "▸" : "▾" }}</span>
              <span class="oe-group-title">Tab 2</span>
              <span class="drawer-badge oe-group-badge">{{ openTabs2.length }}</span>
            </div>
            <div v-show="!groupCollapsed.tab2" class="oe-group-items">
              <div
                v-for="tab in openTabs2"
                :key="'p2-' + tab.path"
                class="oe-item-row"
                :class="{ active: tab.path === activeTabPath2 && activePane === 'pane2', dirty: tab.dirty }"
                @click="emit('select-tab', tab.path, 'pane2')"
              >
                <span class="oe-icon" :style="{ color: fileTypeColor(tab.name) }">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <path d="M14 2v6h6" />
                  </svg>
                </span>
                <span class="oe-name" :title="tab.path">{{ tab.name }}</span>
                <span
                  v-if="gitStatusMap[normalizeRel(tab.filePath || tab.path)]"
                  class="oe-git-badge"
                  :class="'git-' + String(gitStatusMap[normalizeRel(tab.filePath || tab.path)]).toLowerCase()"
                  :title="gitStatusMap[normalizeRel(tab.filePath || tab.path)]"
                >
                  {{ gitStatusMap[normalizeRel(tab.filePath || tab.path)] }}
                </span>
                <span v-if="tab.dirty" class="oe-dirty-dot" title="Unsaved changes">●</span>
                <button
                  type="button"
                  class="oe-close-btn"
                  title="Close Tab"
                  aria-label="Close Tab"
                  @click.stop="emit('close-tab', tab.path, 'pane2')"
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
              <div v-if="openTabs2.length === 0" class="oe-empty-hint">No open tabs in Tab 2</div>
            </div>
          </div>
        </template>

        <!-- Single Window Mode: Single list under Tab 1 -->
        <template v-else>
          <div class="oe-group is-active-pane">
            <div class="oe-group-header" @click.stop="toggleGroup('tab1')">
              <span class="sec-caret" aria-hidden="true">{{ groupCollapsed.tab1 ? "▸" : "▾" }}</span>
              <span class="oe-group-title">Tab 1</span>
              <span class="drawer-badge oe-group-badge">{{ openTabs.length }}</span>
            </div>
            <div v-show="!groupCollapsed.tab1" class="oe-group-items">
              <div
                v-for="tab in openTabs"
                :key="'single-' + tab.path"
                class="oe-item-row"
                :class="{ active: tab.path === activeTabPath, dirty: tab.dirty }"
                @click="emit('select-tab', tab.path, 'pane1')"
              >
                <span class="oe-icon" :style="{ color: fileTypeColor(tab.name) }">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <path d="M14 2v6h6" />
                  </svg>
                </span>
                <span class="oe-name" :title="tab.path">{{ tab.name }}</span>
                <span
                  v-if="gitStatusMap[normalizeRel(tab.filePath || tab.path)]"
                  class="oe-git-badge"
                  :class="'git-' + String(gitStatusMap[normalizeRel(tab.filePath || tab.path)]).toLowerCase()"
                  :title="gitStatusMap[normalizeRel(tab.filePath || tab.path)]"
                >
                  {{ gitStatusMap[normalizeRel(tab.filePath || tab.path)] }}
                </span>
                <span v-if="tab.dirty" class="oe-dirty-dot" title="Unsaved changes">●</span>
                <button
                  type="button"
                  class="oe-close-btn"
                  title="Close Tab"
                  aria-label="Close Tab"
                  @click.stop="emit('close-tab', tab.path, 'pane1')"
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </template>
      </div>
    </section>

    <!-- 2. EXPLORER / WORKSPACE FILES Section -->
    <section class="block explorer-block" :class="{ collapsed }">
      <div class="drawer-sec-head ex-head" @click="toggleCollapse">
        <span class="sec-caret" aria-hidden="true">{{ collapsed ? "▸" : "▾" }}</span>
        <span class="drawer-sec-title">EXPLORER</span>
        <span v-if="currentPath !== '.'" class="drawer-sec-sub" :title="currentPath">{{ currentPath }}</span>
        <div class="drawer-sec-actions">
          <button
            class="ex-icon-btn"
            type="button"
            title="Collapse All Folders"
            aria-label="Collapse All Folders"
            @click.stop="collapseAllFolders"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="m4 10 4-4 4 4"/><path d="M8 6v12"/><path d="m20 14-4 4-4-4"/><path d="M16 18V6"/>
            </svg>
          </button>
          <button class="ex-icon-btn" type="button" title="Refresh" @click.stop="load(currentPath)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.6-6.4M21 4v5h-5"/></svg>
          </button>
          <button v-if="currentPath !== '.'" class="ex-icon-btn" type="button" title="Up" @click.stop="up">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
          </button>
        </div>
      </div>

    <div v-show="!collapsed" class="explorer" @click="closeContextMenu" @contextmenu.prevent>
      <div v-if="loading" class="ex-empty">Loading…</div>
      <div v-else-if="error" class="ex-empty ex-err">{{ error }}</div>
      <div v-else-if="!entries.length" class="ex-empty">Empty.</div>

      <!-- Tree recursive: satu komponen node merender dirinya sendiri pada
           kedalaman berapa pun (tidak ada batas level). -->
      <template v-else>
        <ExplorerTreeNode
          v-for="e in entries"
          :key="e.name"
          :entry="e"
          :path="childPath(currentPath, e.name)"
          :depth="0"
          :dirs="expanded"
          :selected="selected"
          :icon-fn="fileTypeIcon"
          :color-fn="fileTypeColor"
          :git-status-map="gitStatusMap"
          @toggle="handleToggle"
          @open="handleOpen"
          @context="onContextMenu"
        />
      </template>
    </div>

    <!-- Context Menu -->
    <div
      v-if="contextOpen && contextMenu"
      class="ctx-menu"
      :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
      @click.stop
      @contextmenu.prevent
    >
      <template v-if="contextMenu.type === 'file'">
        <div class="ctx-item" @click="ctxOpen(contextMenu.entry)">Open</div>
        <div class="ctx-item" @click="ctxOpenWithEditor(contextMenu.entry)">Open with Editor</div>
        <div class="ctx-sep"></div>
        <div class="ctx-item" @click="ctxCopyPath(contextMenu.entry)">Copy Path</div>
        <div class="ctx-item" @click="ctxCopyFullPath(contextMenu.entry)">Copy Full Path</div>
        <div class="ctx-sep"></div>
        <div class="ctx-item" @click="ctxReveal(contextMenu.entry)">Reveal in Explorer</div>
        <div class="ctx-sep"></div>
        <div class="ctx-item" @click="ctxRename(contextMenu.entry)">Rename</div>
        <div class="ctx-item ctx-danger" @click="ctxDelete(contextMenu.entry)">Delete</div>
      </template>
      <template v-else-if="contextMenu.type === 'folder'">
        <div class="ctx-item" @click="ctxOpen(contextMenu.entry)">Open</div>
        <div class="ctx-sep"></div>
        <div class="ctx-item" @click="ctxCopyPath(contextMenu.entry)">Copy Path</div>
        <div class="ctx-item" @click="ctxCopyFullPath(contextMenu.entry)">Copy Full Path</div>
        <div class="ctx-sep"></div>
        <div class="ctx-item" @click="ctxReveal(contextMenu.entry)">Reveal in Explorer</div>
        <div class="ctx-sep"></div>
        <div class="ctx-item" @click="ctxRename(contextMenu.entry)">Rename</div>
        <div class="ctx-item ctx-danger" @click="ctxDelete(contextMenu.entry)">Delete</div>
      </template>
    </div>
  </section>
  </div>
</template>
