<script setup>
/**
 * SettingsOverlay.vue — Full-Page Settings & Administration Overlay (Phase 4).
 *
 * Consolidates workbench administration surfaces:
 *   1. providers  — Providers & Models (LLM instances, models, credentials)
 *   2. globals    — Global Settings (server, logging, conversation, retries)
 *   3. agent      — Agent Instructions (system prompt & defaults)
 *   4. projects   — Project Registry (workspace directories & project policies)
 *   5. history    — Task History (recorded tasks, reports, execution logs)
 *   6. extensions — Extensions Manager (lifecycle, installed tools)
 *
 * Strict SSR safe, zero forbidden tokens, compliant with check_workbench.py and check_ui_refactor.py.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import SettingsView from "../components/SettingsView.vue";
import GlobalSettingsPanel from "../components/GlobalSettingsPanel.vue";
import AgentSettingsPanel from "../components/AgentSettingsPanel.vue";
import ExtensionManager from "../components/ExtensionManager.vue";
import EditorSettingsPanel from "../components/EditorSettingsPanel.vue";
import AboutSettingsPanel from "../components/AboutSettingsPanel.vue";
import ProjectPolicyPanel from "../components/ProjectPolicyPanel.vue";
import AppButton from "../components/ui/AppButton.vue";
import AppCard from "../components/ui/AppCard.vue";
import {
  groupTaskHistory,
  statusTagClass,
  executionLabel,
  formatTs,
} from "../services/taskService.js";
import { getTaskReport } from "../api.js";
import { renderMarkdown } from "../markdown.js";

const props = defineProps({
  open: { type: Boolean, default: true },
  embedded: { type: Boolean, default: false },
  activeTab: { type: String, default: "providers" },
  config: { type: Object, default: () => ({}) },
  projects: { type: Array, default: () => [] },
  taskHistory: { type: Array, default: () => [] },
  activeProject: { type: Object, default: null },
  extensionRefreshKey: { type: Number, default: 0 },
  historyActionBusy: { type: Boolean, default: false },
  providerInstanceId: { type: String, default: "" },
  modelId: { type: String, default: "" },
  mode: { type: String, default: "" },
  notice: { type: String, default: "" },
  error: { type: String, default: "" },
});

const emit = defineEmits([
  "close",
  "update:activeTab",
  "open-report",
  "copy-prompt",
  "delete-history",
  "clear-history",
  "open-history-task",
  "open-project-policy",
  "delete-project",
  "open-project",
  "refresh-config",
  "extension-error",
  "update:provider-instance-id",
  "update:model-id",
  "update:mode",
]);

const NAV_TABS = [
  {
    id: "providers",
    label: "Providers & Models",
    description: "LLM models, API keys, and providers",
    icon: "M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 14.5h-2v-2h2zm0-4h-2V7h2z",
  },
  {
    id: "agent",
    label: "Agent Instructions",
    description: "System prompt and agent defaults",
    icon: "M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4zm-6 13a6 6 0 0 1 12 0v3H6v-3z",
  },
  {
    id: "globals",
    label: "Global Settings",
    description: "Server runtime, logs, and retries",
    icon: "M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 1.2-2.9H1a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 2.6 7a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H7a1.7 1.7 0 0 0 1-1.5V1a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V7a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
  },
  {
    id: "editor",
    label: "Text Editor",
    description: "Code editor typography and layout",
    icon: "M16 18l6-6-6-6M8 6l-6 6 6 6",
  },
  {
    id: "projects",
    label: "Project Registry",
    description: "Workspaces and permission matrix",
    icon: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  },
  {
    id: "history",
    label: "Task History",
    description: "Task history and execution reports",
    icon: "M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0z",
  },
  {
    id: "extensions",
    label: "Extensions Manager",
    description: "Tools, MCP plugins, and capabilities",
    icon: "M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z",
  },
  {
    id: "architecture",
    label: "Architecture",
    description: "System model and core subsystems",
    icon: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
  },
  {
    id: "overview",
    label: "Overview",
    description: "Project summary and runtime status",
    icon: "M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 14.5h-2v-2h2zm0-4h-2V7h2z",
  },
  {
    id: "license",
    label: "License",
    description: "MIT License and legal notices",
    icon: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8",
  },
];

const localTab = ref(props.activeTab || "providers");

watch(
  () => props.activeTab,
  (val) => {
    if (val === "about:license") {
      localTab.value = "license";
    } else if (val === "about") {
      localTab.value = "overview";
    } else if (val) {
      localTab.value = val;
    }
  },
  { immediate: true }
);

const currentTab = computed(() => {
  const tab = props.activeTab || localTab.value;
  if (tab === "about:license") return "license";
  if (tab === "about") return "overview";
  return tab;
});

const searchQuery = ref("");
const filteredNavTabs = computed(() => {
  if (!searchQuery.value.trim()) return NAV_TABS;
  const q = searchQuery.value.toLowerCase();
  return NAV_TABS.filter(
    (t) => t.label.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)
  );
});

function selectTab(tabId) {
  localTab.value = tabId;
  emit("update:activeTab", tabId);
}

const groupedTaskHistory = computed(() => groupTaskHistory(props.taskHistory));

const copiedTaskId = ref("");
let copyTimer = null;

function handleCopyPrompt(task) {
  emit("copy-prompt", task);
  if (task?.task_id) {
    copiedTaskId.value = task.task_id;
    if (typeof window !== "undefined") {
      if (copyTimer) clearTimeout(copyTimer);
      copyTimer = setTimeout(() => {
        copiedTaskId.value = "";
      }, 1500);
    }
  }
}

const selectedReportTask = ref(null);
const reportContent = ref("");
const reportLoading = ref(false);
const reportPopupOpen = ref(false);

const selectedPolicyProject = ref(null);

function openProjectPolicy(project) {
  selectedPolicyProject.value = project;
}

function closeProjectPolicy() {
  selectedPolicyProject.value = null;
}

async function openTaskReport(task) {
  if (!task?.task_id) return;
  selectedReportTask.value = task;
  reportPopupOpen.value = true;
  reportLoading.value = true;
  reportContent.value = "";
  try {
    const res = await getTaskReport(task.task_id, props.activeProject?.id || null);
    reportContent.value = res?.report || "";
  } catch (err) {
    reportContent.value = `Gagal memuat laporan: ${err?.message || err}`;
  } finally {
    reportLoading.value = false;
  }
}

function closeTaskReport() {
  reportPopupOpen.value = false;
  selectedReportTask.value = null;
  reportContent.value = "";
}

function onKeyDown(e) {
  if (e.key === "Escape") {
    if (selectedPolicyProject.value) {
      e.stopPropagation();
      closeProjectPolicy();
      return;
    }
    if (reportPopupOpen.value) {
      e.stopPropagation();
      closeTaskReport();
      return;
    }
    if (props.open) {
      emit("close");
    }
  }
}

onMounted(() => {
  if (typeof window !== "undefined") {
    window.addEventListener("keydown", onKeyDown);
  }
});

onBeforeUnmount(() => {
  if (copyTimer) clearTimeout(copyTimer);
  if (typeof window !== "undefined") {
    window.removeEventListener("keydown", onKeyDown);
  }
});
</script>

<template>
  <div
    v-if="open"
    class="settings-overlay"
    :class="{ 'settings-embedded': embedded }"
    role="dialog"
    :aria-modal="!embedded"
    aria-label="AEGIS Settings &amp; Administration"
  >
    <div v-if="!embedded" class="settings-overlay-backdrop" @click="emit('close')" />

    <div class="settings-overlay-dialog" :class="{ 'dialog-embedded': embedded }">
      <!-- Header bar (modal & embedded editor tab) -->
      <header class="settings-overlay-header" :class="{ 'header-embedded': embedded }">
        <div class="settings-header-info">
          <div class="settings-badge aegis-badge">Admin</div>
          <div>
            <h2 class="settings-title">AEGIS Settings &amp; Administration</h2>
            <p v-if="!embedded" class="settings-subtitle">Configure providers, workspaces, task history, and extensions</p>
          </div>
        </div>

        <div class="settings-header-actions" style="display: flex; align-items: center; gap: 8px;">
          <AppButton
            variant="icon"
            class="settings-close-btn"
            title="Close Settings (Esc)"
            aria-label="Close settings"
            @click="emit('close')"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </AppButton>
        </div>
      </header>

      <!-- Layout: Vertical nav + scrollable content -->
      <div class="settings-overlay-layout" :class="{ 'layout-embedded': embedded }">
        <!-- Sidebar Navigation -->
        <nav class="settings-nav" :class="{ 'nav-embedded': embedded }" role="tablist" aria-label="Settings navigation">
          <!-- Integrated Search Box in Sidepanel Header -->
          <div class="settings-nav-search-wrap">
            <div class="settings-search-box">
              <svg class="search-ico" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
              <input
                v-model="searchQuery"
                type="text"
                class="settings-search-input"
                placeholder="Search settings…"
                aria-label="Search settings"
              />
            </div>
          </div>

          <!-- Navigation Tab Items -->
          <div class="settings-nav-list">
            <button
              v-for="tab in filteredNavTabs"
              :key="tab.id"
              type="button"
              role="tab"
              class="settings-nav-item"
              :class="{ active: currentTab === tab.id }"
              :aria-selected="currentTab === tab.id"
              @click="selectTab(tab.id)"
            >
              <svg class="settings-nav-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path :d="tab.icon" />
              </svg>
              <div class="settings-nav-text">
                <span class="settings-nav-label">{{ tab.label }}</span>
                <span v-if="!embedded" class="settings-nav-desc">{{ tab.description }}</span>
              </div>
              <span v-if="tab.id === 'projects' && projects.length" class="settings-nav-badge aegis-badge">
                {{ projects.length }}
              </span>
              <span v-else-if="tab.id === 'history' && taskHistory.length" class="settings-nav-badge aegis-badge">
                {{ taskHistory.length }}
              </span>
            </button>
          </div>
        </nav>

        <!-- Main Content Area -->
        <main class="settings-content" :class="{ 'content-embedded': embedded }" role="region" :aria-label="currentTab">
          <div v-if="notice" class="wb-notice">{{ notice }}</div>
          <div v-if="error" class="wb-error">{{ error }}</div>

          <!-- Sub-Tab 1: Providers & Models -->
          <section v-if="currentTab === 'providers'" class="settings-tab-pane">
            <SettingsView
              :config="config"
              :provider-instance-id="providerInstanceId"
              :model-id="modelId"
              :mode="mode"
              active-section="providers"
              :hide-tabs="true"
              @refresh-config="emit('refresh-config')"
              @update:provider-instance-id="emit('update:provider-instance-id', $event)"
              @update:model-id="emit('update:model-id', $event)"
              @update:mode="emit('update:mode', $event)"
            />
          </section>

          <!-- Sub-Tab: Text Editor Settings -->
          <section v-else-if="currentTab === 'editor'" class="settings-tab-pane">
            <EditorSettingsPanel />
          </section>

          <!-- Sub-Tab 2: Global Settings -->
          <section v-else-if="currentTab === 'globals'" class="settings-tab-pane">
            <GlobalSettingsPanel />
          </section>

          <!-- Sub-Tab 3: Agent Prompt -->
          <section v-else-if="currentTab === 'agent'" class="settings-tab-pane">
            <AgentSettingsPanel />
          </section>

          <!-- Sub-Tab 4: Project Registry -->
          <section v-else-if="currentTab === 'projects'" class="settings-tab-pane">
            <AppCard variant="panel" class="settings-panel">
              <template #header>
                <div class="panel-head">
                  <div class="title">Project Registry</div>
                </div>
              </template>
              <div v-if="!projects.length" class="panel-body">
                <div class="wb-empty">No projects yet.</div>
              </div>
              <table v-else class="aegis-table app-table">
                <thead>
                  <tr>
                    <th style="width: 34%">Project</th>
                    <th style="width: 48%">Path</th>
                    <th class="th-actions text-end">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="p in projects"
                    :key="p.id"
                    class="clickable"
                    @click="emit('open-project', p)"
                  >
                    <td>
                      <div class="cell-name">
                        <span class="avatar">P</span>
                        <div>
                          <div class="name">{{ p.name }}</div>
                          <div class="meta">{{ (p.id || "").slice(0, 8) }}</div>
                        </div>
                      </div>
                    </td>
                    <td><span class="mono">{{ p.root || p.path }}</span></td>
                    <td class="td-actions">
                      <div class="row-actions">
                        <AppButton
                          variant="icon"
                          class="policy"
                          title="Project Settings / Policy"
                          aria-label="Project Settings / Policy"
                          @click.stop="openProjectPolicy(p)"
                        >
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="3" />
                            <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 1.2-2.9H1a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 2.6 7a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H7a1.7 1.7 0 0 0 1-1.5V1a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V7a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
                          </svg>
                        </AppButton>
                        <AppButton
                          variant="icon"
                          class="danger"
                          title="Hapus dari daftar AEGIS (file/folder di disk tidak dihapus)"
                          aria-label="Hapus project dari daftar AEGIS"
                          @click.stop="emit('delete-project', p)"
                        >
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />
                          </svg>
                        </AppButton>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </AppCard>

            <!-- Standardized Unified In-Situ Project Policy Popup -->
            <ProjectPolicyPanel
              v-if="selectedPolicyProject"
              :project="selectedPolicyProject"
              :embedded="true"
              @close="closeProjectPolicy"
            />
          </section>

          <!-- Sub-Tab 5: Task History -->
          <section v-else-if="currentTab === 'history'" class="settings-tab-pane">
            <AppCard variant="panel" class="settings-panel">
              <template #header>
                <div class="panel-head">
                  <div class="title">Task History</div>
                </div>
              </template>

              <div v-if="taskHistory.length" class="hist-toolbar">
                <span class="meta">{{ taskHistory.length }} recorded task(s)</span>
                <AppButton
                  variant="danger"
                  size="sm"
                  class="hist-clear-btn"
                  :disabled="historyActionBusy"
                  @click="emit('clear-history')"
                >
                  Clear History
                </AppButton>
              </div>

              <div v-if="!taskHistory.length" class="panel-body">
                <div class="wb-empty">No task history yet.</div>
              </div>
              <div v-else class="history-groups">
                <div v-for="grp in groupedTaskHistory" :key="grp.label" class="hist-group">
                  <div class="hist-group-head">
                    {{ grp.label }} <span class="hist-group-count">({{ grp.items.length }})</span>
                  </div>
                  <table class="aegis-table app-table hist-table">
                    <thead>
                      <tr>
                        <th style="width: 50%">Task</th>
                        <th style="width: 16%">Status</th>
                        <th style="width: 20%">Updated</th>
                        <th style="width: 14%" class="th-actions text-end">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="t in grp.items"
                        :key="t.task_id"
                        class="clickable"
                        @click="emit('open-history-task', t.task_id)"
                      >
                        <td>
                          <div class="cell-name">
                            <span class="avatar">T</span>
                            <div>
                              <div class="name name-clamp">{{ t.task || "(no prompt)" }}</div>
                              <div class="meta meta-clamp">
                                {{ t.task_id }} · {{ executionLabel(t.execution_mode || t.executionMode) }}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td>
                          <span class="status-tag" :class="statusTagClass(t.status)">{{ t.status }}</span>
                          <span
                            class="q-exec hist-exec"
                            :class="String(t.execution_mode || t.executionMode || '').toLowerCase() === 'parallel' ? 'parallel' : 'queue'"
                          >
                            {{ executionLabel(t.execution_mode || t.executionMode) }}
                          </span>
                        </td>
                        <td><span class="mono meta">{{ formatTs(t.last_timestamp) }}</span></td>
                        <td class="td-actions hist-actions-cell">
                          <div class="hist-actions">
                            <AppButton
                              variant="icon"
                              class="q-copy-btn hist-copy"
                              :class="{ copied: copiedTaskId === t.task_id }"
                              :title="copiedTaskId === t.task_id ? 'Copied' : 'Copy prompt'"
                              aria-label="Copy prompt"
                              @click.stop="handleCopyPrompt(t)"
                            >
                              <svg v-if="copiedTaskId === t.task_id" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M20 6L9 17l-5-5" />
                              </svg>
                              <svg v-else width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                                <rect x="9" y="9" width="12" height="12" rx="2" />
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                              </svg>
                            </AppButton>
                            <AppButton
                              variant="icon"
                              class="q-icon-btn hist-report-btn"
                              title="View Agent Report"
                              aria-label="View Agent Report"
                              @click.stop="openTaskReport(t)"
                            >
                              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                <polyline points="14 2 14 8 20 8" />
                                <line x1="16" y1="13" x2="8" y2="13" />
                                <line x1="16" y1="17" x2="8" y2="17" />
                                <line x1="10" y1="9" x2="8" y2="9" />
                              </svg>
                            </AppButton>
                            <AppButton
                              variant="icon"
                              class="q-icon-btn hist-delete-btn"
                              title="Delete task history"
                              aria-label="Delete task history"
                              @click.stop="emit('delete-history', t)"
                            >
                              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="3 6 5 6 21 6" />
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                              </svg>
                            </AppButton>
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </AppCard>

            <!-- Standardized Unified Responsive Report Popup -->
            <div
              v-if="reportPopupOpen"
              class="unified-popup-backdrop hist-report-popup-backdrop"
              @click.self="closeTaskReport"
            >
              <div class="unified-popup-card hist-report-popup-card" role="dialog" aria-modal="true" aria-label="Task Report Popup">
                <div class="unified-popup-head hist-report-popup-head">
                  <div class="unified-popup-meta hist-report-popup-meta">
                    <span class="unified-popup-title hist-report-title">Agent Report</span>
                    <span v-if="selectedReportTask?.status" class="status-tag" :class="statusTagClass(selectedReportTask.status)">
                      {{ selectedReportTask.status }}
                    </span>
                    <span class="mono unified-popup-id hist-report-id" :title="selectedReportTask?.task_id">{{ selectedReportTask?.task_id }}</span>
                  </div>
                  <AppButton
                    variant="icon"
                    class="unified-popup-close-btn hist-report-close-btn"
                    title="Close report"
                    aria-label="Close report"
                    @click="closeTaskReport"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </AppButton>
                </div>
                <div class="unified-popup-body hist-report-popup-body">
                  <div v-if="reportLoading" class="hist-report-loading">
                    <span class="hist-spinner" aria-hidden="true"></span>
                    <span>Memuat ringkasan laporan agent...</span>
                  </div>
                  <div v-else-if="!reportContent" class="wb-empty">Tidak ada laporan yang tersedia untuk task ini.</div>
                  <!-- eslint-disable-next-line vue/no-v-html -->
                  <div v-else class="md hist-report-md" v-html="renderMarkdown(reportContent)"></div>
                </div>
              </div>
            </div>
          </section>

          <!-- Sub-Tab 6: Extensions -->
          <section v-else-if="currentTab === 'extensions'" class="settings-tab-pane">
            <ExtensionManager
              :key="extensionRefreshKey"
              @error="emit('extension-error', $event)"
            />
          </section>

          <!-- Tab 8: Overview -->
          <section v-else-if="currentTab === 'overview'" class="settings-tab-pane">
            <AboutSettingsPanel section="overview" />
          </section>

          <!-- Tab 9: Architecture -->
          <section v-else-if="currentTab === 'architecture'" class="settings-tab-pane">
            <AboutSettingsPanel section="architecture" />
          </section>

          <!-- Tab 10: License -->
          <section v-else-if="currentTab === 'license'" class="settings-tab-pane">
            <AboutSettingsPanel section="license" />
          </section>

          <div v-else class="panel settings-panel">
            <div class="panel-body">
              <div class="wb-empty">Unknown tab selected.</div>
            </div>
          </div>
        </main>
      </div>
    </div>
  </div>
</template>
