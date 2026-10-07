/**
 * useTaskLifecycle.js
 *
 * Mengelola siklus hidup task (idle, running, validating, completed, failed, cancelled),
 * stream SSE event reducer, telemetry token, durasi task, pengiriman (submission),
 * pembatalan terisolasi, serta inspeksi detail task history/report.
 */
import { computed, reactive, ref } from "vue";
import { formatTokens, usageTokens } from "../tokenFormat.js";
import { isViewedTaskRunning, shouldAdoptSubmittedTask, shouldFollowStartedTask } from "../taskView.js";
import { isEventForMonitoredTask } from "../services/taskStateReducer.js";
import {
  createTask,
  cancelTask,
  listTaskQueue,
  getTaskReport,
  getTaskActivity,
} from "../api.js";
import { playStatusSound } from "../audioRegistry.js";
import { createDurationTicker, eventTimeMs, formatDuration } from "../timeUtils.js";
import { statusTagClass, computeTaskTelemetry } from "../services/taskService.js";
import { buildLifecycleStates, activityPhaseIndex, addMilestone, VALIDATING_STEP } from "../lifecycle.js";
import { saveWorkspaceContext } from "../services/workspaceContextService.js";

export const LIFECYCLE_STEP_LABELS = ["Planning", "Inspecting", "Editing", "Running", "Validating", "Completed"];

export function useTaskLifecycle(options = {}) {
  const activeProject = options.activeProject || ref(null);
  const workspaceGen = options.workspaceGen || ref(0);
  const taskHistory = options.taskHistory || ref([]);
  const queueRefresh = options.queueRefresh || ref(0);
  const explorerRefresh = options.explorerRefresh || ref(0);
  const error = options.error || ref("");
  const stopConfirmOpen = options.stopConfirmOpen || ref(false);
  const refreshTaskHistory = options.refreshTaskHistory || (() => {});
  const selectedProviderInstanceId = options.selectedProviderInstanceId || ref("");
  const selectedModelId = options.selectedModelId || ref("");
  const selectedMode = options.selectedMode || ref("balanced");
  const selectedExecutionMode = options.selectedExecutionMode || ref("queue");
  const activeSessionId = options.activeSessionId || ref("");
  const lastReceivedEventId = options.lastReceivedEventId || ref("");
  const settingsOpen = options.settingsOpen || ref(false);
  const llmProviders = options.llmProviders || ref([]);

  const task = reactive({ id: "", prompt: "", status: "idle", phase: "" });
  const isRunning = computed(() => ["running", "validating", "cancelling"].includes(task.status));
  const stopInProgress = ref(false);
  const runningTaskId = ref("");
  const terminalTaskId = ref("");
  const cancellingTaskIds = ref(new Set());
  const isSubmittingTask = ref(false);

  const activityEvents = ref([]);
  const activityPhase = ref("");
  const lifecycleMilestones = ref([]);
  const changes = ref([]);
  const validation = reactive({ state: "pending" });
  const liveFsChange = ref(null);
  let liveFsChangeSeq = 0;

  const tokenCount = ref(null);
  const taskTokensLabel = computed(() => formatTokens(tokenCount.value));
  const taskTokensTooltip = computed(() =>
    tokenCount.value != null
      ? `${tokenCount.value.toLocaleString()} tokens`
      : "Token usage not reported"
  );

  const deferredTaskIds = reactive(new Set());
  const taskTelemetry = reactive({ rounds: 0, toolCalls: 0, observations: 0 });
  const taskStartedAt = ref(null);
  const taskEndedAt = ref(null);
  const durationNow = ref(Date.now());

  const durationTicker = createDurationTicker(() => {
    durationNow.value = Date.now();
  });
  const taskDurationLabel = computed(() => {
    if (!taskStartedAt.value) return "";
    return formatDuration((taskEndedAt.value || durationNow.value) - taskStartedAt.value);
  });

  const lifecycleSteps = computed(() => {
    const states = buildLifecycleStates({
      hasTask: Boolean(task.id),
      status: task.status,
      currentPhase: activityPhase.value,
      milestones: lifecycleMilestones.value,
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

  const agentStatus = computed(() => ({
    label: task.status || "idle",
    cls: statusTagClass(task.status || "idle"),
  }));
  const taskTag = computed(() => ({
    label: task.status || "idle",
    cls: statusTagClass(task.status),
  }));

  const reportTaskId = ref("");
  const currentReport = ref("");

function activateTaskView(info) {
  task.id = info.id || "";
  task.prompt = info.prompt || "";
  task.status = info.status || "idle";
  task.phase = "";
  runningTaskId.value = info.runningTaskId || (info.status === "running" ? info.id : "");
  activityPhase.value = info.status === "running" ? "planning" : "";
  lifecycleMilestones.value = info.status === "running" ? [0] : [];
  activityEvents.value = info.events ? [...info.events] : [];
  changes.value = [];
  tokenCount.value = info.tokenCount !== undefined ? info.tokenCount : null;
  taskTelemetry.rounds = 0;
  taskTelemetry.toolCalls = 0;
  taskTelemetry.observations = 0;
  taskStartedAt.value = info.taskStartedAt || null;
  taskEndedAt.value = info.taskEndedAt || null;
  validation.state = "pending";
  if (info.status !== "running") {
    durationTicker.stop();
  }
}

function handleEvent(evt) {
  if (!evt || !evt.event_type) return;
  if (evt.event_id) {
    lastReceivedEventId.value = String(evt.event_id);
  } else if (evt.lastEventId) {
    lastReceivedEventId.value = String(evt.lastEventId);
  }
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
        const existingTaskInQueue = (taskHistory.value || []).find((t) => (t.task_id || t.id) === startedId);
        const startedPrompt = p.prompt || p.task || existingTaskInQueue?.prompt || existingTaskInQueue?.task || "";
        activateTaskView({
          id: startedId,
          prompt: startedPrompt || (wasViewingThisPending ? task.prompt : ""),
          status: "running",
          runningTaskId: startedId,
          taskStartedAt: eventTimeMs(evt),
        });
        activityEvents.value.push(evt);
        durationTicker.start();
        playStatusSound("running");
      }
      deferredTaskIds.delete(startedId);
      queueRefresh.value += 1;
      refreshTaskHistory();
      break;
    }
    case "phase_changed": {
      if (!isForMonitored) break;
      const idx = activityPhaseIndex(p.phase);
      if (idx >= 0) {
        activityPhase.value = String(p.phase).trim().toLowerCase();
        lifecycleMilestones.value = addMilestone(lifecycleMilestones.value, idx);
      }
      queueRefresh.value += 1;
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

  const isForMonitoredNow = isEventForMonitoredTask({ monitoredTaskId: task.id }, evt);
  if (isForMonitoredNow && evt.event_type !== "task_started") {
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

  async function syncActiveRunningTask() {
    try {
      const res = await listTaskQueue(activeProject.value?.id || null);
      const active = (res?.tasks || []).find((t) => ["running", "validating", "cancelling"].includes(t.status));
      if (active && (!task.id || task.status === "idle")) {
        task.id = active.task_id || active.id;
        task.prompt = active.prompt || active.task || "";
        task.status = active.status;
        runningTaskId.value = task.id;
        if (!taskStartedAt.value) taskStartedAt.value = Date.now();
        durationTicker.start();
      }
    } catch (_) {}
  }

async function submitTask(text, providerId = null, modelId = null, execMode = null, images = null) {
  if (!text || !text.trim()) return;
  error.value = "";
  const targetProjectId = activeProject.value?.id || null;
  const startGen = workspaceGen.value;
  isSubmittingTask.value = true;
  try {
    let pId = providerId || selectedProviderInstanceId.value || null;
    let mId = modelId || selectedModelId.value || null;

    // Fallback otomatis jika pId atau mId belum terpilih namun llmProviders tersedia
    const providersList = (typeof llmProviders !== "undefined" && llmProviders?.value) ? llmProviders.value : [];
    if ((!pId || !mId) && Array.isArray(providersList) && providersList.length) {
      const enabledProv = providersList.filter((p) => p.enabled !== false);
      const defaultInst = enabledProv.find((p) => (p.models || []).some((m) => m.enabled !== false)) || enabledProv[0];
      if (defaultInst) {
        if (!pId) pId = defaultInst.id;
        if (!mId) {
          const activeModels = (defaultInst.models || []).filter((m) => m.enabled !== false);
          if (activeModels.length) mId = activeModels[0].id;
        }
      }
    }

    const eMode = execMode || selectedExecutionMode.value || "queue";
    const meta = {};
    if (pId) meta.provider_instance_id = pId;
    if (mId) meta.model_id = mId;
    if (selectedMode.value) meta.mode = selectedMode.value;
    try {
      if (typeof activeSessionId !== "undefined" && activeSessionId?.value) {
        meta.session_id = activeSessionId.value;
      }
    } catch (_) {}
    const res = await createTask(text.trim(), activeProject.value?.id || null, Object.keys(meta).length ? meta : null, eMode, images);
    try {
      if (typeof activeSessionId !== "undefined" && res?.session_id && !activeSessionId.value) {
        activeSessionId.value = res.session_id;
      }
    } catch (_) {}

    if (workspaceGen.value !== startGen || (activeProject.value?.id || null) !== targetProjectId) {
      queueRefresh.value += 1;
      return;
    }

    if (res && res.task_id) {
      const actualStatus = String(res.status || "").toLowerCase();
      const qState = String(res.queue_state || (isRunning.value ? "pending" : "running")).toLowerCase();
      const isTerminal = ["completed", "failed", "cancelled"].includes(actualStatus);
      const isViewingRunning = isViewedTaskRunning(task.id, runningTaskId.value);
      const shouldAdopt = shouldAdoptSubmittedTask({
        queueState: isTerminal ? actualStatus : qState,
        isViewingRunning,
      });

      if (isTerminal) {
        if (shouldAdopt) {
          activateTaskView({
            id: res.task_id,
            prompt: text.trim(),
            status: actualStatus,
            taskEndedAt: Date.now(),
          });
          terminalTaskId.value = res.task_id;
          playStatusSound(actualStatus);
        } else {
          deferredTaskIds.add(res.task_id);
        }
      } else if (qState === "pending") {
        deferredTaskIds.add(res.task_id);
        if (shouldAdopt) {
          activateTaskView({
            id: res.task_id,
            prompt: text.trim(),
            status: "pending",
          });
        }
      } else {
        if (shouldAdopt) {
          activateTaskView({
            id: res.task_id,
            prompt: text.trim(),
            status: "running",
            runningTaskId: res.task_id,
            taskStartedAt: Date.now(),
          });
          durationTicker.start();
          playStatusSound("running");
        } else {
          deferredTaskIds.add(res.task_id);
        }
      }
      queueRefresh.value += 1;
      refreshTaskHistory();
    }
  } catch (err) {
    error.value = `Failed to create task: ${err.message || err}`;
  } finally {
    isSubmittingTask.value = false;
  }
}

async function handleComposerSubmit(payload) {
  const text = typeof payload === "string" ? payload : payload?.text;
  await submitTask(
    text,
    payload?.providerInstanceId || null,
    payload?.modelId || null,
    payload?.executionMode || null,
    payload?.images || null
  );
}

async function cancelTaskById(targetId) {
  if (!targetId || typeof targetId !== "string") return;
  if (cancellingTaskIds.value.has(targetId)) return;

  cancellingTaskIds.value.add(targetId);
  stopInProgress.value = true;

  const isTargetMonitored = task.id === targetId;
  const previousStatus = isTargetMonitored ? task.status : "";
  if (isTargetMonitored) {
    task.status = "cancelling";
  }

  try {
    const res = await cancelTask(targetId);
    const backendStatus = res?.status || "cancelled";

    // HANYA perbarui task yang sedang dipantau jika targetId masih cocok
    if (task.id === targetId) {
      task.status = backendStatus;
      if (["cancelled", "completed", "failed"].includes(backendStatus)) {
        durationTicker.stop();
      }
    }

    // Bersihkan runningTaskId hanya jika task yang dibatalkan adalah yang tercatat running
    if (runningTaskId.value === targetId) {
      runningTaskId.value = "";
    }
  } catch (err) {
    console.warn("Cancel task notice:", err);
    const errMsg = String(err?.message || err);
    if (errMsg.includes("tidak ditemukan")) {
      if (task.id === targetId) {
        task.status = "cancelled";
        durationTicker.stop();
      }
      if (runningTaskId.value === targetId) {
        runningTaskId.value = "";
      }
    } else {
      error.value = `Failed to cancel task: ${errMsg}`;
      // Pulihkan status hanya bila task yang dipantau masih sama
      if (task.id === targetId && previousStatus) {
        task.status = previousStatus;
      }
    }
  } finally {
    cancellingTaskIds.value.delete(targetId);
    stopInProgress.value = cancellingTaskIds.value.size > 0;
    stopConfirmOpen.value = false;
    queueRefresh.value += 1;
    refreshTaskHistory();
  }
}

async function requestStop(explicitId = null) {
  const targetId = (typeof explicitId === "string" && explicitId) ? explicitId : (runningTaskId.value || task.id);
  await cancelTaskById(targetId);
}

  function handleStopTask(taskId) {
    if (taskId && typeof taskId === "string") {
      cancelTaskById(taskId);
    }
  }

  function resetTaskState() {
    activateTaskView({ id: "", prompt: "", status: "idle" });
    terminalTaskId.value = "";
  }

let viewTaskSeq = 0;
async function handleViewTask(t) {
  if (!t) return;
  const taskId = typeof t === "string" ? t : (t.task_id || t.id);
  if (!taskId) return;
  const currentSeq = ++viewTaskSeq;
  const currentProjectId = activeProject.value?.id || null;
  if (activeProject.value?.id) {
    saveWorkspaceContext(activeProject.value.id, {
      task: { viewedTaskId: taskId }
    });
  }
  let targetObj = typeof t === "object" ? t : null;
  if (!targetObj && Array.isArray(taskHistory.value)) {
    targetObj = taskHistory.value.find((item) => (item.task_id || item.id) === taskId) || null;
  }
  const prompt = targetObj ? (targetObj.prompt || targetObj.task || "") : "";
  const isActuallyRunning = runningTaskId.value === taskId || (targetObj && ["running", "validating", "cancelling"].includes(targetObj.status));
  const status = targetObj?.status || (isActuallyRunning ? "running" : "completed");
  task.id = taskId;
  task.prompt = prompt;
  task.status = status;
  runningTaskId.value = isActuallyRunning ? taskId : "";
  try {
    const res = await getTaskActivity(taskId, currentProjectId);
    if (currentSeq !== viewTaskSeq || task.id !== taskId || (activeProject.value?.id || null) !== currentProjectId) return;
    const allEvents = res.events || [];
    activityEvents.value = allEvents.slice(-500);
    const tel = computeTaskTelemetry(allEvents);
    taskTelemetry.rounds = tel.rounds;
    taskTelemetry.toolCalls = tel.toolCalls;
    taskTelemetry.observations = tel.observations;
    const lastEvent = allEvents[allEvents.length - 1];
    if (isActuallyRunning && lastEvent && ["task_started", "tool_called", "observation_received"].includes(lastEvent.event_type)) {
      if (!allEvents.some((e) => ["task_completed", "task_failed", "task_cancelled"].includes(e.event_type))) {
        task.status = "running";
        runningTaskId.value = taskId;
      }
    } else if (!isActuallyRunning) {
      if (!allEvents.some((e) => ["task_completed", "task_failed", "task_cancelled"].includes(e.event_type))) {
        task.status = targetObj?.status === "incomplete" ? "incomplete" : (targetObj?.status || "failed");
        runningTaskId.value = "";
      }
    }
  } catch (_) {
    if (currentSeq !== viewTaskSeq || task.id !== taskId || (activeProject.value?.id || null) !== currentProjectId) return;
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

  return {
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
  };
}
