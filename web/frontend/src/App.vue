<script setup>
/**
 * App.vue - Root Application Coordinator.
 * Coordinates AppNavbar, AppActivityBar, WorkbenchView, AppFooter,
 * SettingsOverlay, and modal dialogs.
 * Coordinated workbench panels: AgentActivity, ChangesPanel, FileExplorer.
 */
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { AEGIS_VERSION, AETHER_VERSION } from "./version.js";
import AppNavbar from "./components/layout/AppNavbar.vue";
import AppActivityBar from "./components/layout/AppActivityBar.vue";
import AppFooter from "./components/layout/AppFooter.vue";
import WorkbenchView from "./pages/WorkbenchView.vue";
import ProjectLauncher from "./components/ProjectLauncher.vue";
import TaskComposer from "./components/TaskComposer.vue";
import ReportViewer from "./components/ReportViewer.vue";
import ProjectPolicyPanel from "./components/ProjectPolicyPanel.vue";
import AppCommandPalette from "./components/ui/AppCommandPalette.vue";
import AppModal from "./components/ui/AppModal.vue";
import LoginOverlay from "./components/LoginOverlay.vue";
import { formatTokens, usageTokens } from "./tokenFormat.js";
import { shouldAdoptSubmittedTask, shouldFollowStartedTask } from "./taskView.js";
import { isEventForMonitoredTask } from "./services/taskStateReducer.js";
import { useAuth } from "./services/authService.js"; import { startServerHealthMonitor } from "./services/serverService.js";
import {
  openEventStream, getProjects, createProject, deleteProject, getActiveProject, setActiveProject, closeActiveProject, pickFolder,
  createTask, cancelTask, listTaskHistory, clearTaskHistory, deleteTaskHistory, getTaskReport, getConfig, getTaskActivity, getLLMProviders,
  getProjectGitBranches, listTaskQueue,
} from "./api.js";
import { playStatusSound } from "./audioRegistry.js";
import { createDurationTicker, eventTimeMs, formatDuration } from "./timeUtils.js";
import { createResponsiveState } from "./services/responsiveService.js";
import { createThemeState } from "./services/themeService.js";
import { getDefaultCommands, matchesShortcut } from "./services/commandPaletteService.js";
import { statusTagClass, computeTaskTelemetry } from "./services/taskService.js";
import { buildLifecycleStates, activityPhaseIndex, addMilestone, VALIDATING_STEP } from "./lifecycle.js";
import { useWorkspaceFiles } from "./services/fileCacheService.js";

// Layout & Navigation State
const themeState = createThemeState(), responsive = createResponsiveState();
const activeNav = ref("explorer"), settingsOpen = ref(false), settingsTab = ref("providers");
const composerOpen = ref(false), commandPaletteOpen = ref(false), commandPaletteMode = ref("commands");
const closeConfirmOpen = ref(false), stopConfirmOpen = ref(false), policyProject = ref(null);
const reportTaskId = ref(""), currentReport = ref(""), workbenchRef = ref(null);
const notice = ref(""), error = ref(""), cursorPos = ref({ ln: 1, col: 1 }), activeLanguage = ref("Vue 3");
const activeProject = ref(null), projects = ref([]), lastProject = ref(null), launcherBusy = ref(false);// Antigravity & Google OAuth State (docs/Oauth-Google.md, Phase 0)
const {
  currentUser, authLoading, authLoadingMessage, authError, authChecking,
  isAuthenticated, handleLogout, initAuth,
} = useAuth();

// Task & Agent State
const gatewayHttpConnected = ref(false), sseStreamConnected = ref(false);
const connected = computed(() => gatewayHttpConnected.value && sseStreamConnected.value);
const task = reactive({ id: "", prompt: "", status: "idle", phase: "" });
const lastReceivedEventId = ref("");
const isRunning = computed(() => ["running", "validating", "cancelling"].includes(task.status));
const stopInProgress = ref(false), runningTaskId = ref(""), terminalTaskId = ref("");
const { workspaceFiles, fetchWorkspaceFiles, invalidateFileCache, setWorkspaceProject } = useWorkspaceFiles();
const activityEvents = ref([]), activityPhase = ref(""), lifecycleMilestones = ref([]), changes = ref([]);
const validation = reactive({ state: "pending" }), liveFsChange = ref(null);
const explorerRefresh = ref(0), queueRefresh = ref(0), config = ref({}), taskHistory = ref([]);
const savedExecutionMode = (typeof localStorage !== "undefined" && localStorage.getItem("aegis_execution_mode")) || "";
const savedProviderInstanceId = (typeof localStorage !== "undefined" && localStorage.getItem("aegis_provider_instance_id")) || "";
const savedModelId = (typeof localStorage !== "undefined" && localStorage.getItem("aegis_model_id")) || "";
const llmProviders = ref([]), selectedProviderInstanceId = ref(savedProviderInstanceId), selectedModelId = ref(savedModelId), selectedMode = ref(savedExecutionMode || "balanced"), selectedExecutionMode = ref("queue");
const tokenCount = ref(null);
const taskTokensLabel = computed(() => formatTokens(tokenCount.value));
const taskTokensTooltip = computed(() =>
  tokenCount.value != null
    ? `${tokenCount.value.toLocaleString()} tokens`
    : "Token usage not reported"
);
const deferredTaskIds = reactive(new Set());
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
const activeProvider = computed(() => llmProviders.value.find((p) => p.id === selectedProviderInstanceId.value) || null);
const activeProviderLabel = computed(() => activeProvider.value?.name || config.value.provider || "");
const activeModelLabel = computed(() => activeProvider.value?.models?.find((x) => x.id === selectedModelId.value)?.model_name || config.value.model || "");
const taskTelemetry = reactive({ rounds: 0, toolCalls: 0, observations: 0 });
const taskStartedAt = ref(null), taskEndedAt = ref(null), durationNow = ref(Date.now());
let eventSource = null, liveFsChangeSeq = 0, stopHealthMonitor = null;
const gatewayAddress = computed(() => (typeof window !== "undefined" ? window.location.host : ""));

const durationTicker = createDurationTicker(() => { durationNow.value = Date.now(); });
const taskDurationLabel = computed(() => {
  if (!taskStartedAt.value) return "";
  return formatDuration((taskEndedAt.value || durationNow.value) - taskStartedAt.value);
});

const LIFECYCLE_STEP_LABELS = ["Planning", "Inspecting", "Editing", "Running", "Validating", "Completed"];
const lifecycleSteps = computed(() => {
  const states = buildLifecycleStates({
    hasTask: Boolean(task.id), status: task.status,
    currentPhase: activityPhase.value, milestones: lifecycleMilestones.value,
  });
  return LIFECYCLE_STEP_LABELS.map((label, idx) => ({ label, state: states[idx] || "" }));
});

const lifecyclePct = computed(() => {
  if (task.status === "completed") return 100;
  if (!task.id) return 0;
  const activeIdx = lifecycleSteps.value.findIndex((s) => s.state === "active");
  const count = lifecycleSteps.value.filter((s) => s.state === "done").length;
  const effective = activeIdx >= 0 ? Math.max(count, activeIdx) : count;
  return Math.min(100, Math.round((effective / (LIFECYCLE_STEP_LABELS.length - 1)) * 100));
});

const agentStatus = computed(() => ({ label: task.status || "idle", cls: statusTagClass(task.status || "idle") }));
const taskTag = computed(() => ({ label: task.status || "idle", cls: statusTagClass(task.status) }));

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

function handleEvent(evt) {
  if (!evt || !evt.event_type) return;
  if (evt.event_id) {
    lastReceivedEventId.value = String(evt.event_id);
  } else if (evt.lastEventId) {
    lastReceivedEventId.value = String(evt.lastEventId);
  }
  const evtTaskId = evt.task_id || "";
  const isForMonitored = isEventForMonitoredTask({ monitoredTaskId: task.id }, evt);
  const p = evt.payload || {};

  if (evt.event_type === "provider_response" && isForMonitored) {
    const u = usageTokens(p);
    if (u != null) {
      tokenCount.value = (tokenCount.value || 0) + u;
    }
  }

  switch (evt.event_type) {
    case "task_started": {
      const startedId = evt.task_id || task.id;
      const wasViewingThisPending = task.id === startedId && task.status === "pending";
      const shouldFollow = shouldFollowStartedTask({
        startedTaskId: startedId,
        viewedTaskId: task.id,
        isViewingRunning: isRunning.value,
        viewingHistory: Boolean(reportTaskId.value),
        deferredTaskIds,
      });

      if (wasViewingThisPending || shouldFollow) {
        task.id = startedId;
        deferredTaskIds.delete(startedId);
        task.status = "running";
        runningTaskId.value = startedId;
        activityPhase.value = "planning";
        lifecycleMilestones.value = addMilestone(lifecycleMilestones.value, 0);
        if (!taskStartedAt.value) taskStartedAt.value = eventTimeMs(evt);
        durationTicker.start();
        playStatusSound("running");
      } else {
        deferredTaskIds.delete(startedId);
      }
      queueRefresh.value += 1;
      break;
    }
    case "phase_changed": {
      if (!isForMonitored) break;
      const idx = activityPhaseIndex(p.phase);
      if (idx >= 0) {
        activityPhase.value = String(p.phase).trim().toLowerCase();
        lifecycleMilestones.value = addMilestone(lifecycleMilestones.value, idx);
      }
      break;
    }
    case "tool_called":
      if (!isForMonitored) break;
      if (p.tool) activityPhase.value = "running";
      break;
    case "tool_completed":
    case "observation_received":
    case "recovery_started":
    case "recovery_completed":
      break;
    case "validation_started":
      if (!isForMonitored) break;
      validation.state = "running";
      task.status = "validating";
      activityPhase.value = "validating";
      lifecycleMilestones.value = addMilestone(lifecycleMilestones.value, VALIDATING_STEP);
      break;
    case "validation_completed":
      if (!isForMonitored) break;
      validation.state = p.success === false ? "err" : "ok";
      break;
    case "change_detected":
      if (p.path && !p.path.includes(".aegis/")) {
        if (isForMonitored) {
          const idx = changes.value.findIndex((c) => c.path === p.path);
          const item = { kind: p.kind || "change", path: p.path, diff: p.diff };
          if (idx >= 0) changes.value[idx] = item;
          else changes.value.push(item);
        }
        liveFsChange.value = { seq: ++liveFsChangeSeq, path: p.path, kind: p.kind || "change" };
      }
      break;
    case "task_completed":
    case "task_failed":
    case "task_cancelled": {
      const termId = evt.task_id || task.id;
      if (runningTaskId.value === termId) {
        runningTaskId.value = "";
      }
      if (isForMonitored) {
        task.status = evt.event_type.replace("task_", "");
        durationTicker.stop();
        taskEndedAt.value = eventTimeMs(evt);
        terminalTaskId.value = termId;
        if (evt.event_type === "task_completed") explorerRefresh.value += 1;
        playStatusSound(task.status);
      }
      queueRefresh.value += 1;
      refreshTaskHistory();
      break;
    }
  }

  if (isForMonitored) {
    activityEvents.value.push(evt);
    if (activityEvents.value.length > 500) activityEvents.value.shift();
    if (evt.event_type === "provider_request") {
      taskTelemetry.rounds += 1;
    } else if (evt.event_type === "tool_called") {
      taskTelemetry.toolCalls += 1;
    } else if (evt.event_type === "observation_received") {
      taskTelemetry.observations += 1;
    }
  }
}

function connectStream() {
  if (eventSource) {
    try { eventSource.close(); } catch (_) {}
    eventSource = null;
  }
  eventSource = openEventStream({
    lastEventId: lastReceivedEventId.value || null,
    onEvent: handleEvent,
    onOpen: () => { sseStreamConnected.value = true; },
    onError: () => { sseStreamConnected.value = false; },
  });
  eventSource.onopen = () => { sseStreamConnected.value = true; };
  eventSource.onerror = () => { sseStreamConnected.value = false; };
}
async function syncActiveRunningTask() {
  try {
    const res = await listTaskQueue(activeProject.value?.id || null);
    const active = (res?.tasks || []).find((t) => ["running", "validating", "cancelling"].includes(t.status));
    if (active && (!task.id || task.status === "idle")) {
      task.id = active.task_id || active.id; task.prompt = active.prompt || active.task || ""; task.status = active.status;
      runningTaskId.value = task.id; if (!taskStartedAt.value) taskStartedAt.value = Date.now(); durationTicker.start();
    }
  } catch (_) {}
}

async function submitTask(text, providerId = null, modelId = null, execMode = null, images = null) {
  if (!text || !text.trim()) return;
  error.value = "";
  try {
    const pId = providerId || selectedProviderInstanceId.value || null;
    const mId = modelId || selectedModelId.value || null;
    const eMode = execMode || selectedExecutionMode.value || "queue";
    const meta = {};
    if (pId) meta.provider_instance_id = pId;
    if (mId) meta.model_id = mId;
    if (selectedMode.value) meta.mode = selectedMode.value;
    const res = await createTask(text.trim(), activeProject.value?.id || null, Object.keys(meta).length ? meta : null, eMode, images);
    if (res && res.task_id) {
      const qState = String(res.queue_state || (isRunning.value ? "pending" : "running")).toLowerCase();
      const shouldAdopt = shouldAdoptSubmittedTask({
        queueState: qState,
        isViewingRunning: isRunning.value,
      });

      if (qState === "pending") {
        deferredTaskIds.add(res.task_id);
        if (shouldAdopt) {
          task.id = res.task_id;
          task.prompt = text.trim();
          task.status = "pending";
          runningTaskId.value = "";
          tokenCount.value = null;
          taskTelemetry.rounds = 0;
          taskTelemetry.toolCalls = 0;
          taskTelemetry.observations = 0;
          activityPhase.value = "";
          lifecycleMilestones.value = [];
          activityEvents.value = [];
          changes.value = [];
          taskStartedAt.value = null;
          taskEndedAt.value = null;
          durationTicker.stop();
        }
      } else {
        if (shouldAdopt) {
          task.id = res.task_id;
          task.prompt = text.trim();
          task.status = "running";
          runningTaskId.value = res.task_id;
          tokenCount.value = null;
          taskTelemetry.rounds = 0;
          taskTelemetry.toolCalls = 0;
          taskTelemetry.observations = 0;
          activityPhase.value = "planning";
          lifecycleMilestones.value = [0];
          activityEvents.value = [];
          changes.value = [];
          taskStartedAt.value = Date.now();
          taskEndedAt.value = null;
          durationTicker.start();
          playStatusSound("running");
        } else {
          deferredTaskIds.add(res.task_id);
        }
      }
      queueRefresh.value += 1;
    }
  } catch (err) {
    error.value = `Failed to create task: ${err.message || err}`;
  }
}

async function handleComposerSubmit(payload) {
  const text = typeof payload === "string" ? payload : payload?.text;
  if (!text) return;
  composerOpen.value = false;
  await submitTask(text, payload?.providerInstanceId || null, payload?.modelId || null, payload?.executionMode || null, payload?.images || null);
}

async function requestStop() {
  const targetId = runningTaskId.value || task.id;
  if (!targetId || stopInProgress.value) return;
  stopInProgress.value = true;
  const previousStatus = task.status;
  task.status = "cancelling";
  try {
    await cancelTask(targetId);
  } catch (err) {
    console.warn("Cancel task notice:", err);
    error.value = `Failed to cancel task: ${err.message || err}`;
    task.status = previousStatus;
  } finally {
    stopInProgress.value = false;
    stopConfirmOpen.value = false;
  }
}

async function loadProjects() {
  launcherBusy.value = true;
  try { projects.value = (await getProjects())?.projects || []; }
  catch (err) { error.value = `Failed to load projects: ${err.message || err}`; }
  finally { launcherBusy.value = false; }
}

async function loadActiveProject() {
  try {
    const r = await getActiveProject();
    const p = r?.active_project || r?.project || null;
    if (p) {
      activeProject.value = lastProject.value = p;
      setWorkspaceProject(p.id);
      fetchWorkspaceFiles(true);
    }
  } catch (_) {}
}

// Git Branch Awareness State & Synchronization
const gitBranchInfo = ref(null);
async function refreshGitBranchInfo() {
  const pId = activeProject.value?.id;
  if (!pId) { gitBranchInfo.value = null; return; }
  try { const data = await getProjectGitBranches(pId); gitBranchInfo.value = data?.branch_info || null; } catch { gitBranchInfo.value = null; }
}
watch(() => activeProject.value?.id, () => { refreshGitBranchInfo(); }, { immediate: true });

async function handleOpenProject(target) {
  if (!target) return;
  const id = typeof target === "string" ? target : target.id;
  if (!id) return;
  launcherBusy.value = true; error.value = "";
  try {
    const res = await setActiveProject(id);
    activeProject.value = res?.active_project || (typeof target === "object" ? target : null) || projects.value.find((p) => p.id === id) || null;
    lastProject.value = activeProject.value;
    setWorkspaceProject(id);
    resetTaskState();
    workbenchRef.value?.clearAllTabs?.();
    invalidateFileCache(id);
    await refreshAllConfig();
    await refreshTaskHistory();
    await syncActiveRunningTask();
    fetchWorkspaceFiles(true);
  } catch (err) { error.value = `Failed to open project: ${err.message || err}`; }
  finally { launcherBusy.value = false; }
}

async function handleCreateProject(name, path) {
  launcherBusy.value = true;
  try { const res = await createProject(name, path); const p = res?.project || res; if (p) { await loadProjects(); await handleOpenProject(p); } }
  catch (err) { error.value = `Failed to create project: ${err.message || err}`; }
  finally { launcherBusy.value = false; }
}

async function handleDeleteProject(id) {
  try { await deleteProject(id); if (activeProject.value?.id === id) await handleCloseProject(); await loadProjects(); }
  catch (err) { error.value = `Failed to delete project: ${err.message || err}`; }
}

async function handleCloseProject() {
  try {
    await closeActiveProject();
    activeProject.value = null;
    closeConfirmOpen.value = false;
    setWorkspaceProject(null);
    resetTaskState();
    await loadProjects();
    workbenchRef.value?.clearAllTabs?.();
    invalidateFileCache();
  } catch (err) { error.value = `Failed to close project: ${err.message || err}`; }
}

async function handleOpenFolder() {
  launcherBusy.value = true; error.value = "";
  try {
    const res = await pickFolder();
    if (!res || !res.ok || !res.path) { if (res && res.reason !== "cancelled" && res.message) error.value = res.message; return; }
    const p = res.path, exist = projects.value.find((x) => x.path === p || x.root === p);
    if (exist) { await handleOpenProject(exist.id); return; }
    const segs = String(p).split(/[\\/]+/).filter(Boolean), n = segs.length ? segs[segs.length - 1] : "workspace";
    const cr = await createProject(n, p); const np = cr?.project || cr; await loadProjects();
    if (np?.id) await handleOpenProject(np.id);
  } catch (err) { error.value = `Failed to open folder: ${err.message || err}`; }
  finally { launcherBusy.value = false; }
}

function resetTaskState() {
  task.id = ""; task.prompt = ""; task.status = "idle"; task.phase = "";
  runningTaskId.value = terminalTaskId.value = activityPhase.value = "";
  lifecycleMilestones.value = []; activityEvents.value = []; changes.value = [];
  validation.state = "pending"; taskStartedAt.value = taskEndedAt.value = null; durationTicker.stop();
  taskTelemetry.rounds = 0; taskTelemetry.toolCalls = 0; taskTelemetry.observations = 0;
}

async function handleViewTask(t) {
  if (!t) return;
  const taskId = typeof t === "string" ? t : (t.task_id || t.id);
  if (!taskId) return;
  const prompt = typeof t === "object" ? (t.prompt || t.task || "") : "";
  const status = typeof t === "object" ? (t.status || "completed") : "completed";
  task.id = taskId;
  task.prompt = prompt;
  task.status = status;
  runningTaskId.value = status === "running" ? taskId : "";
  try {
    const res = await getTaskActivity(taskId, activeProject.value?.id || null);
    const allEvents = res.events || [];
    activityEvents.value = allEvents.slice(-500);
    const tel = computeTaskTelemetry(allEvents);
    taskTelemetry.rounds = tel.rounds;
    taskTelemetry.toolCalls = tel.toolCalls;
    taskTelemetry.observations = tel.observations;
  } catch (_) {
    activityEvents.value = [];
    taskTelemetry.rounds = 0;
    taskTelemetry.toolCalls = 0;
    taskTelemetry.observations = 0;
  }
  if (settingsOpen.value) settingsOpen.value = false;
}

async function handleOpenReport(taskId) {
  reportTaskId.value = taskId;
  try { currentReport.value = (await getTaskReport(taskId, activeProject.value?.id || null))?.report || ""; }
  catch (err) { currentReport.value = `Failed to load report: ${err.message || err}`; }
}
async function refreshTaskHistory() {
  try { taskHistory.value = (await listTaskHistory(activeProject.value?.id || null))?.tasks || []; } catch (_) { taskHistory.value = []; }
}
async function handleDeleteHistory(t) {
  if (!t?.task_id) return;
  try { await deleteTaskHistory(t.task_id, activeProject.value?.id || null); await refreshTaskHistory(); } catch (err) { error.value = `Failed to delete task history: ${err.message || err}`; }
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
  try { const d = await getLLMProviders(); llmProviders.value = d?.providers || []; } catch { llmProviders.value = []; }
  const en = llmProviders.value.filter((p) => p.enabled !== false), cfgPid = config.value.provider_instance_id, cfgMid = config.value.model_id;
  if (!en.some((p) => p.id === selectedProviderInstanceId.value)) {
    const withM = en.filter((p) => (p.models || []).some((m) => m.enabled !== false));
    selectedProviderInstanceId.value = (en.find((p) => p.id === cfgPid) || withM[0] || en[0])?.id || "";
    selectedModelId.value = "";
  }
  const inst = en.find((p) => p.id === selectedProviderInstanceId.value);
  const ms = inst ? (inst.models || []).filter((m) => m.enabled !== false) : [];
  if (!ms.some((m) => m.id === selectedModelId.value)) selectedModelId.value = ms.find((m) => m.id === cfgMid)?.id || ms[0]?.id || "";
}
async function refreshAllConfig() { await loadConfig(); await refreshLLMProviders(); }
function toggleSidebarAction(f) { responsive.toggleSidebar(f); } function toggleAssistantAction(f) { responsive.toggleRightDrawer(f); }

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
    commandPaletteOpen.value = composerOpen.value = settingsOpen.value = closeConfirmOpen.value = stopConfirmOpen.value = false;
    reportTaskId.value = ""; policyProject.value = null;
  }
}

onMounted(async () => {
  responsive.bindResizeListener();
  if (typeof window !== "undefined") window.addEventListener("keydown", onKeyDown);
  connectStream();
  stopHealthMonitor = startServerHealthMonitor((ok) => {
    gatewayHttpConnected.value = Boolean(ok);
    if (ok) {
      if (!eventSource || eventSource.readyState === 2 || !sseStreamConnected.value) {
        connectStream();
      }
    } else {
      sseStreamConnected.value = false;
    }
  }, 5000);
  await loadActiveProject(); await loadProjects(); await refreshAllConfig();
  if (activeProject.value) await refreshTaskHistory();
  await syncActiveRunningTask(); initAuth();
});
onBeforeUnmount(() => {
  responsive.unbindResizeListener();
  if (typeof window !== "undefined") window.removeEventListener("keydown", onKeyDown);
  if (stopHealthMonitor) { stopHealthMonitor(); stopHealthMonitor = null; }
  if (eventSource) { eventSource.close(); eventSource = null; }
  durationTicker.stop();
});
</script>

<template>
  <div class="ide-root" :class="[`tier-${responsive.tier.value}`]">
    <AppNavbar
      :project="activeProject" :tier="responsive.tier.value" :changes-count="changes.length" :is-running="isRunning" :assistant-visible="responsive.rightDrawerOpen.value && Boolean(activeProject)"
      :user="currentUser" @logout="handleLogout" @open-explorer="activeNav = 'explorer'"
      @open-command-palette="commandPaletteOpen = true; commandPaletteMode = 'commands'" @toggle-assistant="toggleAssistantAction()"
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
        :is-running="isRunning" :stop-in-progress="stopInProgress" :error="error" :tier="responsive.tier.value"
        :sidebar-visible="responsive.sidebarOpen.value && Boolean(activeProject)" :assistant-visible="responsive.rightDrawerOpen.value && Boolean(activeProject)"
        :active-overlay="responsive.activeOverlay.value" @close-overlay="responsive.closeOverlays()" @toggle-assistant="toggleAssistantAction" @toggle-sidebar="toggleSidebarAction"
        @select-project="(id) => { const p = projects.find(proj => proj.id === id); if (p) handleOpenProject(p); }"
        @close-project="handleCloseProject" @open-composer="composerOpen = true" @request-stop="requestStop" @stop-task="requestStop" @open-report="handleOpenReport"
        @view-task="handleViewTask" @cursor-change="(pos) => { cursorPos = pos; }" @submit-task="handleComposerSubmit" @run-consultant-task="handleComposerSubmit"
        @update:provider-instance-id="(id) => { selectedProviderInstanceId = id; }" @update:model-id="(id) => { selectedModelId = id; }" @update:mode="(m) => { selectedMode = m; }"
        @open-settings="(tab) => { if (tab) settingsTab = tab; workbenchRef?.openSettings?.(tab || 'providers'); }"
        @refresh-config="refreshAllConfig" @delete-history="handleDeleteHistory" @clear-history="handleClearHistory" @open-history-task="handleViewTask" @open-project-policy="(p) => { policyProject = p; }" @delete-project="handleDeleteProject" @open-project="handleOpenProject"
        @open-folder="handleOpenFolder" @open-path="() => { activeNav = 'explorer'; }" @open-explorer="activeNav = 'explorer'"
        @branch-info-updated="(info) => { gitBranchInfo = info; }"
      />
    </div>

    <AppFooter
      :cursor="cursorPos" :language="activeLanguage" :model-label="activeModelLabel" :provider-label="activeProviderLabel"
      :task-status="task.status" :connected="connected" :gateway-address="gatewayAddress" :agent-status="agentStatus" :aether-version="AETHER_VERSION" :git-branch-info="gitBranchInfo"
      :bottom-dock-open="workbenchRef?.bottomDockOpen || false" :active-dock-tab="workbenchRef?.dockActiveTab || 'terminal'" :tier="responsive.tier.value" :problems-count="workbenchRef?.problems?.length || 0"
      @toggle-dock="(tab) => workbenchRef?.toggleBottomDock(tab)" @open-git="() => { activeNav = 'git'; toggleSidebarAction(true); }"
    />

    <AppModal v-if="composerOpen" :model-value="composerOpen" title="New Agent Task" max-width="640px" @close="composerOpen = false">
      <TaskComposer :running="isRunning" :config="config" :providers="llmProviders" :task-history="taskHistory" v-model:provider-instance-id="selectedProviderInstanceId" v-model:model-id="selectedModelId" v-model:mode="selectedMode" v-model:execution-mode="selectedExecutionMode" @submit="handleComposerSubmit" @stop="requestStop" />
    </AppModal>
    <ReportViewer v-if="reportTaskId" :task-id="reportTaskId" :status="task.status" :report="currentReport" @close="reportTaskId = ''" />
    <ProjectPolicyPanel v-if="policyProject" :project="policyProject" @close="policyProject = null" />
    <AppCommandPalette v-model="commandPaletteOpen" v-model:mode="commandPaletteMode" :files="workspaceFiles" :commands="defaultCommands" @close="commandPaletteOpen = false" @select-file="(f) => workbenchRef?.handleOpenFile?.(f)" />
    <AppModal v-if="closeConfirmOpen" :model-value="closeConfirmOpen" title="Close Workspace" max-width="420px" @close="closeConfirmOpen = false">
      <div class="confirm-dialog-content"><p>Close workspace "{{ activeProject?.name }}"?</p><div class="confirm-dialog-actions"><button type="button" class="btn btn-ghost" @click="closeConfirmOpen = false">Cancel</button><button type="button" class="btn btn-danger" @click="handleCloseProject">Close</button></div></div>
    </AppModal>
    <AppModal v-if="stopConfirmOpen" :model-value="stopConfirmOpen" title="Stop Task" max-width="420px" @close="stopConfirmOpen = false">
      <div class="confirm-dialog-content"><p>Stop running task?</p><div class="confirm-dialog-actions"><button type="button" class="btn btn-ghost" @click="stopConfirmOpen = false">Cancel</button><button type="button" class="btn btn-danger" :disabled="stopInProgress" @click="requestStop">Stop</button></div></div>
    </AppModal>
    <LoginOverlay
      v-if="!isAuthenticated && config?.auth_required"
      :loading="authLoading"
      :loading-message="authLoadingMessage"
      :error="authError"
      @clear-error="authError = ''"
    />
  </div>
</template>
<style scoped>
.confirm-dialog-content { padding: 16px; display: flex; flex-direction: column; gap: 16px; }
.confirm-dialog-actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
