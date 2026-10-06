// Aegis Gateway API client (#52).
//
// Frontend TIPIS: hanya memanggil HTTP/SSE Django Gateway (#50/#51).
// TIDAK ada logic agent (runtime/loop/planning/tools/validation/recovery) di sini.
// TIDAK ada event system kedua: event SSE berasal dari #51 apa adanya.

const BASE = "/api";

export async function request(path, options = {}) {
  let authToken = "";
  try {
    authToken = localStorage.getItem("aegis_auth_token") || "";
  } catch {
    // Ignore storage read error
  }

  const headers = {
    "Content-Type": "application/json",
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    ...(options.headers || {}),
  };

  const resp = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  });

  if (resp.status === 401 && typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("aegis:auth-unauthorized"));
  }

  const text = await resp.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!resp.ok) {
    const message =
      data?.error?.message ||
      (typeof data?.error === "string" ? data.error : null) ||
      data?.detail ||
      `HTTP ${resp.status}`;
    const err = new Error(message);
    err.status = resp.status;
    err.code = data?.error?.code;
    throw err;
  }
  return data;
}

// --- #50 endpoints ---------------------------------------------------------
export function getHealth() {
  return request("/health");
}

export function terminateServer() {
  return request("/server/terminate", { method: "POST" });
}

// Konfigurasi provider/model/mode dari Aegis (TIDAK hardcode di frontend).
export function getConfig() {
  return request("/config");
}

// --- Global Settings (`data/settings.json` — SATU sumber konfigurasi global) ---
// Halaman Settings HANYA membaca/menulis lewat backend; backend memakai loader
// konfigurasi Aegis yang sudah ada (tidak ada sumber konfigurasi kedua).
// GET mengembalikan nilai AKTUAL; POST menggabungkan (merge) perubahan ke file
// yang sama sehingga setting lain tidak hilang.
export function getGlobalSettings() {
  return request("/settings");
}

export function updateGlobalSettings(payload) {
  return request("/settings/update", {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

// --- LLM Config / Settings -------------------------------------------------
// Halaman Settings HANYA memanggil endpoint konfigurasi LLM backend (yang
// memakai LLMConfigService Aegis existing). Nilai secret TIDAK pernah
// dikembalikan oleh backend (hanya versi masked).
export function getLLMConfig() {
  return request("/llm/config");
}

// Provider instance + nested model dari konfigurasi LLM tersimpan (SQLite).
// Dipakai alur New Task: dropdown Provider Instance + Model (bukan settings/.env).
export function getLLMProviders() {
  return request("/llm/providers");
}

export function createLLMCredential(name, value) {
  return request("/llm/credentials", {
    method: "POST",
    body: JSON.stringify({ name, value }),
  });
}

export function deleteLLMCredential(name, force = false) {
  return request("/llm/credentials", {
    method: "DELETE",
    body: JSON.stringify({ name, force }),
  });
}

export function createLLMProvider(payload) {
  return request("/llm/providers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateLLMProvider(providerId, payload) {
  return request(`/llm/providers/${encodeURIComponent(providerId)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteLLMProvider(providerId) {
  return request(`/llm/providers/${encodeURIComponent(providerId)}`, {
    method: "DELETE",
  });
}

export function testLLMProvider(providerId) {
  return request("/llm/providers/test", {
    method: "POST",
    body: JSON.stringify({ provider_id: providerId }),
  });
}

export function createLLMModel(payload) {
  return request("/llm/models", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateLLMModel(modelId, payload) {
  return request(`/llm/models/${encodeURIComponent(modelId)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteLLMModel(modelId) {
  return request(`/llm/models/${encodeURIComponent(modelId)}`, {
    method: "DELETE",
  });
}

export function getProjects() {
  return request("/projects");
}

// File Explorer: daftar file project aktif (read-only, via ListFilesTool Aegis).
export function listFiles(path = ".", recursive = false) {
  const q = new URLSearchParams({ path: path || "." });
  if (recursive) q.set("recursive", "true");
  return request(`/files?${q.toString()}`);
}

// Code Editor (Workbench): baca isi file project aktif (ReadFileTool Aegis).
// Frontend TIDAK membaca filesystem browser; isi file selalu dari backend.
export function readFileContent(path, projectId = null) {
  const query = new URLSearchParams({ path: String(path || "") });
  if (projectId) query.set("project_id", projectId);
  return request(`/files/content?${query.toString()}`);
}

// Code Editor (Workbench): simpan isi file project aktif (WriteFileTool Aegis).
// Penulisan dilakukan backend di dalam workspace boundary existing.
export function writeFileContent(path, content, projectId = null) {
  const payload = { path, content };
  if (projectId) payload.project_id = projectId;
  return request("/files/content", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Buka Windows Explorer pada ACTIVE PROJECT (path dari backend, bukan frontend).
export function openInExplorer() {
  return request("/open-in-explorer", { method: "POST" });
}

export function revealInExplorer(path) {
  return request("/reveal-in-explorer", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}

export function deleteEntry(path, type) {
  return request("/delete-entry", {
    method: "POST",
    body: JSON.stringify({ path, type }),
  });
}

export function renameEntry(oldPath, newPath) {
  return request("/files/rename", {
    method: "POST",
    body: JSON.stringify({ old_path: oldPath, new_path: newPath }),
  });
}

// --- Project Launcher / Active Project -------------------------------------
// Single-user local app: tidak ada login/session user, hanya active project.
export function createProject(name, path) {
  return request("/projects", {
    method: "POST",
    body: JSON.stringify({ name, path }),
  });
}

// Buka dialog folder native OS (Finder / file manager) — DIPANGGIL BACKEND,
// karena browser tidak dapat memperoleh path absolut dari dialog sistem.
// Result: {ok:true, path} | {ok:false, reason:"cancelled"} | throw (gagal).
export function pickFolder() {
  return request("/projects/pick-folder", { method: "POST" });
}

export function deleteProject(projectId) {
  return request(`/projects/${encodeURIComponent(projectId)}`, { method: "DELETE" });
}

// --- Project Policy / Permission Matrix (PROJECT-LOCAL) --------------------
// Policy permission SETIAP project disimpan project-local di
// `<root>/.aegis/permissions.json` (dibuat dari Default Project Permission
// Matrix saat project dibuat). Di-enforce oleh PermissionManager Aegis
// existing saat Agent melakukan action — BUKAN sistem permission kedua.
// Dikelola dari Sidebar -> Projects -> Project Settings / Policy.
// Matrix: aksi x inside/outside workspace (allow | ask | deny).
export function getProjectPolicy(projectId) {
  return request(`/projects/${encodeURIComponent(projectId)}/policy`);
}

export function saveProjectPolicy(projectId, { matrix }) {
  return request(`/projects/${encodeURIComponent(projectId)}/policy`, {
    method: "POST",
    body: JSON.stringify(matrix ? { matrix } : {}),
  });
}

export function getActiveProject() {
  return request("/active-project");
}

export function setActiveProject(projectId) {
  return request("/active-project", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId }),
  });
}

export function closeActiveProject() {
  return request("/active-project", { method: "DELETE" });
}

// --- GitHub Backup (OPTIONAL per project) ----------------------------------
// Konfigurasi disimpan project-local di `<root>/.aegis/github/`. Token TIDAK
// pernah dikembalikan backend (hanya `credential_set`). Checkpoint/history/
// recovery memakai Git history project (bukan DB checkpoint kedua).
export function getGithubConfig(projectId) {
  return request(`/projects/${encodeURIComponent(projectId)}/github`);
}

export function saveGithubConfig(projectId, payload) {
  return request(`/projects/${encodeURIComponent(projectId)}/github`, {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

export function testGithubConnection(projectId, payload = {}) {
  return request(`/projects/${encodeURIComponent(projectId)}/github/test`, {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

export function listGithubCheckpoints(projectId) {
  return request(`/projects/${encodeURIComponent(projectId)}/github/checkpoints`);
}

export function createGithubCheckpoint(projectId, description) {
  return request(`/projects/${encodeURIComponent(projectId)}/github/checkpoints`, {
    method: "POST",
    body: JSON.stringify({ description }),
  });
}

export function restoreGithubCheckpoint(projectId, commit, force = false) {
  return request(`/projects/${encodeURIComponent(projectId)}/github/restore`, {
    method: "POST",
    body: JSON.stringify({ commit, force }),
  });
}

// --- Local Git (#Fase 1.2) --------------------------------------------------
export function getProjectGitStatus(projectId) {
  return request(`/projects/${encodeURIComponent(projectId)}/git/status`);
}

export function getProjectGitDiff(projectId, filePath = null) {
  const query = filePath ? `?path=${encodeURIComponent(filePath)}` : "";
  return request(`/projects/${encodeURIComponent(projectId)}/git/diff${query}`);
}

export function getProjectGitCommits(projectId, limit = 10) {
  return request(
    `/projects/${encodeURIComponent(projectId)}/git/commits?limit=${encodeURIComponent(limit)}`
  );
}

export function getProjectGitBranches(projectId) {
  return request(`/projects/${encodeURIComponent(projectId)}/git/branches`);
}

export function discardProjectGitChanges(projectId, filePath = null) {
  return request(
    `/projects/${encodeURIComponent(projectId)}/git/discard`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: filePath }),
    }
  );
}

export function initProjectGit(projectId) {
  return request(
    `/projects/${encodeURIComponent(projectId)}/git/init`,
    {
      method: "POST",
    }
  );
}

export function deinitProjectGit(projectId) {
  return request(
    `/projects/${encodeURIComponent(projectId)}/git/deinit`,
    {
      method: "POST",
    }
  );
}

export function createTask(task, projectId = null, metadata = null, executionMode = null, images = null, activeFile = null) {
  const body = { task };
  if (projectId) body.project_id = projectId;
  if (metadata) body.metadata = metadata;
  // execution_mode — Task 01: hanya parameter task (queue/parallel), belum
  // parallel execution. Default 'queue' di backend agar task lama kompatibel.
  const rawMode = executionMode || (metadata && metadata.execution_mode) || null;
  if (rawMode) body.execution_mode = String(rawMode).toLowerCase();
  // Attachment gambar (multimodal, ADDITIVE): daftar {data: base64,
  // mime_type, filename?}. Dikirim hanya bila ada; backend memvalidasi &
  // meneruskan image parts ke jalur Agent Task (sama seperti Consultant).
  if (images && images.length) body.images = images;
  if (activeFile) body.active_file = activeFile;
  return request("/tasks", { method: "POST", body: JSON.stringify(body) });
}

export function getTask(taskId) {
  return request(`/tasks/${encodeURIComponent(taskId)}`);
}

// --- Approval (ASK) --------------------------------------------------------
// Saat policy menahan sebuah action (mode ASK/require_approval), backend
// memancarkan `approval_requested` (SSE) DAN menyediakan endpoint berikut.
// Allow/Deny disampaikan lewat endpoint resolve (terikat ke task/session).
// Ini BUKAN sistem permission kedua: enforcement tetap di PermissionManager
// existing; UI hanya menyampaikan keputusan user.
export function listApprovals(taskId = null) {
  const qs = taskId ? `?task_id=${encodeURIComponent(taskId)}` : "";
  return request(`/tasks/approvals${qs}`);
}

export function resolveApproval(requestId, allow) {
  return request("/tasks/approvals/resolve", {
    method: "POST",
    body: JSON.stringify({ request_id: requestId, allow: Boolean(allow) }),
  });
}

// Minta penghentian task (cooperative cancellation: Agent loop berhenti di
// safe boundary lalu mencatat CANCELLED ke `.aegis/log`).
export function cancelTask(taskId) {
  return request(`/tasks/${encodeURIComponent(taskId)}/cancel`, { method: "POST" });
}

// GET /api/tasks -> daftar task (history). Backend in-memory (#53).
export function listTasks(projectId = null) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request(`/tasks${qs}`);
}

// --- Task Queue (TAMPILAN/kontrol UI antrian) ------------------------------
// Satu queue GLOBAL AEGIS; sumber data = TaskRecord in-memory yang sama
// dengan GET /api/tasks. Ini BUKAN subsystem kedua.

// GET /api/tasks/queue -> antrian task aktif (pending/running/disabled).
export function listTaskQueue(projectId = null) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request(`/tasks/queue${qs}`);
}

// POST /api/tasks/queue/<id>/disable -> tandai task jangan dieksekusi.
export function disableQueueTask(taskId) {
  return request(`/tasks/queue/${encodeURIComponent(taskId)}/disable`, {
    method: "POST",
  });
}

// POST /api/tasks/queue/<id>/enable -> kembalikan task ke pending.
export function enableQueueTask(taskId) {
  return request(`/tasks/queue/${encodeURIComponent(taskId)}/enable`, {
    method: "POST",
  });
}

// POST /api/tasks/queue/<id>/move -> geser posisi (direction: up|down).
export function moveQueueTask(taskId, direction) {
  return request(`/tasks/queue/${encodeURIComponent(taskId)}/move`, {
    method: "POST",
    body: JSON.stringify({ direction }),
  });
}

// POST /api/tasks/queue/<id>/remove -> hapus task non-running dari antrian.
export function removeQueueTask(taskId) {
  return request(`/tasks/queue/${encodeURIComponent(taskId)}/remove`, {
    method: "POST",
  });
}

// POST /api/tasks/queue/clear -> kosongkan antrian non-running task.
export function clearTaskQueue(projectId = null) {
  return request("/tasks/queue/clear", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId }),
  });
}

// --- Task History / Activity / Report (membaca .aegis/log/) ---------------
// Persistent source of truth = `.aegis/log/`. Endpoint di bawah HANYA
// membaca log (read-only); tidak ada storage/subsystem kedua di frontend.

// GET /api/tasks/history -> daftar task dari persistent log (newest first).
export function listTaskHistory(projectId = null) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request(`/tasks/history${qs}`);
}

// GET /api/tasks/history/<task_id> -> ringkasan satu task dari persistent log.
export function getTaskHistory(taskId, projectId = null) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request(`/tasks/history/${encodeURIComponent(taskId)}${qs}`);
}

// DELETE /api/tasks/history/<task_id> -> hapus satu task history (.log, response, state).
export function deleteTaskHistory(taskId, projectId = null) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request(`/tasks/history/${encodeURIComponent(taskId)}${qs}`, {
    method: "DELETE",
  });
}

// POST /api/tasks/history/clear -> hapus seluruh task history untuk project.
export function clearTaskHistory(projectId = null) {
  return request("/tasks/history/clear", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId }),
  });
}

// GET /api/tasks/<task_id>/activity -> chronological activity (commentary,
// tool call, tool result, observation) dari persistent log.
export function getTaskActivity(taskId, projectId = null, eventTypes = null) {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  if (eventTypes && eventTypes.length) params.set("event_types", eventTypes.join(","));
  const qs = params.toString();
  return request(`/tasks/${encodeURIComponent(taskId)}/activity${qs ? `?${qs}` : ""}`);
}

// GET /api/tasks/<task_id>/report -> final Agent Report dari persistent log
// (task_completed.data.result, fallback task_finished.data.result).
export function getTaskReport(taskId, projectId = null) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request(`/tasks/${encodeURIComponent(taskId)}/report${qs}`);
}

// --- Consultant (Aegis reasoning layer) ------------------------------------
// POST /api/consultant/consult -> satu giliran konsultasi. Backend menjalankan
// reasoning/tool/boundary/bible memakai subsistem Aegis yang sudah ada.
// `mode` ("quick" | "investigate", default "quick") menentukan tool yang benar-
// benar tersedia bagi LLM. `images` (opsional) = daftar gambar multimodal
// ({data: base64, mime_type, filename?}). Response memuat reply, tool_events,
// task_proposal.
export function consult(
  message,
  {
    sessionId = null,
    providerInstanceId = null,
    modelId = null,
    projectId = null,
    mode = "quick",
    images = null,
    activeFile = null,
  } = {}
) {
  const body = { message };
  if (sessionId) body.session_id = sessionId;
  if (providerInstanceId) body.provider_instance_id = providerInstanceId;
  if (modelId) body.model_id = modelId;
  if (projectId) body.project_id = projectId;
  if (mode) body.mode = mode;
  if (images && images.length) body.images = images;
  if (activeFile) body.active_file = activeFile;
  return request("/consultant/consult", { method: "POST", body: JSON.stringify(body) });
}

// Consultant session management: persistent transcripts.
export function listConsultantSessions(projectId = null) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request(`/consultant/sessions${qs}`);
}

export function getConsultantSession(sessionId, projectId = null) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request(`/consultant/sessions/${encodeURIComponent(sessionId)}${qs}`);
}

export function createConsultantSession({ projectId = null, title = null } = {}) {
  const body = {};
  if (projectId) body.project_id = projectId;
  if (title) body.title = title;
  return request("/consultant/sessions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function renameConsultantSession(sessionId, title, projectId = null) {
  const body = { title };
  if (projectId) body.project_id = projectId;
  return request(`/consultant/sessions/${encodeURIComponent(sessionId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteConsultantSession(sessionId, projectId = null) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request(`/consultant/sessions/${encodeURIComponent(sessionId)}${qs}`, {
    method: "DELETE",
  });
}

// --- Extension Management (Task 07) - generic management API (thin over ExtensionManager) ---
export function listExtensions() {
  return request("/extensions");
}
export function getExtension(extensionId) {
  return request(`/extensions/${encodeURIComponent(extensionId)}`);
}
export function installExtension(repositoryUrl, ref = null) {
  const body = { repository_url: repositoryUrl };
  if (ref) body.ref = ref;
  return request("/extensions/install", { method: "POST", body: JSON.stringify(body) });
}
export function enableExtension(extensionId) {
  return request(`/extensions/${encodeURIComponent(extensionId)}/enable`, { method: "POST" });
}
export function disableExtension(extensionId) {
  return request(`/extensions/${encodeURIComponent(extensionId)}/disable`, { method: "POST" });
}
export function updateExtension(extensionId, repositoryUrl = null, ref = null) {
  const body = {};
  if (repositoryUrl) body.repository_url = repositoryUrl;
  if (ref) body.ref = ref;
  return request(`/extensions/${encodeURIComponent(extensionId)}/update`, { method: "POST", body: JSON.stringify(body) });
}
export function uninstallExtension(extensionId) {
  return request(`/extensions/${encodeURIComponent(extensionId)}`, { method: "DELETE" });
}

// --- Extension UI System (Task 05) - generic contract -----------------------
// UI contributions: daftar UI capability extension (form/table/chart/modal/...)
// Config form schema: declarative schema untuk form config (secret-safe)
// Result resolution: generic renderer resolution untuk structured result
export function listExtensionUI({ extensionId = null, type = null, enabledOnly = true } = {}) {
  const params = new URLSearchParams();
  if (extensionId) params.set("extension_id", extensionId);
  if (type) params.set("type", type);
  if (!enabledOnly) params.set("enabled_only", "0");
  const qs = params.toString();
  return request(`/extensions/ui${qs ? `?${qs}` : ""}`);
}

export function getExtensionConfigSchema(extensionId, projectId = null) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request(`/extensions/config/${encodeURIComponent(extensionId)}${qs}`);
}


export function setExtensionConfigValue(extensionId, key, value, opts = {}) {
  const body = { value };
  if (opts.scope) body.scope = opts.scope;
  if (opts.projectId) body.project_id = opts.projectId;
  return request(`/extensions/config/${encodeURIComponent(extensionId)}/${encodeURIComponent(key)}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}


// --- #51 SSE ---------------------------------------------------------------
export const KNOWN_SSE_EVENTS = Object.freeze([
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
]);

// Membuka EventSource ke /api/events (opsional filter session_id/task_id/last_event_id).
// Mengembalikan EventSource agar pemanggil dapat menutupnya (disconnect).
export function openEventStream({
  sessionId = null,
  taskId = null,
  lastEventId = null,
  onEvent = null,
  onOpen = null,
  onError = null,
} = {}) {
  const params = new URLSearchParams();
  if (sessionId) params.set("session_id", sessionId);
  if (taskId) params.set("task_id", taskId);
  if (lastEventId) params.set("last_event_id", lastEventId);
  const qs = params.toString();
  const url = `${BASE}/events${qs ? `?${qs}` : ""}`;

  const source = new EventSource(url);
  if (typeof onOpen === "function") source.addEventListener("open", onOpen);
  if (typeof onError === "function") source.addEventListener("error", onError);

  // Event Aegis dikirim dengan `event: <event_type>`. Kita dengarkan tipe
  // yang dikenal (#51) tanpa mengasumsikan semuanya selalu ada.
  const handle = (evt) => {
    let payload = null;
    try {
      payload = JSON.parse(evt.data);
    } catch {
      payload = { raw: evt.data };
    }
    if (payload && typeof payload === "object") {
      if (evt.lastEventId && !payload.lastEventId) {
        payload.lastEventId = evt.lastEventId;
      }
      if (!payload.event_type && evt.type && evt.type !== "message") {
        payload.event_type = evt.type;
      }
    }
    if (onEvent) onEvent(payload);
  };

  KNOWN_SSE_EVENTS.forEach((name) => source.addEventListener(name, handle));
  // Fallback: event tanpa tipe eksplisit.
  source.onmessage = handle;

  return source;
}

// --- Terminal command streaming ------------------------------------------
// POST /api/terminal/run → stream SSE output line by line.
// onChunk(eventType, data) called per SSE event.
// signal: optional AbortSignal (pass AbortController.signal for Ctrl+C support).
export async function streamTerminalCommand(projectId, command, onChunk, signal = null) {
  const fetchOpts = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId || "", command }),
  };
  if (signal) fetchOpts.signal = signal;

  let res;
  try {
    res = await fetch(`${BASE}/terminal/run`, fetchOpts);
  } catch (err) {
    // AbortError = user pressed Ctrl+C before response started.
    if (err.name === "AbortError") return;
    throw err;
  }

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody?.error?.message || `HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const frames = buf.split("\n\n");
      buf = frames.pop();
      for (const frame of frames) {
        if (!frame.trim()) continue;
        let eventType = "terminal_output";
        let data = null;
        for (const line of frame.split("\n")) {
          if (line.startsWith("event: ")) eventType = line.slice(7).trim();
          else if (line.startsWith("data: ")) {
            try { data = JSON.parse(line.slice(6)); } catch { /* skip */ }
          }
        }
        if (data !== null && onChunk) onChunk(eventType, data);
      }
    }
  } catch (err) {
    // AbortError mid-stream = Ctrl+C after stream started — not an error.
    if (err.name !== "AbortError") throw err;
  } finally {
    reader.cancel().catch(() => {});
  }
}

// --- Google OAuth & Identity Gateway (docs/Oauth-Google.md, Phase 0) -------
export function getGoogleAuthUrl(redirectUri = "") {
  const query = redirectUri ? `?redirect_uri=${encodeURIComponent(redirectUri)}` : "";
  return request(`/auth/google/url${query}`);
}

export function postGoogleAuthCallback(payload) {
  return request("/auth/google/callback", {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

export function getAuthMe() {
  return request("/auth/me");
}

export function postAuthLogout() {
  return request("/auth/logout", {
    method: "POST",
  });
}

