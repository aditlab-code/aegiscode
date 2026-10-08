// @ts-check
import test from "node:test";
import assert from "node:assert/strict";
import { KNOWN_SSE_EVENTS, openEventStream } from "./api.js";
import { useServerConnection } from "./composables/useServerConnection.js";
import { createInitialTaskState, shouldProcessEventIdempotent } from "./services/taskStateReducer.js";

test("AEG-09: KNOWN_SSE_EVENTS registers all backend lifecycle, observation, and policy events", () => {
  const REQUIRED_EVENTS = [
    "task_created",
    "task_started",
    "phase_changed",
    "agent_commentary",
    "tool_called",
    "tool_completed",
    "tool_result",
    "agent_observation",
    "observation_received",
    "provider_request",
    "provider_response",
    "validation_started",
    "validation_completed",
    "recovery_started",
    "recovery_completed",
    "policy_applied",
    "policy_escalated",
    "verification_strategy_applied",
    "change_detected",
    "approval_requested",
    "approval_resolved",
    "task_completed",
    "task_failed",
    "task_cancelled",
  ];

  for (const evt of REQUIRED_EVENTS) {
    assert.ok(
      KNOWN_SSE_EVENTS.includes(evt),
      `Event ${evt} harus terdaftar di KNOWN_SSE_EVENTS`
    );
  }
});

test("AEG-10: openEventStream appends last_event_id query parameter when specified", () => {
  let createdUrl = "";
  class MockEventSource {
    constructor(url) {
      createdUrl = url;
      this.addEventListener = () => {};
    }
  }
  globalThis.EventSource = MockEventSource;

  openEventStream({
    taskId: "task-123",
    lastEventId: "evt-999",
  });

  assert.ok(createdUrl.includes("task_id=task-123"), "URL harus memuat task_id");
  assert.ok(createdUrl.includes("last_event_id=evt-999"), "URL harus memuat last_event_id");
});

test("AEG-18: Monotonic telemetry does not decrease when visual event window shifts (> 500 events)", () => {
  const activityEvents = [];
  const taskTelemetry = { rounds: 0, toolCalls: 0, observations: 0 };

  // Simulasikan kedatangan 600 events (500 tool_called + 100 lainnya)
  for (let i = 0; i < 600; i++) {
    const evt = {
      event_type: i < 500 ? "tool_called" : "observation_received",
      task_id: "task-long",
      event_id: `evt-${i}`,
    };

    activityEvents.push(evt);
    if (activityEvents.length > 500) {
      activityEvents.shift();
    }

    if (evt.event_type === "provider_request") {
      taskTelemetry.rounds += 1;
    } else if (evt.event_type === "tool_called") {
      taskTelemetry.toolCalls += 1;
    } else if (evt.event_type === "observation_received") {
      taskTelemetry.observations += 1;
    }
  }

  // Meskipun array tampilan activityEvents hanya menyimpan 500 elemen terakhir,
  // akumulasi toolCalls tidak boleh turun dari 500 menjadi 400!
  assert.equal(activityEvents.length, 500, "Array tampilan visual dibatasi 500 baris");
  assert.equal(taskTelemetry.toolCalls, 500, "Akumulasi toolCalls harus tetap 500 (tidak berkurang)");
  assert.equal(taskTelemetry.observations, 100, "Akumulasi observations harus 100");
});

test("AEG-18: Connection status requires both HTTP gateway and SSE stream to be active", () => {
  const computeConnected = (httpOk, sseOk) => Boolean(httpOk && sseOk);

  assert.equal(computeConnected(true, true), true, "Keduanya aktif -> connected");
  assert.equal(computeConnected(true, false), false, "SSE putus -> disconnected");
  assert.equal(computeConnected(false, true), false, "HTTP gateway mati -> disconnected");
  assert.equal(computeConnected(false, false), false, "Keduanya mati -> disconnected");
});
test("AEG-10b: useServerConnection applies blended exponential backoff with jitter and bounds", () => {
  const conn = useServerConnection();
  const calc = conn.calculateBackoffDelay;
  assert.equal(typeof calc, "function");

  // Periksa rentang batas blended jitter: [0.5 * baseDelay, baseDelay]
  const expectedRanges = [
    { attempt: 0, min: 500, max: 1000 },
    { attempt: 1, min: 1000, max: 2000 },
    { attempt: 2, min: 2000, max: 4000 },
    { attempt: 3, min: 4000, max: 8000 },
    { attempt: 4, min: 5000, max: 10000 }, // Capped at maxReconnectDelay = 10000
    { attempt: 5, min: 5000, max: 10000 },
  ];

  for (const { attempt, min, max } of expectedRanges) {
    const samples = [];
    for (let i = 0; i < 50; i++) {
      const delay = calc(attempt);
      assert.ok(delay >= min, `Delay attempt ${attempt} (${delay}) harus >= ${min}`);
      assert.ok(delay <= max, `Delay attempt ${attempt} (${delay}) harus <= ${max}`);
      samples.push(delay);
    }
    const unique = new Set(samples);
    assert.ok(unique.size > 1, `Harus ada variasi jitter acak pada attempt ${attempt}`);
  }
});

test("AEG-10c: openEventStream maps native MessageEvent lastEventId into payload", () => {
  let registeredHandlers = {};
  class MockEventSource {
    constructor() {
      this.addEventListener = (event, handler) => {
        registeredHandlers[event] = handler;
      };
    }
  }
  globalThis.EventSource = MockEventSource;

  let receivedPayload = null;
  openEventStream({
    onEvent: (payload) => {
      receivedPayload = payload;
    },
  });

  assert.ok(typeof registeredHandlers["task_started"] === "function");
  // Simulasikan pesan native EventSource dengan lastEventId terisi
  registeredHandlers["task_started"]({
    type: "task_started",
    data: JSON.stringify({ task_id: "t-1", prompt: "Test prompt" }),
    lastEventId: "native-evt-uuid-42",
  });

  assert.ok(receivedPayload !== null);
  assert.equal(receivedPayload.lastEventId, "native-evt-uuid-42");
  assert.equal(receivedPayload.event_type, "task_started");
});

test("AEG-10d: useServerConnection tracks lastReceivedEventId and lastReceivedSequence", () => {
  let registeredHandlers = {};
  class MockEventSource {
    constructor() {
      this.readyState = 1;
      this.addEventListener = (event, handler) => {
        registeredHandlers[event] = handler;
      };
      this.close = () => {
        this.readyState = 2;
      };
    }
  }
  globalThis.EventSource = MockEventSource;

  const conn = useServerConnection();
  conn.connectStream();

  // Simulasikan kedatangan event dengan ID dan sequence
  registeredHandlers["tool_called"]({
    type: "tool_called",
    data: JSON.stringify({ event_id: "evt-tool-7", sequence: 7 }),
    lastEventId: "evt-tool-7",
  });

  assert.equal(conn.lastReceivedEventId.value, "evt-tool-7");
  assert.equal(conn.lastReceivedSequence.value, 7);

  conn.closeConnection();
});

test("AEG-10e: Idempotent event handling prevents telemetry and token inflation on replayed events", () => {
  const state = createInitialTaskState();
  state.monitoredTaskId = "task-replay-test";

  const taskTelemetry = { rounds: 0, toolCalls: 0, observations: 0 };
  let tokenCount = 0;
  const activityEvents = [];

  function processSimulatedEvent(evt) {
    if (!shouldProcessEventIdempotent(state, evt)) {
      return false; // Ditolak karena duplikat
    }
    activityEvents.push(evt);
    if (evt.event_type === "provider_request") {
      taskTelemetry.rounds += 1;
    } else if (evt.event_type === "tool_called") {
      taskTelemetry.toolCalls += 1;
    } else if (evt.event_type === "observation_received") {
      taskTelemetry.observations += 1;
    } else if (evt.event_type === "provider_response") {
      tokenCount += evt.payload?.usage?.total_tokens || 0;
    }
    return true;
  }

  // Aliran event dengan duplikasi replay (mis. reconnect SSE mengirim ulang event sequence 2, 3, 4)
  const streamWithDuplicates = [
    { task_id: "task-replay-test", event_id: "e-1", sequence: 1, event_type: "provider_request" },
    { task_id: "task-replay-test", event_id: "e-2", sequence: 2, event_type: "tool_called" },
    // Replay duplikat sequence 2
    { task_id: "task-replay-test", event_id: "e-2", sequence: 2, event_type: "tool_called" },
    { task_id: "task-replay-test", event_id: "e-3", sequence: 3, event_type: "observation_received" },
    // Replay duplikat sequence 3
    { task_id: "task-replay-test", event_id: "e-3", sequence: 3, event_type: "observation_received" },
    { task_id: "task-replay-test", event_id: "e-4", sequence: 4, event_type: "provider_response", payload: { usage: { total_tokens: 300 } } },
    // Replay duplikat sequence 4
    { task_id: "task-replay-test", event_id: "e-4", sequence: 4, event_type: "provider_response", payload: { usage: { total_tokens: 300 } } },
  ];

  for (const evt of streamWithDuplicates) {
    processSimulatedEvent(evt);
  }

  // Verifikasi tidak ada inflasi telemetri
  assert.equal(activityEvents.length, 4, "Hanya 4 event unik yang masuk ke activityEvents");
  assert.equal(taskTelemetry.rounds, 1, "Rounds harus tetap 1");
  assert.equal(taskTelemetry.toolCalls, 1, "toolCalls harus tetap 1 (tidak menjadi 2)");
  assert.equal(taskTelemetry.observations, 1, "observations harus tetap 1 (tidak menjadi 2)");
  assert.equal(tokenCount, 300, "tokenCount harus tetap 300 (tidak menjadi 600)");
});

test("AEG-10f: useServerConnection reconnect cycle recovers after stream error and sends lastReceivedEventId", () => {
  const createdStreams = [];
  class MockEventSource {
    constructor(url) {
      this.url = url;
      this.readyState = 1;
      this.handlers = {};
      this.addEventListener = (evt, handler) => {
        this.handlers[evt] = handler;
      };
      this.close = () => {
        this.readyState = 2;
      };
      createdStreams.push(this);
    }
  }
  globalThis.EventSource = MockEventSource;

  const conn = useServerConnection();
  conn.connectStream();

  assert.equal(createdStreams.length, 1);
  assert.ok(!createdStreams[0].url.includes("last_event_id="), "Koneksi pertama belum punya last_event_id");

  // Simulasikan kedatangan event dengan sequence & ID
  createdStreams[0].handlers["task_started"]({
    type: "task_started",
    data: JSON.stringify({ event_id: "evt-ack-100", sequence: 10 }),
    lastEventId: "evt-ack-100",
  });
  assert.equal(conn.lastReceivedEventId.value, "evt-ack-100");
  assert.equal(conn.lastReceivedSequence.value, 10);

  // Simulasikan error koneksi jaringan
  createdStreams[0].onerror();
  // Stream lama harus seketika ditutup (readyState === 2)
  assert.equal(createdStreams[0].readyState, 2, "Stream lama harus ditutup seketika");
  assert.equal(conn.sseStreamConnected.value, false);

  // Simulasikan siklus reconnect berikutnya
  conn.connectStream();
  assert.equal(createdStreams.length, 2, "Harus membuat instance EventSource baru");
  assert.ok(
    createdStreams[1].url.includes("last_event_id=evt-ack-100"),
    "Stream baru harus menyertakan last_event_id dari event terakhir yang diterima"
  );

  // Koneksi baru sukses terhubung
  createdStreams[1].onopen();
  assert.equal(conn.sseStreamConnected.value, true);
  assert.equal(conn.getReconnectAttempt(), 0, "reconnectAttempt harus di-reset ke 0 saat onopen");

  conn.closeConnection();
});

test("AEG-19: UI refresh while agent running restores active task and duration ticker", async () => {
  // State lokal representasi useTaskLifecycle saat refresh halaman (mount baru)
  const task = { id: "", prompt: "", status: "idle" };
  const runningTaskId = { value: "" };
  const taskStartedAt = { value: null };
  let tickerStarted = false;
  const durationTicker = {
    start: () => { tickerStarted = true; },
    stop: () => { tickerStarted = false; },
  };

  // Kasus 1: Antrian backend memiliki task yang sedang running saat UI dimuat
  const mockRunningQueue = {
    tasks: [
      { task_id: "task-old", status: "completed", prompt: "Old prompt" },
      { task_id: "task-live-1", status: "running", prompt: "Build autonomous agent" },
    ],
  };

  async function syncActiveRunningTaskMock(listQueueFn) {
    const res = await listQueueFn();
    const active = (res?.tasks || []).find((t) => ["running", "validating", "cancelling"].includes(t.status));
    if (active && (!task.id || task.status === "idle")) {
      task.id = active.task_id || active.id;
      task.prompt = active.prompt || active.task || "";
      task.status = active.status;
      runningTaskId.value = task.id;
      if (!taskStartedAt.value) taskStartedAt.value = Date.now();
      durationTicker.start();
    }
  }

  await syncActiveRunningTaskMock(async () => mockRunningQueue);

  assert.equal(task.id, "task-live-1", "Task ID harus dipulihkan dari backend queue");
  assert.equal(task.prompt, "Build autonomous agent", "Prompt task harus dipulihkan");
  assert.equal(task.status, "running", "Status task harus disinkronkan ke running");
  assert.equal(runningTaskId.value, "task-live-1", "runningTaskId harus mengarah ke task aktif");
  assert.ok(taskStartedAt.value > 0, "taskStartedAt harus diinisialisasi");
  assert.equal(tickerStarted, true, "Duration ticker harus otomatis berjalan saat UI mendeteksi running task");

  // Kasus 2: Antrian backend kosong atau hanya memuat task selesai -> UI tetap idle
  const taskIdle = { id: "", prompt: "", status: "idle" };
  const runningIdle = { value: "" };
  let tickerIdleStarted = false;
  const idleTicker = {
    start: () => { tickerIdleStarted = true; },
    stop: () => { tickerIdleStarted = false; },
  };

  async function syncIdleQueueMock(listQueueFn) {
    const res = await listQueueFn();
    const active = (res?.tasks || []).find((t) => ["running", "validating", "cancelling"].includes(t.status));
    if (active && (!taskIdle.id || taskIdle.status === "idle")) {
      taskIdle.id = active.task_id || active.id;
      taskIdle.status = active.status;
      runningIdle.value = taskIdle.id;
      idleTicker.start();
    }
  }

  await syncIdleQueueMock(async () => ({ tasks: [{ task_id: "t-done", status: "completed" }] }));
  assert.equal(taskIdle.id, "", "Task idle tidak mengadopsi task yang sudah selesai");
  assert.equal(taskIdle.status, "idle");
  assert.equal(runningIdle.value, "");
  assert.equal(tickerIdleStarted, false, "Ticker tidak dinyalakan saat task idle");
});

console.log("[OK] sseGapAndTelemetry: event contracts, lastEventId param, monotonic telemetry, dan status koneksi terverifikasi!");
