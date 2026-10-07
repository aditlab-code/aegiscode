// @ts-check
import test from "node:test";
import assert from "node:assert/strict";
import {
  createInitialTaskState,
  isEventForMonitoredTask,
  shouldProcessEventIdempotent,
  resolveSequenceGap,
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
test("LIFECYCLE-01b: shouldProcessEventIdempotent detects sequence gap and resolveSequenceGap resolves it", () => {
  const state = createInitialTaskState();

  const evt1 = { event_id: "evt-1", sequence: 1, task_id: "t1" };
  assert.equal(shouldProcessEventIdempotent(state, evt1), true);
  assert.equal(state.hasSequenceGap, false);
  assert.equal(state.lastProcessedSequence, 1);

  // Jump from sequence 1 directly to sequence 4 -> Gap detected (missing 2, 3)
  const evt4 = { event_id: "evt-4", sequence: 4, task_id: "t1" };
  assert.equal(shouldProcessEventIdempotent(state, evt4), true);
  assert.equal(state.hasSequenceGap, true);
  assert.equal(state.missingSequenceGaps.length, 1);
  assert.deepEqual(state.missingSequenceGaps[0], { from: 2, to: 3 });
  assert.equal(state.lastProcessedSequence, 4);

  // Reconcile missing events
  const missingEvents = [
    { event_id: "evt-3", sequence: 3, task_id: "t1" },
    { event_id: "evt-2", sequence: 2, task_id: "t1" },
  ];
  const applied = [];
  const resolvedCount = resolveSequenceGap(state, missingEvents, (e) => applied.push(e.event_id));

  assert.equal(resolvedCount, 2);
  assert.deepEqual(applied, ["evt-2", "evt-3"]);
  assert.equal(state.hasSequenceGap, false);
  assert.deepEqual(state.missingSequenceGaps, []);
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
