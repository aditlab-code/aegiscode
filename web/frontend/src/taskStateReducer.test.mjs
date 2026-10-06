// @ts-check
import test from "node:test";
import assert from "node:assert/strict";
import {
  createInitialTaskState,
  isEventForMonitoredTask,
  reduceSubmitTask,
  reduceTaskStarted,
  reduceRequestStop,
  reduceCancelFailed,
  reduceTaskTerminal,
} from "./services/taskStateReducer.js";

test("AEG-04: isEventForMonitoredTask correctly isolates events between tasks", () => {
  const state = createInitialTaskState();
  state.monitoredTaskId = "task-alpha";

  assert.equal(isEventForMonitoredTask(state, { task_id: "task-alpha" }), true);
  assert.equal(isEventForMonitoredTask(state, { task_id: "task-beta" }), false);
  assert.equal(isEventForMonitoredTask(state, { task_id: "" }), true, "Event global tanpa task_id diteruskan");
});

test("AEG-04: Terminal event from background task does not overwrite monitored task state", () => {
  const state = createInitialTaskState();
  state.monitoredTaskId = "task-alpha";
  state.status = "running";
  state.runningTaskId = "task-alpha";
  state.runningTasksMap.set("task-alpha", { id: "task-alpha", status: "running" });
  state.runningTasksMap.set("task-beta", { id: "task-beta", status: "running" });

  // Event task_completed datang dari task-beta di latar belakang
  const res = reduceTaskTerminal(state, {
    event_type: "task_completed",
    task_id: "task-beta",
  });

  assert.equal(res.isMonitoredTerminal, false, "Task yang dipantau bukan task yang selesai");
  assert.equal(state.status, "running", "Status task-alpha harus tetap 'running'");
  assert.equal(state.monitoredTaskId, "task-alpha", "Monitored task id tidak boleh berubah");
  assert.equal(state.runningTasksMap.has("task-beta"), false, "task-beta harus dihapus dari runningTasksMap");
  assert.equal(state.runningTasksMap.has("task-alpha"), true, "task-alpha harus tetap ada di runningTasksMap");
});

test("AEG-05: Submitting task when another is running adds to queue without stealing view or setting running", () => {
  const state = createInitialTaskState();
  state.monitoredTaskId = "task-alpha";
  state.status = "running";
  state.runningTaskId = "task-alpha";

  const res = reduceSubmitTask(state, {
    taskId: "task-beta",
    prompt: "Lakukan audit kode",
    queueState: "pending",
  });

  assert.equal(res.adopted, false, "Task beta pending tidak boleh diadopsi saat task alpha sedang running");
  assert.equal(state.monitoredTaskId, "task-alpha", "UI tetap memantau task alpha");
  assert.equal(state.deferredTaskIds.has("task-beta"), true, "Task beta harus dicatat di deferredTaskIds");
});

test("AEG-05: Submitting pending task when idle adopts it as pending (not running)", () => {
  const state = createInitialTaskState();
  state.monitoredTaskId = "";
  state.status = "idle";
  state.runningTaskId = "";

  const res = reduceSubmitTask(state, {
    taskId: "task-gamma",
    prompt: "Format markdown",
    queueState: "pending",
  });

  assert.equal(res.adopted, true, "Task gamma pending diadopsi saat idle");
  assert.equal(res.status, "pending");
  assert.equal(state.status, "pending", "Status harus 'pending', TIDAK boleh langsung 'running'");
  assert.equal(state.runningTaskId, "", "runningTaskId harus tetap kosong sampai backend mulai eksekusi");
  assert.equal(state.deferredTaskIds.has("task-gamma"), true, "Harus dicatat di deferredTaskIds");

  // Ketika event task_started tiba dari backend untuk task-gamma
  const startRes = reduceTaskStarted(state, {
    event_type: "task_started",
    task_id: "task-gamma",
  });

  assert.equal(startRes.followed, true);
  assert.equal(state.status, "running", "Setelah task_started, status bertransisi menjadi 'running'");
  assert.equal(state.runningTaskId, "task-gamma", "runningTaskId terisi");
  assert.equal(state.deferredTaskIds.has("task-gamma"), false, "Dihapus dari deferredTaskIds");
});

test("AEG-11: Cancellation transitions to 'cancelling' and reverts on failure", () => {
  const state = createInitialTaskState();
  state.monitoredTaskId = "task-delta";
  state.status = "running";
  state.runningTaskId = "task-delta";

  // 1. Pengguna klik stop -> status menjadi cancelling
  const { previousStatus } = reduceRequestStop(state, "task-delta");
  assert.equal(previousStatus, "running");
  assert.equal(state.status, "cancelling");

  // 2. Jika API pembatalan gagal (network error / 500) -> status dikembalikan ke previousStatus
  reduceCancelFailed(state, previousStatus);
  assert.equal(state.status, "running", "Status harus dipulihkan kembali ke 'running' saat cancel gagal");

  // 3. Jika API berhasil dan event task_cancelled tiba dari SSE
  reduceRequestStop(state, "task-delta");
  const termRes = reduceTaskTerminal(state, {
    event_type: "task_cancelled",
    task_id: "task-delta",
  });

  assert.equal(termRes.isMonitoredTerminal, true);
  assert.equal(state.status, "cancelled", "Status bertransisi ke 'cancelled'");
  assert.equal(state.runningTaskId, "", "runningTaskId dikosongkan");
});

console.log("[OK] taskStateReducer: isolasi event antar-task, pending queue adoption, dan pembatalan terverifikasi!");
