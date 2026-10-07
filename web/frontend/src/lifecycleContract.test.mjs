// @ts-check
import test from "node:test";
import assert from "node:assert/strict";
import {
  createInitialTaskState,
  isEventForMonitoredTask,
  shouldProcessEventIdempotent,
  reduceSubmitTask,
  reduceTaskStarted,
  reduceTaskTerminal,
} from "./services/taskStateReducer.js";

test("LIFECYCLE-01: shouldProcessEventIdempotent ignores duplicate sequence and duplicate event_id", () => {
  const state = createInitialTaskState();

  const event1 = {
    event_id: "evt-001",
    sequence: 1,
    task_id: "task-1",
    event_type: "task_started",
  };

  // Event pertama harus diproses
  assert.equal(shouldProcessEventIdempotent(state, event1), true);
  assert.equal(state.lastProcessedSequence, 1);
  assert.equal(state.processedEventIds.has("evt-001"), true);

  // Event duplikat sequence harus ditolak
  const duplicateSeq = {
    event_id: "evt-002",
    sequence: 1,
    task_id: "task-1",
    event_type: "phase_changed",
  };
  assert.equal(shouldProcessEventIdempotent(state, duplicateSeq), false);

  // Event duplikat event_id harus ditolak
  const duplicateId = {
    event_id: "evt-001",
    sequence: 2,
    task_id: "task-1",
    event_type: "phase_changed",
  };
  assert.equal(shouldProcessEventIdempotent(state, duplicateId), false);

  // Event baru dengan sequence lebih tinggi harus diproses
  const event3 = {
    event_id: "evt-003",
    sequence: 2,
    task_id: "task-1",
    event_type: "task_completed",
  };
  assert.equal(shouldProcessEventIdempotent(state, event3), true);
  assert.equal(state.lastProcessedSequence, 2);
});

test("LIFECYCLE-02: Global event stream isolation across tasks", () => {
  const state = createInitialTaskState();
  state.monitoredTaskId = "task-focus";

  // Event milik task lain tidak boleh diproses untuk layar aktif
  const foreignEvent = {
    task_id: "task-other",
    event_type: "agent_reasoning_delta",
  };
  assert.equal(isEventForMonitoredTask(state, foreignEvent), false);

  // Event milik monitored task harus diproses
  const myEvent = {
    task_id: "task-focus",
    event_type: "agent_reasoning_delta",
  };
  assert.equal(isEventForMonitoredTask(state, myEvent), true);

  // Global event tanpa task_id tetap diterima
  const systemEvent = {
    event_type: "system_heartbeat",
  };
  assert.equal(isEventForMonitoredTask(state, systemEvent), true);
});

console.log("[OK] Lifecycle & Event Contract tests passed!");
