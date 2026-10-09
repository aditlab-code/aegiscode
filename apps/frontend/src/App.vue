<script setup>
/**
 * App.vue - Root Application Coordinator.
 * Coordinates AppNavbar, AppActivityBar, WorkbenchView, AppStatusBar,
 * SettingsOverlay, and modal dialogs.
 * Coordinated workbench panels: AgentActivity, ChangesPanel, FileExplorer.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { AEGIS_VERSION } from "./version.js";
import AppNavbar from "./components/layout/AppNavbar.vue";
import AppActivityBar from "./components/layout/AppActivityBar.vue";
import AppStatusBar from "./components/layout/AppStatusBar.vue";
import WorkbenchView from "./pages/WorkbenchView.vue";
import ProjectLauncher from "./components/workspace/ProjectLauncher.vue";
import ReportViewer from "./components/workspace/ReportViewer.vue";
import ProjectPolicyPanel from "./components/workspace/ProjectPolicyPanel.vue";
import AppCommandPalette from "./components/ui/AppCommandPalette.vue";
import AppModal from "./components/ui/AppModal.vue";
import AppButton from "./components/ui/AppButton.vue";
import ApprovalModal from "./components/ui/ApprovalModal.vue";
import LoginOverlay from "./components/workspace/LoginOverlay.vue";
import { useAuth } from "./services/authService.js";
import {
  listTaskHistory,
  clearTaskHistory,
  deleteTaskHistory,
  getConfig,
  getLLMProviders,
  getOperationalMode,
  listApprovals,
} from "./api.js";
import { createResponsiveState } from "./services/responsiveService.js";
import { createThemeState } from "./services/themeService.js";
import { getDefaultCommands, matchesShortcut } from "./services/commandPaletteService.js";
import { useWorkspaceFiles } from "./services/fileCacheService.js";
import { saveWorkspaceContext, loadWorkspaceContext } from "./services/workspaceContextService.js";
import { useProjectContext } from "./composables/useProjectContext.js";
import { useServerConnection } from "./composables/useServerConnection.js";
import { useTaskLifecycle } from "./composables/useTaskLifecycle.js";

// Layout & Navigation State
const themeState = createThemeState(), responsive = createResponsiveState();
const activeNav = ref("explorer"), settingsOpen = ref(false), settingsTab = ref("providers");
const commandPaletteOpen = ref(false), commandPaletteMode = ref("commands");
const closeConfirmOpen = ref(false), stopConfirmOpen = ref(false), policyProject = ref(null);
const approvalModalOpen = ref(false), pendingApproval = ref(null), operationalMode = ref("ask");
const workbenchRef = ref(null);
const notice = ref(""), error = ref(""), cursorPos = ref({ ln: 1, col: 1 }), activeLanguage = ref("Vue 3");
const workspaceGen = ref(0);
const explorerRefresh = ref(0), queueRefresh = ref(0), config = ref({}), taskHistory = ref([]);
const activeSessionId = ref("");

// Sovereign Local Password Authentication (PR-SEC-2)
const {
  currentUser, authStatus, authLoading, authLoadingMessage, authError, authChecking,
  isAuthenticated, handleLogout, loginWithPassword, setupInitialPassword, initAuth,
} = useAuth();

async function handlePasswordSubmit(password) {
  try {
    await loginWithPassword(password);
    await refreshAllConfig();
  } catch (_) {
    // Error dikelola reaktif di authError
  }
}

async function handlePasswordSetup({ password, confirmPassword }) {
  try {
    await setupInitialPassword(password, confirmPassword);
    await refreshAllConfig();
  } catch (_) {
    // Error dikelola reaktif di authError
  }
}
// Workspace Files Cache
const { workspaceFiles, fetchWorkspaceFiles, invalidateFileCache, setWorkspaceProject } = useWorkspaceFiles();

// Provider & Execution Mode Config
const savedExecutionMode = (typeof localStorage !== "undefined" && localStorage.getItem("aegis_execution_mode")) || "";
const savedProviderInstanceId = (typeof localStorage !== "undefined" && localStorage.getItem("aegis_provider_instance_id")) || "";
const savedModelId = (typeof localStorage !== "undefined" && localStorage.getItem("aegis_model_id")) || "";
const llmProviders = ref([]), selectedProviderInstanceId = ref(savedProviderInstanceId), selectedModelId = ref(savedModelId), selectedMode = ref(savedExecutionMode || "balanced"), selectedExecutionMode = ref("queue");

watch(selectedMode, (val) => {
  if (typeof localStorage !== "undefined" && val) {
    try { localStorage.setItem("aegis_execution_mode", val); } catch (_) {}
  }
});
watch(selectedProviderInstanceId, (val) => {
  if (typeof localStorage !== "undefined" && val) {
    try { localStorage.setItem("aegis_provider_instance_id", val); } catch (_) {}
  }
});
watch(selectedModelId, (val) => {
  if (typeof localStorage !== "undefined" && val) {
    try { localStorage.setItem("aegis_model_id", val); } catch (_) {}
  }
});

// Composable 1: Project Context
const {
  activeProject,
  projects,
  lastProject,
  launcherBusy,
  gitBranchInfo,
  loadProjects,
  loadActiveProject,
  refreshGitBranchInfo,
  handleOpenProject,
  handleCreateProject,
  handleDeleteProject,
  handleCloseProject,
  handleOpenFolder,
} = useProjectContext({
  error,
  workspaceGen,
  activeNav,
  closeConfirmOpen,
  workbenchRef,
  setWorkspaceProject,
  fetchWorkspaceFiles,
  invalidateFileCache,
  resetTaskState: () => resetTaskState(),
  refreshAllConfig: () => refreshAllConfig(),
  refreshTaskHistory: () => refreshTaskHistory(),
  syncActiveRunningTask: () => syncActiveRunningTask(),
  handleViewTask: (id) => handleViewTask(id),
  runningTaskId: computed(() => runningTaskId.value),
});

watch(activeNav, (newNav) => {
  if (activeProject.value?.id && newNav) {
    saveWorkspaceContext(activeProject.value.id, { activeNav: newNav });
  }
});

// Composable 2: Server Connection
const {
  gatewayHttpConnected,
  sseStreamConnected,
  connected,
  lastReceivedEventId,
  connectStream,
  startHealthCheck,
  closeConnection,
} = useServerConnection({
  onEvent: (evt) => handleRootEvent(evt),
});

// Composable 3: Task Lifecycle
// Penyelarasan sesi: submitTask menyertakan meta.session_id = activeSessionId.value melalui useTaskLifecycle
const {
  task,
  isRunning,
  stopInProgress,
  runningTaskId,
  terminalTaskId,
  cancellingTaskIds,
  isSubmittingTask,
  activityEvents,
  activityPhase,
  lifecycleMilestones,
  changes,
  validation,
  liveFsChange,
  tokenCount,
  taskTokensLabel,
  taskTokensTooltip,
  deferredTaskIds,
  taskTelemetry,
  taskStartedAt,
  taskEndedAt,
  durationNow,
  durationTicker,
  taskDurationLabel,
  lifecycleSteps,
  lifecyclePct,
  agentStatus,
  taskTag,
  reportTaskId,
  currentReport,
  activateTaskView,
  handleEvent,
  syncActiveRunningTask,
  submitTask,
  handleComposerSubmit,
  cancelTaskById,
  requestStop,
  handleStopTask,
  resetTaskState,
  handleViewTask,
  handleOpenReport,
} = useTaskLifecycle({
  activeProject,
  workspaceGen,
  taskHistory,
  queueRefresh,
  explorerRefresh,
  error,
  stopConfirmOpen,
  refreshTaskHistory: () => refreshTaskHistory(),
  selectedProviderInstanceId,
  selectedModelId,
  selectedMode,
  selectedExecutionMode,
  activeSessionId,
  lastReceivedEventId,
  settingsOpen,
  llmProviders,
});

function handleRootEvent(evt) {
  if (!evt || !evt.event_type) return;
  if (evt.event_type === "approval_requested") {
    const payload = evt.data || evt.payload || evt;
    pendingApproval.value = payload;
    approvalModalOpen.value = true;
  } else if (evt.event_type === "approval_resolved") {
    const payload = evt.data || evt.payload || evt;
    const resId = payload.request_id || payload.id;
    if (!resId || resId === pendingApproval.value?.request_id) {
      pendingApproval.value = null;
      approvalModalOpen.value = false;
    }
  } else if (evt.event_type === "mode_updated") {
    const payload = evt.data || evt.payload || evt;
    const modeVal = payload.mode || payload;
    if (typeof modeVal === "string" && ["ask", "agents"].includes(modeVal.toLowerCase())) {
      operationalMode.value = modeVal.toLowerCase();
    }
  } else if (evt.event_type === "task_started" || evt.event_type === "task_created") {
    if (workbenchRef.value) {
      workbenchRef.value.assistantVisible = true;
      workbenchRef.value.assistantTab = "agents";
    }
  }
  handleEvent(evt);
}

async function syncOperationalState() {
  try {
    const modeRes = await getOperationalMode();
    if (modeRes?.mode) operationalMode.value = modeRes.mode;
  } catch (_) {}
  try {
    const appRes = await listApprovals();
    if (Array.isArray(appRes?.approvals) && appRes.approvals.length > 0) {
      pendingApproval.value = appRes.approvals[0];
      approvalModalOpen.value = true;
    }
  } catch (_) {}
}

const activeProvider = computed(() => llmProviders.value.find((p) => p.id === selectedProviderInstanceId.value) || null);
const activeProviderLabel = computed(() => activeProvider.value?.name || config.value.provider || "");
const activeModelLabel = computed(() => activeProvider.value?.models?.find((x) => x.id === selectedModelId.value)?.model_name || config.value.model || "");
const gatewayAddress = computed(() => (typeof window !== "undefined" ? window.location.host : ""));

const defaultCommands = computed(() => getDefaultCommands({
  quickOpen: () => { commandPaletteMode.value = "files"; commandPaletteOpen.value = true; },
  showCommands: () => { commandPaletteMode.value = "commands"; commandPaletteOpen.value = true; },
  toggleTerminal: () => workbenchRef.value?.toggleBottomDock(),
  toggleSidebar: () => responsive.toggleSidebar(),
  toggleRightAssistant: () => responsive.toggleRightDrawer(),
  toggleTheme: () => themeState.toggleTheme(),
  toggleWallpaper: () => themeState.toggleWallpaper(),
  openSettings: () => workbenchRef.value?.openSettings?.("providers"),
}));

async function refreshTaskHistory() {
  try { taskHistory.value = (await listTaskHistory(activeProject.value?.id || null))?.tasks || []; } catch (_) { taskHistory.value = []; }
}
async function handleDeleteHistory(t) {
  if (!t?.task_id) return;
  try {
    await deleteTaskHistory(t.task_id, activeProject.value?.id || null);
  } catch (err) {
    console.warn("Delete task history warning:", err);
  } finally {
    if (activeProject.value?.id) {
      const ctx = loadWorkspaceContext(activeProject.value.id);
      if (ctx?.task?.viewedTaskId === t.task_id) {
        saveWorkspaceContext(activeProject.value.id, { task: { viewedTaskId: null } }, true);
        resetTaskState();
      }
    }
    await refreshTaskHistory();
  }
}
async function handleClearHistory() {
  try { await clearTaskHistory(activeProject.value?.id || null); await refreshTaskHistory(); } catch (err) { error.value = `Failed to clear history: ${err.message || err}`; }
}
async function loadConfig() {
  try {
    config.value = (await getConfig()) || {};
    if (config.value.mode && !savedExecutionMode) selectedMode.value = config.value.mode;
    if (config.value.provider_instance_id && !selectedProviderInstanceId.value) selectedProviderInstanceId.value = config.value.provider_instance_id;
    if (config.value.model_id && !selectedModelId.value) selectedModelId.value = config.value.model_id;
  } catch (_) { config.value = {}; }
}
async function refreshLLMProviders() {
  try {
    const d = await getLLMProviders();
    llmProviders.value = d?.providers || [];
  } catch {
    llmProviders.value = [];
  }
  const en = llmProviders.value.filter((p) => p.enabled !== false);
  const cfgPid = config.value.provider_instance_id;
  const cfgMid = config.value.model_id;

  if (!en.some((p) => p.id === selectedProviderInstanceId.value)) {
    const withM = en.filter((p) => (p.models || []).some((m) => m.enabled !== false));
    const chosen = en.find((p) => p.id === cfgPid) || withM[0] || en[0];
    selectedProviderInstanceId.value = chosen?.id || "";
    const ms = chosen ? (chosen.models || []).filter((m) => m.enabled !== false) : [];
    selectedModelId.value = ms.find((m) => m.id === cfgMid)?.id || ms[0]?.id || "";
  } else {
    const inst = en.find((p) => p.id === selectedProviderInstanceId.value);
    const ms = inst ? (inst.models || []).filter((m) => m.enabled !== false) : [];
    if (!ms.some((m) => m.id === selectedModelId.value)) {
      selectedModelId.value = ms.find((m) => m.id === cfgMid)?.id || ms[0]?.id || "";
    }
  }
}
async function refreshAllConfig() { await loadConfig(); await refreshLLMProviders(); }
function toggleSidebarAction(f) { responsive.toggleSidebar(f); }
function toggleAssistantAction(f) { responsive.toggleRightDrawer(f); }

function onKeyDown(e) {
  if (matchesShortcut(e, "Cmd+P") || matchesShortcut(e, "Ctrl+P")) {
    e.preventDefault(); commandPaletteMode.value = "files"; commandPaletteOpen.value = true;
  } else if (matchesShortcut(e, "Cmd+K") || matchesShortcut(e, "Ctrl+K")) {
    e.preventDefault(); commandPaletteMode.value = "commands"; commandPaletteOpen.value = true;
  } else if (matchesShortcut(e, "Cmd+B") || matchesShortcut(e, "Ctrl+B")) {
    e.preventDefault(); toggleSidebarAction();
  } else if (matchesShortcut(e, "Cmd+J") || matchesShortcut(e, "Ctrl+J")) {
    e.preventDefault(); toggleAssistantAction();
  } else if (matchesShortcut(e, "Ctrl+`")) {
    e.preventDefault(); workbenchRef.value?.toggleBottomDock();
  } else if (matchesShortcut(e, "Cmd+,") || matchesShortcut(e, "Ctrl+,")) {
    e.preventDefault(); workbenchRef.value?.openSettings?.("providers");
  } else if (e.key === "Escape") {
    commandPaletteOpen.value = settingsOpen.value = closeConfirmOpen.value = stopConfirmOpen.value = approvalModalOpen.value = false;
    reportTaskId.value = ""; policyProject.value = null;
  }
}

onMounted(async () => {
  responsive.bindResizeListener();
  if (typeof window !== "undefined") window.addEventListener("keydown", onKeyDown);
  connectStream((evt) => handleRootEvent(evt));
  startHealthCheck(5000, (evt) => handleRootEvent(evt));
  await syncOperationalState();
  await loadActiveProject();
  await loadProjects();
  await refreshAllConfig();
  if (activeProject.value) await refreshTaskHistory();
  await syncActiveRunningTask();
  if (activeProject.value?.id && !runningTaskId.value) {
    const ctx = loadWorkspaceContext(activeProject.value.id);
    if (ctx?.task?.viewedTaskId) {
      const exists = (taskHistory.value || []).some(
        (item) => (item.task_id || item.id) === ctx.task.viewedTaskId
      );
      if (exists) {
        await handleViewTask(ctx.task.viewedTaskId);
      } else {
        saveWorkspaceContext(activeProject.value.id, { task: { viewedTaskId: null } }, true);
      }
    }
  }
  initAuth();
});

onBeforeUnmount(() => {
  responsive.unbindResizeListener();
  if (typeof window !== "undefined") window.removeEventListener("keydown", onKeyDown);
  closeConnection();
  durationTicker.stop();
});
</script>

<template>
  <div
    class="ide-root"
    :class="[`tier-${responsive.tier.value}`]"
  >
    <div class="ide-window" :class="[`tier-${responsive.tier.value}`]">
      <AppNavbar
        :project="activeProject"
        :tier="responsive.tier.value"
        :changes-count="changes.length"
        :is-running="isRunning"
        :assistant-visible="responsive.rightDrawerOpen.value && Boolean(activeProject)"
        :sidebar-visible="responsive.sidebarOpen.value && Boolean(activeProject)"
        :bottom-dock-visible="workbenchRef?.bottomDockOpen || false"
        :user="currentUser"
        @logout="handleLogout"
        @open-explorer="activeNav = 'explorer'"
        @open-command-palette="commandPaletteOpen = true; commandPaletteMode = 'commands'"
        @toggle-assistant="toggleAssistantAction()"
        @toggle-sidebar="toggleSidebarAction()"
        @toggle-terminal="workbenchRef?.toggleBottomDock()"
      />

      <div class="ide-main-row">
        <AppActivityBar
          v-model:active-nav="activeNav"
          :sidebar-open="responsive.sidebarOpen.value"
          :is-dark="themeState.isDark.value"
          :changes-count="changes.length"
          @toggle-theme="themeState.toggleTheme()"
          @open-settings="(tab) => { if (tab) settingsTab = tab; workbenchRef?.openSettings?.(tab || 'providers'); }"
          @toggle-sidebar="toggleSidebarAction"
          @open-sidebar="toggleSidebarAction(true)"
        />

        <WorkbenchView
          ref="workbenchRef" :active-project="activeProject" :projects="projects" :selected-project-id="activeProject?.id || ''"
          :config="config" :providers="llmProviders" :provider-instance-id="selectedProviderInstanceId" :model-id="selectedModelId" :mode="selectedMode"
          :task-provider="activeProviderLabel" :task-model="activeModelLabel"
          :task-history="taskHistory" :settings-tab="settingsTab" :active-nav="activeNav" :changes="changes" :validation="validation"
          :explorer-refresh="explorerRefresh" :live-fs-change="liveFsChange" :queue-refresh="queueRefresh" :connected="connected" :agent-status="agentStatus"
          :task="task" :task-tag="taskTag" :task-duration-label="taskDurationLabel" :task-timer-live="isRunning"
          :task-tokens-label="taskTokensLabel" :task-tokens-tooltip="taskTokensTooltip" :show-reasoning="isRunning"
          :lifecycle-steps="lifecycleSteps" :lifecycle-pct="lifecyclePct" :activity-phase="activityPhase" :activity-events="activityEvents"
          :is-running="isRunning" :is-submitting="isSubmittingTask" :running-task-id="runningTaskId" :stop-in-progress="stopInProgress" :error="error" :tier="responsive.tier.value"
          :sidebar-visible="responsive.sidebarOpen.value && Boolean(activeProject)" :assistant-visible="responsive.rightDrawerOpen.value && Boolean(activeProject)"
          :active-overlay="responsive.activeOverlay.value" @close-overlay="responsive.closeOverlays()" @toggle-assistant="toggleAssistantAction" @toggle-sidebar="toggleSidebarAction"
          @select-project="(id) => { const p = projects.find(proj => proj.id === id); if (p) handleOpenProject(p); }"
          @close-project="handleCloseProject" @open-composer="() => workbenchRef?.handleOpenAgentComposer?.()" @request-stop="requestStop" @stop-task="handleStopTask" @open-report="handleOpenReport"
          @view-task="handleViewTask" @cursor-change="(pos) => { cursorPos = pos; }" @submit-task="handleComposerSubmit" @run-consultant-task="handleComposerSubmit"
          @update:provider-instance-id="(id) => { selectedProviderInstanceId = id; }" @update:model-id="(id) => { selectedModelId = id; }" @update:mode="(m) => { selectedMode = m; }"
          @open-settings="(tab) => { if (tab) settingsTab = tab; workbenchRef?.openSettings?.(tab || 'providers'); }"
          @refresh-config="refreshAllConfig" @refresh-history="refreshTaskHistory" @delete-history="handleDeleteHistory" @clear-history="handleClearHistory" @open-history-task="handleViewTask" @open-project-policy="(p) => { policyProject = p; }" @delete-project="handleDeleteProject" @open-project="handleOpenProject"
          @open-folder="handleOpenFolder" @open-path="() => { activeNav = 'explorer'; }" @open-explorer="activeNav = 'explorer'"
          @branch-info-updated="(info) => { gitBranchInfo = info; }"
          @open-session="(id) => { activeSessionId = id || ''; }"
          @open-consultant-session="(id) => { activeSessionId = id || ''; }"
        />
      </div>

      <AppStatusBar
        :cursor="cursorPos" :language="activeLanguage"
        :connected="connected" :gateway-address="gatewayAddress" :aegis-version="AEGIS_VERSION" :git-branch-info="gitBranchInfo"
        @open-git="() => { activeNav = 'git'; toggleSidebarAction(true); }"
      />
    </div>

    <ReportViewer v-if="reportTaskId" :task-id="reportTaskId" :status="task.status" :report="currentReport" @close="reportTaskId = ''" />
    <ProjectPolicyPanel v-if="policyProject" :project="policyProject" @close="policyProject = null" />
    <AppCommandPalette v-model="commandPaletteOpen" v-model:mode="commandPaletteMode" :files="workspaceFiles" :commands="defaultCommands" @close="commandPaletteOpen = false" @select-file="(f) => workbenchRef?.handleOpenFile?.(f)" />
    <AppModal v-if="closeConfirmOpen" :model-value="closeConfirmOpen" title="Close Workspace" max-width="420px" @close="closeConfirmOpen = false">
      <div class="confirm-dialog-content">
        <p>Close workspace "{{ activeProject?.name }}"?</p>
        <div class="confirm-dialog-actions">
          <AppButton variant="ghost" size="sm" @click="closeConfirmOpen = false">Cancel</AppButton>
          <AppButton variant="danger" size="sm" @click="handleCloseProject">Close</AppButton>
        </div>
      </div>
    </AppModal>
    <AppModal v-if="stopConfirmOpen" :model-value="stopConfirmOpen" title="Stop Task" max-width="420px" @close="stopConfirmOpen = false">
      <div class="confirm-dialog-content">
        <p>Stop running task?</p>
        <div class="confirm-dialog-actions">
          <AppButton variant="ghost" size="sm" @click="stopConfirmOpen = false">Cancel</AppButton>
          <AppButton variant="danger" size="sm" :disabled="stopInProgress" @click="requestStop">Stop</AppButton>
        </div>
      </div>
    </AppModal>
    <ApprovalModal
      v-model="approvalModalOpen"
      :approval="pendingApproval"
      @close="approvalModalOpen = false"
      @resolved="() => { pendingApproval = null; approvalModalOpen = false; }"
    />
    <LoginOverlay
      v-if="!isAuthenticated && !authChecking"
      :has-password="authStatus?.has_password ?? authStatus?.has_pin ?? false"
      :has-pin="authStatus?.has_password ?? authStatus?.has_pin ?? false"
      :loading="authLoading"
      :loading-message="authLoadingMessage"
      :error="authError"
      @submit-password="handlePasswordSubmit"
      @setup-password="handlePasswordSetup"
      @submit-pin="handlePasswordSubmit"
      @setup-pin="handlePasswordSetup"
      @clear-error="authError = ''"
    />
  </div>
</template>
<style scoped>
.confirm-dialog-content { padding: 16px; display: flex; flex-direction: column; gap: 16px; }
.confirm-dialog-actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
