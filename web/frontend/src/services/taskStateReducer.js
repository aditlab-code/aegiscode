// @ts-check
import {
  isViewedTaskRunning,
  shouldAdoptSubmittedTask,
  shouldFollowStartedTask,
} from "../taskView.js";

/**
 * Buat inisialisasi state manajemen task untuk multi-task isolation.
 */
export function createInitialTaskState() {
  return {
    monitoredTaskId: "",
    prompt: "",
    status: "idle", // 'idle' | 'pending' | 'running' | 'validating' | 'cancelling' | 'completed' | 'failed' | 'cancelled'
    activityPhase: "",
    runningTaskId: "",
    runningTasksMap: new Map(), // taskId -> { id, prompt, status, ... }
    deferredTaskIds: new Set(), // Set of taskIds waiting in queue
    activityEvents: [],
    changes: [],
    tokenCount: null,
    taskStartedAt: null,
    taskEndedAt: null,
  };
}

/**
 * Tentukan apakah sebuah event SSE relevan untuk task yang sedang dipantau di layar.
 * Mencegah kontaminasi event antar-task (AEG-04).
 *
 * @param {object} state
 * @param {object} event
 * @returns {boolean}
 */
export function isEventForMonitoredTask(state, event) {
  if (!event) return false;
  const evtTaskId = event.task_id || event.taskId;
  if (!evtTaskId) return true; // Event global sistem
  return evtTaskId === state.monitoredTaskId;
}

/**
 * Reducer saat task baru di-submit (AEG-05).
 * Memisahkan task pending dari running agar task di antrean tidak langsung dianggap running.
 *
 * @param {object} state
 * @param {{ taskId: string, prompt: string, queueState?: string }} payload
 * @returns {{ adopted: boolean, status: string }}
 */
export function reduceSubmitTask(state, { taskId, prompt, queueState }) {
  const isViewingRunning = isViewedTaskRunning(state.monitoredTaskId, state.runningTaskId);
  const queueStateNorm = String(queueState || "").trim().toLowerCase();
  const shouldAdopt = shouldAdoptSubmittedTask({
    queueState: queueStateNorm || (isViewingRunning ? "pending" : "running"),
    isViewingRunning,
  });

  if (queueStateNorm === "pending" || (!queueStateNorm && isViewingRunning)) {
    state.deferredTaskIds.add(taskId);
    if (shouldAdopt) {
      state.monitoredTaskId = taskId;
      state.prompt = prompt;
      state.status = "pending";
      state.activityPhase = "";
      state.activityEvents = [];
      state.changes = [];
      state.tokenCount = null;
      state.taskStartedAt = null;
      state.taskEndedAt = null;
      return { adopted: true, status: "pending" };
    }
    return { adopted: false, status: state.status };
  }

  // Jika langsung dialokasikan slot running (atau parallel)
  if (shouldAdopt) {
    state.monitoredTaskId = taskId;
    state.prompt = prompt;
    state.status = "running";
    state.runningTaskId = taskId;
    state.runningTasksMap.set(taskId, { id: taskId, prompt, status: "running" });
    state.activityPhase = "planning";
    state.activityEvents = [];
    state.changes = [];
    state.tokenCount = null;
    state.taskStartedAt = Date.now();
    state.taskEndedAt = null;
    return { adopted: true, status: "running" };
  }

  return { adopted: false, status: state.status };
}

/**
 * Reducer saat event task_started diterima (AEG-04 & AEG-05).
 * Menyesuaikan status task yang dipantau bila giliran eksekusinya telah tiba.
 *
 * @param {object} state
 * @param {object} event
 * @param {{ viewingHistory?: boolean }} [options]
 * @returns {{ followed: boolean, status: string }}
 */
export function reduceTaskStarted(state, event, options = {}) {
  const startedId = event?.task_id || event?.taskId || state.monitoredTaskId;
  const wasViewingThisPending = state.monitoredTaskId === startedId && state.status === "pending";
  const isViewingRunning = isViewedTaskRunning(state.monitoredTaskId, state.runningTaskId);

  const shouldFollow = shouldFollowStartedTask({
    startedTaskId: startedId,
    viewedTaskId: state.monitoredTaskId,
    isViewingRunning,
    viewingHistory: Boolean(options.viewingHistory),
    deferredTaskIds: state.deferredTaskIds,
  });

  // Perbarui registry task yang aktif dieksekusi di backend
  state.runningTasksMap.set(startedId, { id: startedId, status: "running" });

  if (wasViewingThisPending || shouldFollow) {
    state.monitoredTaskId = startedId;
    state.deferredTaskIds.delete(startedId);
    state.status = "running";
    state.runningTaskId = startedId;
    state.activityPhase = "planning";
    state.taskStartedAt = event?.timestamp ? new Date(event.timestamp).getTime() : Date.now();
    return { followed: true, status: "running" };
  }

  // Task lain yang berjalan di background
  state.deferredTaskIds.delete(startedId);
  return { followed: false, status: state.status };
}

/**
 * Reducer saat pengguna meminta pembatalan task (AEG-11).
 * Mengubah status ke 'cancelling' sementara tanpa langsung mereset ke 'idle'.
 *
 * @param {object} state
 * @param {string} targetId
 * @returns {{ previousStatus: string }}
 */
export function reduceRequestStop(state, targetId) {
  const previousStatus = state.status;
  if (state.monitoredTaskId === targetId || !targetId) {
    state.status = "cancelling";
  }
  return { previousStatus };
}

/**
 * Reducer bila permintaan pembatalan ke backend gagal (AEG-11).
 * Mengembalikan status ke keadaan sebelum pembatalan diminta.
 *
 * @param {object} state
 * @param {string} previousStatus
 */
export function reduceCancelFailed(state, previousStatus) {
  state.status = previousStatus || "running";
}

/**
 * Reducer saat event terminal tiba (task_completed, task_failed, task_cancelled) (AEG-04 & AEG-11).
 *
 * @param {object} state
 * @param {object} event
 * @returns {{ isMonitoredTerminal: boolean, newStatus: string }}
 */
export function reduceTaskTerminal(state, event) {
  const evtTaskId = event?.task_id || event?.taskId || state.monitoredTaskId;
  const eventType = String(event?.event_type || event?.type || "");
  const normalizedStatus = eventType.replace("task_", "");

  // Bersihkan dari map running tasks
  state.runningTasksMap.delete(evtTaskId);

  // Jika task yang selesai adalah running slot backend aktif
  if (state.runningTaskId === evtTaskId) {
    state.runningTaskId = "";
  }

  // Jika task yang selesai adalah task yang sedang dipantau di layar
  if (evtTaskId === state.monitoredTaskId) {
    state.status = normalizedStatus;
    state.taskEndedAt = event?.timestamp ? new Date(event.timestamp).getTime() : Date.now();
    return { isMonitoredTerminal: true, newStatus: normalizedStatus };
  }

  return { isMonitoredTerminal: false, newStatus: state.status };
}
