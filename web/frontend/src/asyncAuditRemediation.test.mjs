// @ts-check
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { KNOWN_SSE_EVENTS } from "./api.js";
import { usageTokens } from "./tokenFormat.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const readSrc = (relPath) => fs.readFileSync(path.join(__dirname, relPath), "utf8");
const readTaskLifecycleSrc = () => {
  const p = path.join(__dirname, "composables/useTaskLifecycle.js");
  if (fs.existsSync(p)) return fs.readFileSync(p, "utf8");
  return readSrc("App.vue");
};
const between = (s, a, b) => s.slice(s.indexOf(a), s.indexOf(b, s.indexOf(a)));

// ── T01: ASYNC-01 ─────────────────────────────────────────────────────────────
test("T01_ASYNC01: KNOWN_SSE_EVENTS dan EVENT_DESCRIBERS memuat warning & reasoning delta", () => {
  assert.ok(KNOWN_SSE_EVENTS.includes("warning"), "KNOWN_SSE_EVENTS harus memuat 'warning'");
  assert.ok(KNOWN_SSE_EVENTS.includes("agent_reasoning_delta"), "KNOWN_SSE_EVENTS harus memuat 'agent_reasoning_delta'");

  const actCode = readSrc("components/drawer/AgentActivity.vue");
  const descSource = between(
    actCode,
    "const EVENT_DESCRIBERS = {",
    "\n// Aktivitas non-tool"
  );

  const env = { renderMarkdown: (t) => t };
  const describers = new Function(...Object.keys(env), `${descSource}\nreturn EVENT_DESCRIBERS;`)(...Object.values(env));

  // Verifikasi warning describer
  const warnItem = describers.warning({ message: "Rate limit reached", target: "fetch" }, { at: 1, ts: 100 }, 1);
  assert.ok(warnItem, "Warning item harus dibuat");
  assert.equal(warnItem.title, "Warning");
  assert.equal(warnItem.kind, "notice");
  assert.equal(warnItem.icon, "warn");
  assert.equal(warnItem.detailText, "Rate limit reached");

  // Verifikasi agent_reasoning_delta describer
  const deltaItem = describers.agent_reasoning_delta({ delta: "Analyzing files..." }, { at: 2, ts: 101 }, 2);
  assert.ok(deltaItem, "Reasoning delta item harus dibuat");
  assert.equal(deltaItem.title, "Reasoning");
  assert.equal(deltaItem.kind, "reasoning");
  assert.equal(deltaItem.icon, "brain");
  assert.equal(deltaItem.detailText, "Analyzing files...");
});

// ── T02: ASYNC-02 ─────────────────────────────────────────────────────────────
test("T02_ASYNC02: cancelTaskById membatalkan task spesifik tanpa menghentikan task aktif lain", async () => {
  const appCode = readTaskLifecycleSrc();
  const cancelSrc = between(
    appCode,
    "async function cancelTaskById(targetId) {",
    "\nasync function requestStop("
  );

  const cancelledTargetIds = [];
  const task = { id: "task-running-active", status: "running" };
  const runningTaskId = { value: "task-running-active" };
  const stopInProgress = { value: false };
  const cancellingTaskIds = { value: new Set() };
  const error = { value: "" };
  const durationTicker = { stop: () => {} };
  const queueRefresh = { value: 0 };
  const stopConfirmOpen = { value: true };
  const refreshTaskHistory = () => {};

  const cancelTask = async (id) => {
    cancelledTargetIds.push(id);
    return { status: "cancelled" };
  };

  const cancelTaskById = new Function(
    "task", "runningTaskId", "stopInProgress", "cancellingTaskIds",
    "error", "durationTicker", "queueRefresh", "stopConfirmOpen",
    "refreshTaskHistory", "cancelTask",
    `${cancelSrc}\nreturn cancelTaskById;`
  )(
    task, runningTaskId, stopInProgress, cancellingTaskIds,
    error, durationTicker, queueRefresh, stopConfirmOpen,
    refreshTaskHistory, cancelTask
  );

  // Batalkan task lain di antrian (task-queue-99)
  await cancelTaskById("task-queue-99");

  assert.deepEqual(cancelledTargetIds, ["task-queue-99"]);
  // Monitored task harus TETAP 'running' dan runningTaskId TIDAK dibersihkan
  assert.equal(task.id, "task-running-active");
  assert.equal(task.status, "running");
  assert.equal(runningTaskId.value, "task-running-active");
});

// ── T03: ASYNC-03 ─────────────────────────────────────────────────────────────
test("T03_ASYNC03: cancelTaskById menghormati status backend dan guard task ID yang berubah", async () => {
  const appCode = readTaskLifecycleSrc();
  const cancelSrc = between(
    appCode,
    "async function cancelTaskById(targetId) {",
    "\nasync function requestStop("
  );

  const task = { id: "task-current", status: "cancelling" };
  const runningTaskId = { value: "task-current" };
  const stopInProgress = { value: true };
  const cancellingTaskIds = { value: new Set() };
  const error = { value: "" };
  let tickerStopped = false;
  const durationTicker = { stop: () => { tickerStopped = true; } };
  const queueRefresh = { value: 0 };
  const stopConfirmOpen = { value: false };
  const refreshTaskHistory = () => {};

  // Simulasi: Backend merespons bahwa task sebenarnya sudah selesai ('completed')
  const cancelTask = async (id) => {
    // Sembari menunggu cancel, pengguna berpindah melihat task lain
    task.id = "task-switched-to-other";
    task.status = "running";
    return { status: "completed" };
  };

  const cancelTaskById = new Function(
    "task", "runningTaskId", "stopInProgress", "cancellingTaskIds",
    "error", "durationTicker", "queueRefresh", "stopConfirmOpen",
    "refreshTaskHistory", "cancelTask",
    `${cancelSrc}\nreturn cancelTaskById;`
  )(
    task, runningTaskId, stopInProgress, cancellingTaskIds,
    error, durationTicker, queueRefresh, stopConfirmOpen,
    refreshTaskHistory, cancelTask
  );

  await cancelTaskById("task-current");

  // Karena task.id sekarang adalah task-switched-to-other, statusnya TIDAK boleh ditimpa
  assert.equal(task.id, "task-switched-to-other");
  assert.equal(task.status, "running", "Task baru tidak boleh tertimpa status cancel dari task lama");
});

// ── T04: ASYNC-04 ─────────────────────────────────────────────────────────────
test("T04_ASYNC04: submitTask mengadopsi status terminal jika backend langsung mengembalikan completed", async () => {
  const appCode = readTaskLifecycleSrc();
  const submitSrc = between(
    appCode,
    "async function submitTask(text,",
    "\nasync function handleComposerSubmit("
  );

  const task = { id: "", prompt: "", status: "idle", phase: "" };
  const runningTaskId = { value: "" };
  const terminalTaskId = { value: "" };
  const activityPhase = { value: "" };
  const lifecycleMilestones = { value: [] };
  const activityEvents = { value: [] };
  const changes = { value: [] };
  const tokenCount = { value: null };
  const taskTelemetry = { rounds: 0, toolCalls: 0, observations: 0 };
  const taskStartedAt = { value: null };
  const taskEndedAt = { value: null };
  const validation = { state: "pending" };
  let tickerStarted = false;
  const durationTicker = { start: () => { tickerStarted = true; }, stop: () => {} };
  const error = { value: "" };
  const activeProject = { value: { id: "p1" } };
  const workspaceGen = { value: 0 };
  const isSubmittingTask = { value: false };
  const selectedProviderInstanceId = { value: "" };
  const selectedModelId = { value: "" };
  const selectedExecutionMode = { value: "queue" };
  const selectedMode = { value: "balanced" };
  const isRunning = { value: false };
  const deferredTaskIds = new Set();
  const queueRefresh = { value: 0 };
  const refreshTaskHistory = () => {};
  const playStatusSound = () => {};

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
    if (info.status !== "running") durationTicker.stop();
  }

  const isViewedTaskRunning = () => false;
  const shouldAdoptSubmittedTask = () => true;

  // createTask mengembalikan completed (misalnya eksekusi sinkron / cached)
  const createTask = async () => ({
    task_id: "t-instant-done",
    status: "completed",
    queue_state: "completed",
  });

  const submitFn = new Function(
    "task", "runningTaskId", "error", "activeProject", "workspaceGen", "isSubmittingTask",
    "selectedProviderInstanceId", "selectedModelId", "selectedExecutionMode",
    "selectedMode", "isRunning", "isViewedTaskRunning", "shouldAdoptSubmittedTask",
    "activateTaskView", "terminalTaskId", "playStatusSound", "deferredTaskIds",
    "durationTicker", "queueRefresh", "refreshTaskHistory", "createTask",
    `${submitSrc}\nreturn submitTask;`
  )(
    task, runningTaskId, error, activeProject, workspaceGen, isSubmittingTask,
    selectedProviderInstanceId, selectedModelId, selectedExecutionMode,
    selectedMode, isRunning, isViewedTaskRunning, shouldAdoptSubmittedTask,
    activateTaskView, terminalTaskId, playStatusSound, deferredTaskIds,
    durationTicker, queueRefresh, refreshTaskHistory, createTask
  );

  await submitFn("Test instant completion");

  assert.equal(task.id, "t-instant-done");
  assert.equal(task.status, "completed", "Status task harus 'completed' bukan 'running'");
  assert.equal(runningTaskId.value, "", "runningTaskId harus tetap kosong");
  assert.equal(tickerStarted, false, "Ticker tidak boleh dinyalakan untuk task selesai");
  assert.equal(isSubmittingTask.value, false, "isSubmittingTask harus false");
});

// ── T05: ASYNC-05 ─────────────────────────────────────────────────────────────
test("T05_ASYNC05: activateTaskView membersihkan prompt, tokens, dan state saat beralih task", () => {
  const appCode = readTaskLifecycleSrc();
  const activateSrc = between(
    appCode,
    "function activateTaskView(info) {",
    "\nfunction handleEvent(evt)"
  );

  const task = { id: "old-id", prompt: "Old prompt", status: "running", phase: "editing" };
  const runningTaskId = { value: "old-id" };
  const activityPhase = { value: "editing" };
  const lifecycleMilestones = { value: [0, 1, 2] };
  const activityEvents = { value: [{ event_type: "tool_called" }] };
  const changes = { value: [{ path: "test.js" }] };
  const tokenCount = { value: 5000 };
  const taskTelemetry = { rounds: 10, toolCalls: 5, observations: 5 };
  const taskStartedAt = { value: 123456 };
  const taskEndedAt = { value: null };
  const validation = { state: "ok" };
  let tickerStopped = false;
  const durationTicker = { stop: () => { tickerStopped = true; } };
  const taskReducerState = {
    monitoredTaskId: "",
    lastProcessedSequence: 0,
    processedEventIds: new Set(),
    hasSequenceGap: false,
    missingSequenceGaps: [],
  };

  const activateTaskView = new Function(
    "task", "runningTaskId", "activityPhase", "lifecycleMilestones",
    "activityEvents", "changes", "tokenCount", "taskTelemetry",
    "taskStartedAt", "taskEndedAt", "validation", "durationTicker",
    "taskReducerState",
    `${activateSrc}\nreturn activateTaskView;`
  )(
    task, runningTaskId, activityPhase, lifecycleMilestones,
    activityEvents, changes, tokenCount, taskTelemetry,
    taskStartedAt, taskEndedAt, validation, durationTicker,
    taskReducerState
  );


  // Adopsi task baru yang masih pending
  activateTaskView({
    id: "new-pending-id",
    prompt: "New prompt for B",
    status: "pending",
  });

  assert.equal(task.id, "new-pending-id");
  assert.equal(task.prompt, "New prompt for B");
  assert.equal(task.status, "pending");
  assert.equal(runningTaskId.value, "");
  assert.equal(activityPhase.value, "");
  assert.deepEqual(lifecycleMilestones.value, []);
  assert.deepEqual(activityEvents.value, []);
  assert.deepEqual(changes.value, []);
  assert.equal(tokenCount.value, null);
  assert.equal(taskTelemetry.rounds, 0);
  assert.equal(tickerStopped, true);
});

// ── T06: ASYNC-06 ─────────────────────────────────────────────────────────────
test("T06_ASYNC06: submitTask guard generasi workspace menolak adopsi jika project berpindah saat in-flight", async () => {
  const appCode = readTaskLifecycleSrc();
  const submitSrc = between(
    appCode,
    "async function submitTask(text,",
    "\nasync function handleComposerSubmit("
  );

  const task = { id: "", prompt: "", status: "idle" };
  const activeProject = { value: { id: "p1" } };
  const workspaceGen = { value: 1 };
  const isSubmittingTask = { value: false };
  let queueRefreshed = 0;
  const queueRefresh = { get value() { return queueRefreshed; }, set value(v) { queueRefreshed = v; } };
  let adopted = false;

  const createTask = async () => {
    // Pengguna berpindah ke project P2 sebelum API merespons
    activeProject.value = { id: "p2" };
    workspaceGen.value = 2;
    return { task_id: "task-from-p1", status: "running" };
  };

  const submitFn = new Function(
    "task", "runningTaskId", "error", "activeProject", "workspaceGen", "isSubmittingTask",
    "selectedProviderInstanceId", "selectedModelId", "selectedExecutionMode",
    "selectedMode", "isRunning", "isViewedTaskRunning", "shouldAdoptSubmittedTask",
    "activateTaskView", "terminalTaskId", "playStatusSound", "deferredTaskIds",
    "durationTicker", "queueRefresh", "refreshTaskHistory", "createTask",
    `${submitSrc}\nreturn submitTask;`
  )(
    task, { value: "" }, { value: "" }, activeProject, workspaceGen, isSubmittingTask,
    { value: "" }, { value: "" }, { value: "queue" },
    { value: "balanced" }, { value: false }, () => false, () => true,
    () => { adopted = true; }, { value: "" }, () => {}, new Set(),
    { start: () => {}, stop: () => {} }, queueRefresh, () => {}, createTask
  );

  await submitFn("Task meant for project 1");

  assert.equal(adopted, false, "Task dari project 1 tidak boleh diadopsi ke workspace project 2");
  assert.equal(isSubmittingTask.value, false);
  assert.ok(queueRefreshed > 0, "Queue refresh harus dipicu untuk background consistency");
});

// ── T07: ASYNC-07 ─────────────────────────────────────────────────────────────
test("T07_ASYNC07: ConsultantChat send() membuang respons terlambat jika sesi berganti", async () => {
  const chatCode = readSrc("components/drawer/ConsultantChat.vue");
  const sendSrc = between(
    chatCode,
    "let consultSeq = 0;",
    "\nfunction onKeydown(e)"
  );

  const sessionId = { value: "SESSION_1" };
  const messages = { value: [] };
  const sending = { value: false };
  const input = { value: "Pertanyaan untuk sesi 1" };
  const attachments = { value: [] };
  const props = { providerInstanceId: null, modelId: null, projectId: "p1", activeFile: null, activeTabPath: null };
  const mode = { value: "consult" };
  const activeSideTab = { value: "chat" };

  let resolveConsult;
  const consult = () => new Promise((resolve) => { resolveConsult = resolve; });

  const sendFn = new Function(
    "sessionId", "messages", "sending", "input", "attachments", "props", "mode",
    "activeSideTab", "consult", "pushHistory", "clearAttachments", "resetComposer",
    "emit", "scrollToBottom", "summarizeTools", "loadSessions", "restoreAttachments",
    "error",
    `${sendSrc}\nreturn send;`
  )(
    sessionId, messages, sending, input, attachments, props, mode,
    activeSideTab, consult, () => {}, () => {}, () => {},
    () => {}, () => {}, () => [], async () => {}, () => {},
    { value: "" }
  );

  // 1. Kirim di Sesi 1
  const sendPromise = sendFn();
  assert.equal(sending.value, true);

  // 2. Pengguna berganti ke Sesi 2
  sessionId.value = "SESSION_2";
  messages.value = [{ role: "user", text: "Halo Sesi 2" }];

  // 3. API Sesi 1 baru saja selesai merespons terlambat
  resolveConsult({
    session_id: "SESSION_1",
    reply: "Jawaban untuk Sesi 1 yang terlambat",
    status: "success",
  });
  await sendPromise;

  // 4. messages di Sesi 2 TIDAK boleh memuat balasan Sesi 1
  assert.equal(messages.value.length, 1);
  assert.equal(messages.value[0].text, "Halo Sesi 2");
  assert.equal(sessionId.value, "SESSION_2");
});

// ── T08: ASYNC-08 ─────────────────────────────────────────────────────────────
test("T08_ASYNC08: usageTokens memproses token tepat satu kali tanpa duplikasi", () => {
  // Verifikasi parsing token payload provider_response
  const payloadWithUsage = {
    provider: "antigravity",
    model: "gemini-3.8-flash",
    usage: {
      prompt: 1500,
      completion: 250,
      total: 1750,
    },
  };

  const tokens = usageTokens(payloadWithUsage);
  assert.equal(tokens, 1750, "Token total harus 1750");

  // Akumulasi satu kali
  let tokenCount = null;
  tokenCount = (tokenCount || 0) + tokens;
  assert.equal(tokenCount, 1750);

  // Payload tanpa usage mengembalikan null dan tidak menduplikasi akumulasi
  const payloadNoUsage = { provider: "antigravity", model: "gemini-3.8-flash" };
  const noTokens = usageTokens(payloadNoUsage);
  assert.equal(noTokens, null);
  if (noTokens != null) {
    tokenCount += noTokens;
  }
  assert.equal(tokenCount, 1750, "Token count tidak boleh bertambah");
});

// ── T09: ASYNC-09 ─────────────────────────────────────────────────────────────
test("T09_ASYNC09: AgentDrawerPanel mengizinkan enqueue saat running dan menolak saat isSubmitting", () => {
  const panelCode = readSrc("components/drawer/AgentDrawerPanel.vue");
  const submitSrc = between(
    panelCode,
    "function handleSubmit() {",
    "\nasync function viewReport("
  );

  let submittedTexts = [];
  const props = { isRunning: true, isSubmitting: false };
  const promptText = { value: "Langkah berikutnya setelah running" };

  const submitFn = new Function(
    "props", "promptText", "pushHistory", "emit",
    `${submitSrc}\nreturn handleSubmit;`
  )(
    props, promptText, () => {}, (name, text) => submittedTexts.push(text)
  );

  // 1. Saat running = true dan isSubmitting = false -> enqueue BERHASIL
  submitFn();
  assert.deepEqual(submittedTexts, ["Langkah berikutnya setelah running"]);

  // 2. Saat isSubmitting = true -> enqueue DITOLAK
  promptText.value = "Prompt kedua";
  props.isSubmitting = true;
  submitFn();
  assert.deepEqual(submittedTexts, ["Langkah berikutnya setelah running"], "Tidak boleh submit saat isSubmitting = true");
});

// ── T10: ASYNC-10 ─────────────────────────────────────────────────────────────
test("T10_ASYNC10: EVENT_DESCRIBERS merender kegagalan provider_response error dan task_failed", () => {
  const actCode = readSrc("components/drawer/AgentActivity.vue");
  const descSource = between(
    actCode,
    "const EVENT_DESCRIBERS = {",
    "\n// Aktivitas non-tool"
  );

  const env = { renderMarkdown: (t) => t };
  const describers = new Function(...Object.keys(env), `${descSource}\nreturn EVENT_DESCRIBERS;`)(...Object.values(env));

  // 1. Error provider pada provider_response
  const provErr = describers.provider_response(
    { provider: "antigravity", model: "gemini-3.8-flash", error: "Connection reset by peer" },
    { at: 5, ts: 500 },
    5
  );
  assert.ok(provErr, "Provider error harus terdeskripsikan");
  assert.equal(provErr.title, "Antigravity error");
  assert.equal(provErr.icon, "x");
  assert.equal(provErr.error, "Connection reset by peer");
  assert.ok(provErr.detailText.includes("[PROVIDER ERROR]"));
  assert.ok(provErr.detailText.includes("Connection reset by peer"));

  // 2. Kegagalan task pada task_failed
  const taskFail = describers.task_failed(
    { error: "AssertionError: expected true but got false" },
    { at: 6, ts: 600 },
    6
  );
  assert.ok(taskFail, "Task failed harus terdeskripsikan");
  assert.equal(taskFail.title, "Task failed");
  assert.equal(taskFail.icon, "x");
  assert.equal(taskFail.error, "AssertionError: expected true but got false");
  assert.ok(taskFail.detailText.includes("[FAILURE]"));
});

// ── T11: ASYNC-11 ─────────────────────────────────────────────────────────────
test("T11_ASYNC11: handleViewTask guard viewTaskSeq mengabaikan respons activity out-of-order", async () => {
  const appCode = readTaskLifecycleSrc();
  const viewSrc = between(
    appCode,
    "let viewTaskSeq = 0;",
    "\nasync function handleOpenReport("
  );

  let taskResolvers = {};
  const task = { id: "", prompt: "", status: "idle" };
  const runningTaskId = { value: "" };
  const taskHistory = { value: [] };
  const activityEvents = { value: [] };
  const taskTelemetry = { rounds: 0, toolCalls: 0, observations: 0 };
  const activeProject = { value: { id: "p1" } };
  const settingsOpen = { value: false };

  const getTaskActivity = (id) => new Promise((resolve) => {
    taskResolvers[id] = resolve;
  });

  const viewFn = new Function(
    "activeProject", "saveWorkspaceContext", "taskHistory", "runningTaskId",
    "task", "getTaskActivity", "computeTaskTelemetry", "activityEvents",
    "taskTelemetry", "settingsOpen",
    `${viewSrc}\nreturn handleViewTask;`
  )(
    activeProject, () => {}, taskHistory, runningTaskId,
    task, getTaskActivity, () => ({ rounds: 1, toolCalls: 1, observations: 1 }),
    activityEvents, taskTelemetry, settingsOpen
  );

  // 1. Pengguna klik Task A, lalu segera klik Task B
  const pA = viewFn("task-A");
  const pB = viewFn("task-B");

  // 2. Task B merespons lebih cepat
  taskResolvers["task-B"]({ events: [{ event_type: "tool_called", id: "b1" }] });
  await pB;
  assert.equal(task.id, "task-B");
  assert.equal(activityEvents.value[0].id, "b1");

  // 3. Task A yang terlambat baru saja merespons
  taskResolvers["task-A"]({ events: [{ event_type: "tool_called", id: "a1" }] });
  await pA;

  // 4. Data Task B tidak boleh tertimpa oleh respons Task A
  assert.equal(task.id, "task-B", "Task ID harus tetap Task B");
  assert.equal(activityEvents.value[0].id, "b1", "Activity events harus tetap milik Task B");
});

// ── T12: ASYNC-12 ─────────────────────────────────────────────────────────────
test("T12_ASYNC12: useWorkbenchLiveEvents dengan rolling buffer 500 tidak mengulang pemrosesan event lama", () => {
  const liveCode = readSrc("composables/useWorkbenchLiveEvents.js")
    .replace(/^import .*;$/gm, "")
    .replace(/export /g, "");

  const callbacks = [];
  const props = { activityEvents: [] };

  const useLive = new Function(
    "ref", "computed", "watch", "classifyDiagnostic",
    `${liveCode}\nreturn useWorkbenchLiveEvents;`
  )(
    (v) => ({ value: v }),
    (f) => ({ get value() { return f(); } }),
    (source, fn) => { callbacks.push(fn); },
    () => ({ type: "info" })
  );

  const { localOutputLines } = useLive(props);
  const activityWatcher = callbacks[0];


  // Buat 500 event awal
  const events = [];
  for (let i = 1; i <= 500; i++) {
    events.push({
      event_id: `evt-${i}`,
      event_type: "tool_called",
      payload: { tool: `tool_${i}`, path: `file_${i}.txt` },
      timestamp: i,
    });
  }

  // Jalankan watcher untuk 500 event
  activityWatcher(events);
  assert.equal(localOutputLines.value.length, 500);

  const linesCountBefore = localOutputLines.value.length;

  // Sekarang simulasikan penambahan event ke-501 dengan shift (rolling buffer)
  const shiftedEvents = events.slice(1); // buang evt-1
  shiftedEvents.push({
    event_id: "evt-501",
    event_type: "tool_called",
    payload: { tool: "tool_501", path: "file_501.txt" },
    timestamp: 501,
  });

  // Jalankan watcher untuk shiftedEvents
  activityWatcher(shiftedEvents);

  // localOutputLines dibatasi maxBufferSize (500).
  // Elemen terakhir harus tool_501, dan elemen pertama harus tool_2
  assert.equal(localOutputLines.value.length, 500);
  assert.ok(localOutputLines.value[499].text.includes("tool_501"), "Event 501 harus masuk ke ujung buffer");
  assert.ok(localOutputLines.value[0].text.includes("tool_2"), "Event 1 digeser dan digantikan tool_2");
});
