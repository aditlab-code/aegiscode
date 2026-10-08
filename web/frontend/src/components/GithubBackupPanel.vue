<script setup>
// GitHub Backup panel (OPTIONAL per project).
//
// SATU sumber konfigurasi dipakai bersama oleh halaman Backup (sidebar, project
// aktif) dan Projects (detail project). Panel ini HANYA memanggil HTTP gateway;
// tidak ada Git/checkpoint logic di frontend. Token TIDAK pernah dikembalikan
// backend (hanya `credential_set`), sehingga field token selalu kosong saat
// dibuka dan hanya dikirim saat user mengisi.
import { computed, reactive, ref, watch } from "vue";
import {
  createGithubCheckpoint,
  deinitProjectGit,
  getGithubConfig,
  getProjectGitBranches,
  initProjectGit,
  listGithubCheckpoints,
  restoreGithubCheckpoint,
  saveGithubConfig,
  testGithubConnection,
} from "../api";
import { computeGitGraph } from "../services/gitGraphLayout";

const props = defineProps({
  // Project (dari daftar launcher / active project): { id, name, root|path }.
  project: { type: Object, default: null },
  refreshKey: { type: Number, default: 0 },
});

const emit = defineEmits(["branch-info-updated", "checkpoint-created"]);

const loading = ref(false);
const busy = ref(false);
const initializingGit = ref(false);
const deinitializingGit = ref(false);
const confirmDeinit = ref(false);
const error = ref("");
const notice = ref("");

const config = ref({
  configured: false,
  enabled: false,
  repository: "",
  branch: "",
  exclude: [],
  credential_set: false,
  is_repository: false,
  current_branch: null,
  gitignore_ok: false,
  changes: { modified: 0, added: 0, deleted: 0, total: 0 },
});

const form = reactive({
  token: "",
  repository: "",
  branch: "main",
  excludeText: "",
});

const gitBranchInfo = ref(null);
const checkpoints = ref([]);
const checkpointDescription = ref("");
const restoreTarget = ref(null);
const restoring = ref(false);
const configureOpen = ref(false);
const checkpointsCollapsed = ref(false);

const currentBranchName = computed(() => {
  return gitBranchInfo.value?.current || config.value.current_branch || config.value.branch || "main";
});

const upstreamBranchName = computed(() => {
  return gitBranchInfo.value?.upstream || null;
});

const aheadCount = computed(() => {
  return gitBranchInfo.value?.ahead || 0;
});

const behindCount = computed(() => {
  return gitBranchInfo.value?.behind || 0;
});

const checkpointGraph = computed(() => {
  return computeGitGraph(checkpoints.value, { laneWidth: 14, rowHeight: 46, nodeRadius: 4 });
});

function projectId() {
  return props.project && (props.project.id || props.project.project_id);
}

function applyConfig(data) {
  config.value = { ...config.value, ...(data || {}) };
  // Token SELALU kosong: backend tidak pernah mengembalikannya.
  form.token = "";
  if (data) {
    form.repository = data.repository || "";
    form.branch = data.branch || "main";
    form.excludeText = (data.exclude || []).join("\n");
  }
}

const excludeList = () =>
  form.excludeText
    .split("\n")
    .map((s) => s.trim())
    .filter((s) => s && !s.startsWith("#"));

async function load() {
  const id = projectId();
  configureOpen.value = false;
  if (!id) {
    config.value = { ...config.value, configured: false, repository: "", branch: "" };
    gitBranchInfo.value = null;
    checkpoints.value = [];
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    applyConfig(await getGithubConfig(id));

    try {
      const bInfo = await getProjectGitBranches(id);
      if (bInfo?.is_repository) {
        gitBranchInfo.value = bInfo;
      } else {
        gitBranchInfo.value = null;
      }
    } catch (e) {
      gitBranchInfo.value = null;
    }
    emit("branch-info-updated", gitBranchInfo.value);

    if (config.value.configured || config.value.is_repository) {
      const data = await listGithubCheckpoints(id);
      checkpoints.value = data.checkpoints || [];
    } else {
      checkpoints.value = [];
    }
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    loading.value = false;
  }
}

async function save() {
  const id = projectId();
  if (!id) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    const payload = {
      repository: form.repository,
      branch: form.branch,
      exclude: excludeList(),
    };
    // Token hanya dikirim bila user mengisinya (tidak pernah ditampilkan ulang).
    if (form.token) payload.token = form.token;
    applyConfig(await saveGithubConfig(id, payload));
    notice.value = "Konfigurasi GitHub disimpan (token terenkripsi).";
    if (config.value.configured) {
      const data = await listGithubCheckpoints(id);
      checkpoints.value = data.checkpoints || [];
    }
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    busy.value = false;
  }
}

async function test() {
  const id = projectId();
  if (!id) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    const payload = { repository: form.repository, branch: form.branch };
    if (form.token) payload.token = form.token;
    const result = await testGithubConnection(id, payload);
    if (result.ok) {
      notice.value = result.message || "Connected successfully";
    } else {
      error.value = result.message || "Connection failed";
    }
  } catch (e) {
    error.value = e.message || "Connection failed";
  } finally {
    busy.value = false;
  }
}

async function commitCheckpoint() {
  const id = projectId();
  if (!id || !checkpointDescription.value.trim()) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    if (!config.value.configured && config.value.is_repository) {
      try {
        await saveGithubConfig(id, {
          repository: form.repository || config.value.repository || "",
          branch: form.branch || config.value.branch || config.value.current_branch || "main",
          exclude: excludeList(),
        });
      } catch (_) {}
    }
    const result = await createGithubCheckpoint(id, checkpointDescription.value.trim());
    checkpointDescription.value = "";
    notice.value = result.message || "Checkpoint dibuat.";
    if (result.push_error) error.value = result.push_error;
    const data = await listGithubCheckpoints(id);
    checkpoints.value = data.checkpoints || [];
    await refreshStatus(id);
    emit("checkpoint-created", result);
    error.value = e.message || String(e);
  } finally {
    busy.value = false;
  }
}

async function handleInitGit() {
  const id = projectId();
  if (!id) return;
  initializingGit.value = true;
  error.value = "";
  notice.value = "";
  try {
    const res = await initProjectGit(id);
    if (res?.ok || res?.is_repository) {
      notice.value = "Git repository initialized successfully.";
      await load();
    } else {
      error.value = res?.error || "Failed to initialize Git repository.";
    }
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    initializingGit.value = false;
  }
}

async function handleDeinitGit() {
  const id = projectId();
  if (!id) return;
  deinitializingGit.value = true;
  error.value = "";
  notice.value = "";
  try {
    const res = await deinitProjectGit(id);
    if (res?.ok) {
      notice.value = "Git repository de-initialized successfully.";
      confirmDeinit.value = false;
      configureOpen.value = false;
      await load();
    } else {
      error.value = res?.error || "Failed to de-initialize Git repository.";
    }
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    deinitializingGit.value = false;
  }
}

async function refreshStatus(id) {
  try {
    applyConfig(await getGithubConfig(id));
  } catch {
    /* status refresh best-effort */
  }
}

function askRestore(cp) {
  restoreTarget.value = cp;
  error.value = "";
  notice.value = "";
}

function cancelRestore() {
  restoreTarget.value = null;
}

async function confirmRestore() {
  const id = projectId();
  const target = restoreTarget.value;
  if (!id || !target) return;
  restoring.value = true;
  error.value = "";
  notice.value = "";
  try {
    const result = await restoreGithubCheckpoint(id, target.hash, true);
    notice.value = result.message || "Recovery selesai.";
    restoreTarget.value = null;
    await refreshStatus(id);
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    restoring.value = false;
  }
}

function formatCommitTime(ts) {
  if (!ts) return "—";
  const num = Number(ts);
  const timeMs = num > 1e11 ? num : num * 1000;
  const d = new Date(timeMs);
  if (Number.isNaN(d.getTime())) return String(ts);
  const diffSec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

watch(
  () => [projectId(), props.refreshKey],
  () => {
    load();
  },
  { immediate: true }
);
</script>

<template>
  <div class="sc-panel">
    <!-- Notice / Error Banner -->
    <div v-if="error" class="sc-alert err">
      <span class="sc-alert-text">{{ error }}</span>
      <button type="button" class="sc-alert-close" @click="error = ''">×</button>
    </div>
    <div v-if="notice" class="sc-alert ok">
      <span class="sc-alert-text">{{ notice }}</span>
      <button type="button" class="sc-alert-close" @click="notice = ''">×</button>
    </div>

    <div v-if="!project" class="sc-empty">Select a workspace first.</div>
    <div v-else-if="loading && !config.configured && !config.is_repository" class="sc-empty">Loading Source Control…</div>

    <!-- Non-Git repository view -->
    <div v-else-if="!config.is_repository" class="sc-non-repo-card">
      <div class="sc-non-repo-header">
        <svg class="sc-non-repo-ico" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span class="sc-non-repo-title">Workspace is not a Git repository</span>
      </div>
      <p class="sc-non-repo-desc">
        Folder ini tidak memiliki repositori Git lokal (.git). Perubahan atau histori repositori di luar workspace tidak ditampilkan demi isolasi proyek.
      </p>
      <div class="sc-non-repo-actions">
        <button
          type="button"
          class="sc-init-btn"
          :disabled="initializingGit || loading"
          @click="handleInitGit"
        >
          {{ initializingGit ? "Initializing…" : "Initialize Git Repository" }}
        </button>
        <button
          type="button"
          class="sc-refresh-outline-btn"
          :disabled="loading"
          title="Refresh detection"
          @click="load"
        >
          Refresh
        </button>
      </div>
    </div>

    <template v-else>
      <!-- Active Branch Card (Local branch, remote tracking, sync counts) -->
      <div class="sc-branch-card">
        <div class="sc-branch-top-row">
          <div class="sc-branch-chip local" :title="`Local Branch: ${currentBranchName}`">
            <svg class="sc-branch-ico" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>
            </svg>
            <span class="sc-branch-name mono">{{ currentBranchName }}</span>
          </div>

          <div v-if="upstreamBranchName" class="sc-branch-chip remote" :title="`Tracking remote branch: ${upstreamBranchName}`">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>
            </svg>
            <span class="sc-remote-name mono">{{ upstreamBranchName }}</span>
          </div>
          <span v-else class="sc-no-upstream" title="No remote tracking upstream configured">(no upstream)</span>

          <div class="sc-header-actions">
            <button
              type="button"
              class="sc-action-btn"
              :class="{ active: configureOpen }"
              :title="configureOpen ? 'Close Settings' : 'Remote & Token Settings'"
              @click="configureOpen = !configureOpen"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            </button>
            <button
              type="button"
              class="sc-action-btn"
              title="Refresh Git Status"
              :disabled="loading"
              @click="load"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Sync status pills (ahead / behind) -->
        <div v-if="upstreamBranchName" class="sc-branch-sync-row">
          <span class="sc-sync-stat" :class="{ highlight: aheadCount > 0 }">
            <span class="sync-arrow">↑</span> {{ aheadCount }} ahead
          </span>
          <span class="sc-sync-sep">·</span>
          <span class="sc-sync-stat" :class="{ highlight: behindCount > 0 }">
            <span class="sync-arrow">↓</span> {{ behindCount }} behind
          </span>
          <span v-if="aheadCount === 0 && behindCount === 0" class="sc-synced-badge">
            ✓ Up to date
          </span>
        </div>
      </div>

      <!-- Remote Configuration Drawer (collapsible) -->
      <div v-if="configureOpen" class="sc-config-box">
        <div class="sc-config-title">Remote &amp; Auth Configuration</div>
        <div class="sc-fields-stack">
          <label class="sc-field">
            <span class="sc-field-label">Repository URL</span>
            <input
              v-model="form.repository"
              class="sc-input"
              placeholder="https://github.com/owner/repo.git"
            />
          </label>
          <label class="sc-field">
            <span class="sc-field-label">Branch</span>
            <input v-model="form.branch" class="sc-input" placeholder="main" />
          </label>
          <label class="sc-field">
            <span class="sc-field-label">Access Token <span class="sc-hint">(Optional — uses local git credentials if empty)</span></span>
            <input
              v-model="form.token"
              class="sc-input"
              type="password"
              autocomplete="new-password"
              :placeholder="config.credential_set ? '•••••••• (saved)' : 'Optional: Personal Access Token'"
            />
          </label>
          <div class="sc-config-btn-row">
            <button class="sc-btn sc-btn-primary" type="button" :disabled="busy" @click="save">
              Save
            </button>
            <button class="sc-btn sc-btn-secondary" type="button" :disabled="busy" @click="test">
              Test Connection
            </button>
          </div>

          <!-- Danger Zone: De-initialize Git -->
          <div class="sc-danger-zone">
            <div class="sc-danger-title">Danger Zone</div>
            <div v-if="!confirmDeinit" class="sc-danger-action-row">
              <button
                class="sc-btn sc-danger-btn"
                type="button"
                :disabled="busy || deinitializingGit"
                @click="confirmDeinit = true"
              >
                De-initialize Git Repository
              </button>
            </div>
            <div v-else class="sc-danger-confirm-card">
              <span class="sc-danger-warning">
                Hapus direktori lokal .git? Seluruh riwayat commit lokal akan dihapus dan proyek kembali ke status non-repository.
              </span>
              <div class="sc-danger-confirm-btns">
                <button
                  class="sc-btn sc-confirm-danger-yes-btn"
                  type="button"
                  :disabled="deinitializingGit"
                  @click="handleDeinitGit"
                >
                  {{ deinitializingGit ? "Removing…" : "Yes, Delete .git" }}
                </button>
                <button
                  class="sc-btn sc-confirm-danger-no-btn"
                  type="button"
                  :disabled="deinitializingGit"
                  @click="confirmDeinit = false"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Commit Box (Top-level IDE pattern) -->
      <div v-if="config.configured || config.is_repository" class="sc-commit-block">
        <div class="sc-commit-card">
          <textarea
            v-model="checkpointDescription"
            class="sc-commit-textarea"
            rows="2"
            placeholder="Message (Cmd+Enter to commit)..."
            @keydown.cmd.enter="commitCheckpoint"
            @keydown.ctrl.enter="commitCheckpoint"
          ></textarea>
          <button
            class="sc-commit-submit-btn"
            type="button"
            :disabled="busy || !checkpointDescription.trim()"
            @click="commitCheckpoint"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            <span>Create Checkpoint</span>
          </button>
        </div>
      </div>

      <!-- Injected Changes Panel Slot -->
      <slot />
      <!-- Checkpoints Section Header & List -->
      <div v-if="config.configured || config.is_repository" class="sc-checkpoints-section">
        <div class="drawer-sec-head sc-sec-head" @click="checkpointsCollapsed = !checkpointsCollapsed">
          <span class="sec-caret sc-caret" aria-hidden="true">{{ checkpointsCollapsed ? "▸" : "▾" }}</span>
          <span class="drawer-sec-title sc-sec-title">CHECKPOINTS</span>
          <div class="drawer-sec-actions">
            <span class="drawer-badge sc-sec-badge">{{ checkpoints.length }}</span>
          </div>
        </div>

        <div v-show="!checkpointsCollapsed" class="sc-checkpoints-body">
          <div v-if="!checkpointGraph.length" class="sc-empty-hint">No checkpoints yet.</div>
          <div v-else class="sc-cp-list">
            <div v-for="cp in checkpointGraph" :key="cp.hash" class="sc-cp-row-with-graph">
              <!-- Inline SVG Railway Graph Track Column -->
              <div class="sc-graph-track-col" :style="{ width: `${cp.graphWidth}px` }">
                <svg
                  class="sc-graph-svg"
                  :width="cp.graphWidth"
                  :height="cp.rowHeight"
                  :viewBox="`0 0 ${cp.graphWidth} ${cp.rowHeight}`"
                >
                  <!-- Tracks (vertical continuity or curves) -->
                  <path
                    v-for="(track, tIdx) in cp.tracks"
                    :key="tIdx"
                    :d="track.d"
                    :stroke="track.color"
                    stroke-width="1.8"
                    fill="none"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                  <!-- Commit Node Circle -->
                  <circle
                    :cx="cp.cx"
                    :cy="cp.cy"
                    :r="cp.r"
                    :fill="cp.color"
                    stroke="var(--bg-deep, #14121b)"
                    stroke-width="2"
                  />
                </svg>
              </div>

              <!-- Checkpoint Content -->
              <div class="sc-cp-content">
                <div class="sc-cp-msg-row">
                  <!-- Ref Badges (HEAD, main, origin/main, tags) -->
                  <span
                    v-for="(refItem, rIdx) in cp.parsedRefs"
                    :key="rIdx"
                    class="sc-ref-pill"
                    :class="`ref-${refItem.type}`"
                    :title="refItem.label"
                  >
                    <span v-if="refItem.type === 'head'" class="ref-dot">●</span>
                    {{ refItem.name }}
                  </span>
                  <span class="sc-cp-msg" :title="cp.subject">{{ cp.subject }}</span>
                </div>
                <div class="sc-cp-meta-row">
                  <div class="sc-cp-meta-left">
                    <span class="sc-cp-hash mono">{{ cp.short_hash || (cp.hash || "").slice(0, 7) }}</span>
                    <span class="sc-cp-sep">·</span>
                    <span class="sc-cp-time">{{ formatCommitTime(cp.timestamp) }}</span>
                  </div>
                  <button
                    class="sc-restore-action"
                    type="button"
                    title="Restore workspace to this checkpoint"
                    :disabled="busy || restoring"
                    @click="askRestore(cp)"
                  >
                    Restore
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Restore Confirmation Floating Modal (Without Overlay) -->
      <Teleport to="body">
        <div v-if="restoreTarget" class="sc-restore-modal" role="dialog" aria-modal="true" aria-labelledby="restore-modal-title">
          <div class="sc-restore-head-row">
            <div id="restore-modal-title" class="sc-restore-head">Restore Checkpoint?</div>
            <button type="button" class="sc-restore-close" title="Close" aria-label="Cancel" @click="cancelRestore">×</button>
          </div>
          <div class="sc-restore-desc">
            Are you sure you want to restore workspace to commit <span class="sc-commit-hash mono">{{ restoreTarget.short_hash || restoreTarget.hash?.slice(0, 7) }}</span>?
            <div class="sc-restore-target-subject">"{{ restoreTarget.subject }}"</div>
          </div>
          <div class="sc-restore-actions">
            <button class="sc-btn sc-btn-secondary" type="button" :disabled="restoring" @click="cancelRestore">
              Cancel
            </button>
            <button class="sc-btn sc-btn-danger" type="button" :disabled="restoring" @click="confirmRestore">
              {{ restoring ? "Restoring..." : "Restore" }}
            </button>
          </div>
        </div>
      </Teleport>
    </template>
  </div>
</template>

<style scoped>
.sc-panel {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0;
  width: 100%;
  box-sizing: border-box;
}

.sc-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 11.5px;
  line-height: 1.4;
}
.sc-alert.ok {
  background: rgba(45, 125, 78, 0.15);
  border: 1px solid var(--accent, #2d7d4e);
  color: #86efac;
}
.sc-alert.err {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.35);
  color: #fca5a5;
}
.sc-alert-close {
  background: transparent;
  border: none;
  color: inherit;
  font-size: 14px;
  cursor: pointer;
  padding: 0 4px;
}

.sc-empty {
  color: var(--text-faint);
  font-size: 12px;
  padding: 8px 0;
}

/* Non-repository card */
.sc-non-repo-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  margin: 10px;
  background: var(--bg-surface);
  border: 1px dashed var(--border-soft);
  border-radius: 6px;
  box-sizing: border-box;
}

.sc-non-repo-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-normal, #e2e8f0);
}

.sc-non-repo-ico {
  color: var(--warning, #f59e0b);
  flex-shrink: 0;
}

.sc-non-repo-title {
  font-size: 12px;
  font-weight: 600;
}

.sc-non-repo-desc {
  margin: 0;
  font-size: 11.5px;
  line-height: 1.45;
  color: var(--text-faint, #94a3b8);
}

.sc-non-repo-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.sc-init-btn {
  background: var(--accent, #3b82f6);
  color: #ffffff;
  border: none;
  border-radius: 4px;
  padding: 5px 12px;
  font-size: 11.5px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.sc-init-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.sc-init-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sc-refresh-outline-btn {
  background: transparent;
  color: var(--text-normal, #e2e8f0);
  border: 1px solid var(--border-soft);
  border-radius: 4px;
  padding: 5px 10px;
  font-size: 11.5px;
  cursor: pointer;
}

.sc-refresh-outline-btn:hover:not(:disabled) {
  background: var(--bg-hover, rgba(255, 255, 255, 0.05));
}

/* Active Branch Card & Header */
.sc-branch-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 10px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-soft);
  box-sizing: border-box;
}

.sc-branch-top-row {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  min-width: 0;
}

.sc-branch-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 4px;
  min-width: 0;
  max-width: 45%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sc-branch-chip.local {
  background: rgba(16, 240, 154, 0.12);
  color: var(--accent, #10f09a);
  border: 1px solid rgba(16, 240, 154, 0.25);
}

.sc-branch-chip.remote {
  background: rgba(120, 119, 198, 0.12);
  color: var(--text-dim, #b8b3d0);
  border: 1px solid var(--border-soft);
  font-size: 11px;
  font-weight: 500;
}

.sc-remote-name,
.sc-branch-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sc-branch-ico {
  color: var(--accent);
  flex-shrink: 0;
}

.sc-no-upstream {
  font-size: 11px;
  color: var(--text-faint, #6f6885);
  font-style: italic;
}

.sc-branch-sync-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10.5px;
  color: var(--text-faint);
  padding: 1px 2px;
}

.sc-sync-stat {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.sc-sync-stat.highlight {
  color: var(--accent, #10f09a);
  font-weight: 600;
}

.sc-sync-sep {
  opacity: 0.4;
}

.sc-synced-badge {
  color: var(--accent, #10f09a);
  font-size: 10.5px;
  font-weight: 500;
  opacity: 0.9;
}

.sync-arrow {
  font-weight: 700;
}

.sc-header-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.sc-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-dim);
  border-radius: 4px;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}
.sc-action-btn:hover {
  color: var(--text);
  background: var(--bg-hover);
}
.sc-action-btn.active {
  color: var(--accent);
  background: var(--accent-soft);
}

/* Remote Config Drawer */
.sc-config-box {
  padding: 8px 10px;
  background: var(--bg-card);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sc-config-title {
  font-size: 11px;
  font-weight: 650;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--text-dim);
}
.sc-fields-stack {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sc-field {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.sc-field-label {
  font-size: 11px;
  color: var(--text-faint);
}
.sc-hint {
  font-size: 9.5px;
  color: var(--text-faint);
}
.sc-input {
  width: 100%;
  box-sizing: border-box;
  padding: 5px 8px;
  font-size: 11.5px;
  font-family: var(--mono);
  background: var(--bg-surface);
  border: 1px solid var(--border-soft);
  color: var(--text);
  border-radius: 4px;
  outline: none;
}
.sc-input:focus {
  border-color: var(--accent);
}
.sc-config-btn-row {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}

/* Danger Zone */
.sc-danger-zone {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--border-soft);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sc-danger-title {
  font-size: 10.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--danger, #ef4444);
}
.sc-danger-action-row {
  display: flex;
}
.sc-danger-btn {
  background: transparent;
  color: var(--danger, #ef4444);
  border: 1px solid rgba(239, 68, 68, 0.4);
  border-radius: 4px;
  padding: 5px 10px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.sc-danger-btn:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.12);
  border-color: var(--danger, #ef4444);
}
.sc-danger-confirm-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 10px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 4px;
}
.sc-danger-warning {
  font-size: 11px;
  line-height: 1.4;
  color: var(--text-normal, #fca5a5);
}
.sc-danger-confirm-btns {
  display: flex;
  gap: 6px;
  margin-top: 2px;
}
.sc-confirm-danger-yes-btn {
  background: var(--danger, #ef4444);
  color: #ffffff;
  border: none;
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
}
.sc-confirm-danger-yes-btn:hover:not(:disabled) {
  opacity: 0.9;
}
.sc-confirm-danger-no-btn {
  background: transparent;
  color: var(--text-normal);
  border: 1px solid var(--border-soft);
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 11px;
  cursor: pointer;
}

/* Commit Block */
.sc-commit-block {
  width: 100%;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border-soft);
  box-sizing: border-box;
  background: var(--bg-surface);
}
.sc-commit-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}
.sc-commit-textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 6px 8px;
  font-size: 11.5px;
  font-family: inherit;
  background: var(--bg-card);
  border: 1px solid var(--border-soft);
  color: var(--text);
  border-radius: 4px;
  resize: none;
  min-height: 44px;
  max-height: 100px;
  outline: none;
  line-height: 1.4;
}
.sc-commit-textarea:focus {
  border-color: var(--accent);
}
.sc-commit-submit-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  width: 100%;
  height: 26px;
  padding: 0 10px;
  background: var(--accent);
  border: 1px solid var(--accent);
  color: #ffffff;
  font-size: 11.5px;
  font-weight: 500;
  border-radius: 4px;
  cursor: pointer;
  transition: opacity 0.15s ease;
}
.sc-commit-submit-btn:hover:not(:disabled) {
  opacity: 0.9;
}
.sc-commit-submit-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* Checkpoints Section */
.sc-checkpoints-section {
  display: flex;
  flex-direction: column;
  width: 100%;
}
.sc-sec-head {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  min-height: 30px;
  max-height: 30px;
  padding: 0 8px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-soft);
  cursor: pointer;
  user-select: none;
  box-sizing: border-box;
  margin: 0;
  transition: background 0.12s ease;
}
.sc-sec-head:hover {
  background: var(--bg-hover);
}
.sc-caret {
  font-size: 11px;
  color: var(--text-faint);
}
.sc-sec-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-faint);
  white-space: nowrap;
}
.sc-sec-badge {
  font-size: 10px;
  padding: 1px 6px;
  background: var(--bg-hover);
  border-radius: 10px;
  color: var(--text-faint);
  margin-left: auto;
}
.sc-checkpoints-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sc-empty-hint {
  font-size: 11.5px;
  color: var(--text-faint);
  padding: 4px 6px;
}

.sc-cp-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
/* Checkpoint Rows with Railway Graph */
.sc-cp-row-with-graph {
  display: flex;
  align-items: stretch;
  gap: 0;
  min-height: 48px;
  background: transparent;
  border-bottom: 1px solid var(--border-soft);
  transition: background 0.12s ease;
  position: relative;
}

.sc-cp-row-with-graph:hover {
  background: var(--bg-hover);
}

.sc-graph-track-col {
  flex-shrink: 0;
  position: relative;
  display: flex;
  justify-content: center;
  overflow: visible;
}

.sc-graph-svg {
  display: block;
  overflow: visible;
}

.sc-cp-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  padding: 6px 8px 6px 4px;
}

.sc-cp-msg-row {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
  flex-wrap: wrap;
}

.sc-ref-pill {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  line-height: 1.2;
  padding: 1px 5px;
  border-radius: 3px;
  font-family: monospace;
  font-weight: 600;
  flex-shrink: 0;
  max-width: 130px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sc-ref-pill.ref-head {
  background: rgba(16, 240, 154, 0.18);
  color: var(--accent, #10f09a);
  border: 1px solid rgba(16, 240, 154, 0.4);
}

.sc-ref-pill.ref-branch {
  background: rgba(56, 189, 248, 0.15);
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.3);
}

.sc-ref-pill.ref-remote {
  background: rgba(168, 85, 247, 0.15);
  color: #c084fc;
  border: 1px solid rgba(168, 85, 247, 0.3);
}

.sc-ref-pill.ref-tag {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.ref-dot {
  font-size: 8px;
  color: var(--accent, #10f09a);
}

.sc-cp-msg {
  font-size: 11.5px;
  font-weight: 500;
  color: var(--text);
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.sc-cp-meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  margin-top: 2px;
}

.sc-cp-meta-left {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-faint);
}

.sc-cp-hash {
  color: var(--accent-muted);
}

.sc-cp-sep {
  opacity: 0.5;
}

.sc-restore-action {
  font-size: 10.5px;
  padding: 1px 6px;
  background: transparent;
  border: 1px solid var(--border-soft);
  color: var(--text-dim);
  border-radius: 3px;
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease;
}

.sc-restore-action:hover:not(:disabled) {
  color: var(--text);
  border-color: var(--accent);
}

/* Restore Dialog (Modal without overlay) */
.sc-restore-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.sc-restore-head {
  font-size: 14px;
  font-weight: 700;
  color: var(--err, #dc2626);
}
.sc-restore-close {
  background: transparent;
  border: none;
  font-size: 18px;
  line-height: 1;
  color: var(--text-faint, #756e8b);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}
.sc-restore-close:hover {
  background: var(--bg-hover, rgba(255, 255, 255, 0.08));
  color: var(--text, #f4f3f8);
}
.sc-restore-desc {
  font-size: 13px;
  color: var(--text-dim, #a8a2bc);
  line-height: 1.5;
}
.sc-commit-hash {
  color: var(--accent, #10f09a);
  font-weight: 600;
}
.sc-restore-target-subject {
  margin-top: 6px;
  padding: 8px 12px;
  background: var(--bg-deep, #12111a);
  border-radius: 6px;
  border: 1px solid var(--border-soft, #2b263b);
  font-style: italic;
  font-size: 12px;
  color: var(--text, #f4f3f8);
}
.sc-restore-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 6px;
}

/* General button helpers */
.sc-btn {
  font-size: 11.5px;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
}
.sc-btn-primary {
  background: var(--accent);
  border: 1px solid var(--accent);
  color: #ffffff;
}
.sc-btn-secondary {
  background: transparent;
  border: 1px solid var(--border-soft);
  color: var(--text-dim);
}
.sc-btn-secondary:hover {
  color: var(--text);
  border-color: var(--border-subtle);
}
.sc-btn-danger {
  background: var(--err, #dc2626);
  border: 1px solid var(--err, #dc2626);
  color: #ffffff;
}
</style>

<style>
/* Teleported Restore Modal without dark overlay */
.sc-restore-modal {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 90%;
  max-width: 440px;
  background: var(--bg-elev, #1e1c29);
  border: 1px solid var(--border, #38324a);
  border-radius: 10px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(255, 255, 255, 0.08);
  padding: 18px 20px;
  z-index: 99999;
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: var(--text, #f4f3f8);
  font-family: inherit;
  box-sizing: border-box;
}

[data-theme="light"] .sc-restore-modal {
  background: var(--bg-card, #fbf7f0);
  border-color: var(--border, #c8bba9);
  box-shadow: 0 20px 60px rgba(69, 43, 34, 0.22), 0 0 0 1px rgba(0, 0, 0, 0.08);
  color: var(--text, #180c06);
}

[data-theme="light"] .sc-restore-desc {
  color: var(--text-dim, #4a3628);
}

[data-theme="light"] .sc-restore-target-subject {
  background: var(--bg-deep, #efe6db);
  border-color: var(--border-soft, #dcd1c3);
  color: var(--text, #180c06);
}
</style>

