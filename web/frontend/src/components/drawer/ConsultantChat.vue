<script setup>
// Aegis Consultant chat.
//
// Consultant = reasoning layer (Project Intelligence + Investigation +
// Validation + Recommendation + Task Generator) yang TERPISAH dari Agent.
// Frontend ini TIPIS: hanya memanggil endpoint Consultant di Gateway; seluruh
// reasoning/tool/boundary/bible dijalankan backend memakai subsistem Aegis yang
// sudah ada. Task Proposal yang dihasilkan dapat dikirim ke Agent lewat alur
// task existing (emit "run-task" -> App membuat task).
import { computed, nextTick, onMounted, ref, watch } from "vue";
import {
  consult,
  listConsultantSessions,
  getConsultantSession,
  createConsultantSession,
  renameConsultantSession,
  deleteConsultantSession,
} from "../api.js";
import { renderMarkdown } from "../markdown.js";
import QueuePanel from "../queue/QueuePanel.vue";
import PromptAutocompletePopover from "../ui/PromptAutocompletePopover.vue";
import AppThinkingBlock from "../ui/AppThinkingBlock.vue";
import { usePromptAutocomplete } from "../services/promptSuggestionService.js";
import { useAttachmentPipeline } from "../composables/useAttachmentPipeline.js";
import {
  stripTaskProposal,
  assistantText,
  extractFirstCodeBlock,
  extractTaskProposalText,
} from "../services/consultantProposalService.js";
const props = defineProps({
  embedded: { type: Boolean, default: true },
  providers: { type: Array, default: () => [] },
  providerInstanceId: { type: String, default: "" },
  modelId: { type: String, default: "" },
  providerLabel: { type: String, default: "" },
  modelLabel: { type: String, default: "" },
  // Status task Agent yang sedang berjalan (dari App.vue, sumber tunggal).
  // Ini INFORMASI "global agent busy" — TIDAK memblokir Run Task, karena
  // antrian global (concurrency=1) memang menerima task baru saat slot terisi.
  running: { type: Boolean, default: false },
  // task_id task yang BARU SAJA dibuat App.vue dari aksi Run Task (di-bump
  // App.vue setiap submitTask). Dipakai child untuk memasangkan task ke
  // proposal yang memicunya (per-proposal, bukan global).
  submittedTaskId: { type: String, default: "" },
  // task_id yang SEDANG RUNNING di Global Task Queue (sumber tunggal: queue API
  // via App.vue). Dipakai HANYA untuk indikator per-proposal "Running…" — BUKAN
  // untuk memblokir submission proposal lain.
  runningTaskId: { type: String, default: "" },
  // task_id task terminal terakhir (kompatibilitas; tidak dipakai untuk gating).
  terminalTaskId: { type: String, default: "" },
  // Penanda refresh panel TASKS (dinaikkan App.vue setelah Run Task / event
  // terminal task). Panel TASKS membaca SATU queue global yang sama.
  queueRefreshKey: { type: Number, default: 0 },
  // Project aktif (dari App.vue). Panel TASKS di sidebar Consultant hanya
  // menampilkan task milik project ini — sama persis dengan QueuePanel di
  // Workbench/Tasks page. Tanpa ini, queue GLOBAL (semua project) tampil dan
  // task tercampur antar-project. Queue-nya tetap SATU (global); hanya
  // tampilan yang di-scope ke project aktif.
  projectId: { type: String, default: "" },
  // Session konsultan yang SEDANG aktif (di-persist App.vue, mis. localStorage)
  // agar switch/New bertahan antar-reload. Anak meng-Emit update bila berubah.
  activeSessionId: { type: String, default: "" },
  activeTabPath: { type: String, default: "" },
  activeFile: { type: Object, default: () => null },
});

const emit = defineEmits([
  "close",
  "update:providerInstanceId",
  "update:provider-instance-id",
  "update:modelId",
  "update:model-id",
  "update:activeSessionId",
  "update:active-session-id",
  "run-task",
  "stop-task",
  "view-task",
  "apply-to-editor",
  "open-settings",
  "consultant-event",
]);
const messages = ref([]);
const activeSideTab = ref("sessions");
const input = ref("");
const sending = ref(false);
const error = ref("");
const sessionId = ref("");
const scroller = ref(null);
const composer = ref(null);
const fileInput = ref(null);

// Session list for the Sessions tab (persisted on backend).
const sessionsLoading = ref(false);
const sessions = ref([]);
const switchingSession = ref(false);

// Sync local sessionId with prop (from App.vue localStorage persistence).
watch(
  () => props.activeSessionId,
  (id) => {
    if (id && id !== sessionId.value) {
      sessionId.value = id;
      resumeSessionFromId(id);
    }
  },
  { immediate: true }
);

// Load session list when tab becomes visible or project changes.
watch(
  () => [activeSideTab.value, props.projectId],
  () => {
    if (activeSideTab.value === "sessions") {
      loadSessions();
    }
  },
  { immediate: true }
);

async function loadSessions() {
  if (sessionsLoading.value) return;
  sessionsLoading.value = true;
  try {
    const data = await listConsultantSessions(props.projectId || null);
    sessions.value = data.sessions || [];
  } catch (e) {
    sessions.value = [];
  } finally {
    sessionsLoading.value = false;
  }
}

async function switchSession(id) {
  if (sending.value || switchingSession.value || id === sessionId.value) return;
  switchingSession.value = true;
  error.value = "";
  try {
    const sess = await getConsultantSession(id, props.projectId || null);
    if (!sess) {
      error.value = "Session not found.";
      return;
    }
    sessionId.value = id;
    emit("update:activeSessionId", id);
    // Rebuild messages from turns (resume penuh).
    const turns = sess.turns || [];
    messages.value = turns.map((t) => {
      if (t.role === "user") {
        return { role: "user", text: t.text || "" };
      }
      return {
        role: "assistant",
        text: t.text || "",
        tools: [],
        taskProposal: null,
        failed: false,
      };
    });
    scrollToBottom();
  } catch (e) {
    error.value = e.message || "Failed to load session.";
  } finally {
    switchingSession.value = false;
  }
}

let resumeSessionSeq = 0;
async function resumeSessionFromId(id) {
  // Called when props.activeSessionId changes; load turns without UI blocking.
  if (!id) return;
  const thisSeq = ++resumeSessionSeq;
  try {
    const sess = await getConsultantSession(id, props.projectId || null);
    if (!sess || thisSeq !== resumeSessionSeq) return;
    const turns = sess.turns || [];
    messages.value = turns.map((t) => {
      if (t.role === "user") {
        return {
          role: "user",
          text: t.content || t.text || "",
          mode: t.mode || "ask",
          images: t.images || [],
        };
      }
      return {
        role: "assistant",
        text: t.content || t.text || (t.execution?.report || ""),
        mode: t.mode || "ask",
        execution: t.execution || null,
        tools: summarizeTools((t.execution && t.execution.tool_events) || t.tools || []),
        taskProposal: t.taskProposal || null,
        failed: t.execution?.status === "failed",
      };
    });
    scrollToBottom();
  } catch (e) {
    // Silent fail; keep current state.
  }
}

async function createNewSession() {
  if (sending.value) return;
  error.value = "";
  try {
    const sess = await createConsultantSession({
      projectId: props.projectId || null,
      title: null,
    });
    sessionId.value = sess.session_id;
    emit("update:activeSessionId", sess.session_id);
    messages.value = [
      {
        role: "assistant",
        text:
          "Halo! Saya **AEGIS Ask**. Saya siap membantu menganalisis arsitektur proyek, " +
          "menjelaskan alur kode, atau menyusun rekomendasi teknis. Pilih mode **Quick** (ringkas berbasis konteks proyek) " +
          "atau **Deep** (investigasi mendalam dengan inspeksi berkas kode). Apa yang ingin Anda diskusikan?",
        tools: [],
        taskProposal: null,
      },
    ];
    clearAttachments();
    await loadSessions();
    scrollToBottom();
  } catch (e) {
    error.value = e.message || "Failed to create session.";
  }
}

async function removeSession(id, e) {
  if (e) e.stopPropagation();
  try {
    await deleteConsultantSession(id, props.projectId || null);
    if (sessionId.value === id) {
      startNewSession();
    } else {
      await loadSessions();
    }
  } catch (err) {
    error.value = err.message || "Failed to delete session.";
  }
}
const renamingSessionId = ref(null);
const renameInput = ref("");

const activeSessionTitle = computed(() => {
  const current = sessions.value.find((s) => s.session_id === sessionId.value);
  return current?.title || "New Chat";
});

function promptRenameCurrentSession() {
  const current = activeSessionTitle.value;
  const newTitle = prompt("Rename conversation:", current);
  if (!newTitle || newTitle.trim() === "" || newTitle.trim() === current) return;
  saveSessionRename(sessionId.value, newTitle.trim());
}

function startSessionRename(s) {
  renamingSessionId.value = s.session_id;
  renameInput.value = s.title || "New Chat";
}

async function saveSessionRename(id, explicitTitle = null) {
  const newTitle = (explicitTitle !== null ? explicitTitle : renameInput.value).trim();
  renamingSessionId.value = null;
  if (!newTitle || !id) return;
  try {
    await renameConsultantSession(id, newTitle, props.projectId || null);
    await loadSessions();
  } catch (err) {
    error.value = err.message || "Failed to rename session.";
  }
}

function formatSessionTime(timestamp) {
  if (!timestamp) return "";
  const now = Date.now() / 1000;
  const diff = Math.floor(now - timestamp);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// Gambar terlampir (belum dikirim) dikelola via useAttachmentPipeline.
const {
  attachments,
  attachError,
  clearAttachments,
  removeAttachment,
  restoreAttachments,
  triggerAttach: doTriggerAttach,
  onFilesPicked,
} = useAttachmentPipeline({ scopeLabel: "pesan" });

watch(attachError, (err) => {
  if (err) error.value = err;
});

function triggerAttach() {
  doTriggerAttach(fileInput.value, sending.value);
}

// Tinggi maksimum composer (px). Di atas nilai ini textarea scroll internal
// agar footer tidak memanjang tanpa batas.
const COMPOSER_MAX_HEIGHT = 140;

// Auto-grow: reset ke auto dulu lalu set tinggi = konten sebenarnya,
// dibatasi COMPOSER_MAX_HEIGHT.
function autoGrow() {
  const el = composer.value;
  if (!el) return;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, COMPOSER_MAX_HEIGHT) + "px";
  el.style.overflowY = el.scrollHeight > COMPOSER_MAX_HEIGHT ? "auto" : "hidden";
}
function resetComposer() {
  const el = composer.value;
  if (!el) return;
  el.style.height = "auto";
  el.style.overflowY = "hidden";
}

// Mode Ask: "quick" (Ringkas) atau "investigate" (Mendalam / Deep).
// - quick       : Analisis ringkas berbasis Project Bible & konteks proyek.
// - investigate : Investigasi mendalam dengan akses pembacaan & penelusuran kode proyek.
// Mengganti mode TIDAK mereset sesi/konteks percakapan.
const mode = ref("balanced");
const MODES = [
  { id: "fast", label: "Fast" },
  { id: "balanced", label: "Balanced" },
  { id: "deep", label: "Deep" },
];
function setMode(id) {
  if (id === "quick") mode.value = "fast";
  else if (id === "investigate") mode.value = "deep";
  else if (["fast", "balanced", "deep"].includes(id)) {
    mode.value = id;
  }
}

const inputPlaceholder = computed(() => "Ask anything…");

const providerOptions = computed(() =>
  (props.providers || []).filter((p) => p.enabled !== false)
);
// Model difilter: HANYA model milik provider instance yang sedang dipilih.
function modelsFor(providerId) {
  const inst = providerOptions.value.find((p) => p.id === providerId);
  return inst ? (inst.models || []).filter((m) => m.enabled !== false) : [];
}
const modelOptions = computed(() => modelsFor(props.providerInstanceId));

function providerLabel(p) {
  const type = p.provider_label || p.provider_type || "";
  return type ? `${p.name} (${type})` : p.name;
}

const displayProvider = computed(() => {
  if (props.providerLabel) return props.providerLabel;
  const inst = (props.providers || []).find((p) => p.id === props.providerInstanceId);
  return inst ? inst.name : (props.providerInstanceId || "");
});

const displayModel = computed(() => {
  return props.modelLabel || props.modelId || "";
});
// Ubah Provider -> daftar model mengikuti provider baru dan pilih model valid
// pertama (model lama milik provider lain tidak boleh tertinggal).
function onProviderChange(e) {
  const nextId = String(e.target.value || "");
  emit("update:providerInstanceId", nextId);
  emit("update:provider-instance-id", nextId);
  const models = modelsFor(nextId);
  const firstMid = models[0] ? models[0].id : "";
  emit("update:modelId", firstMid);
  emit("update:model-id", firstMid);
}
function onModelChange(e) {
  const mid = String(e.target.value || "");
  emit("update:modelId", mid);
  emit("update:model-id", mid);
}

// Jaga konsistensi: bila model terpilih tidak ada pada provider aktif (mis.
// state dibagi dengan New Task composer), koreksi ke model valid pertama.
watch(
  () => [props.providerInstanceId, props.modelId],
  () => {
    if (!props.providerInstanceId) return;
    const models = modelOptions.value;
    if (!models.length) return;
    if (!models.some((m) => m.id === props.modelId)) {
      emit("update:modelId", models[0].id);
      emit("update:model-id", models[0].id);
    }
  }
);
// --- Runner Task Proposal (provider/model untuk MENJALANKAN task) -----------
// TERPISAH dari pilihan header (yang mengontrol CHAT). Default mengikuti
// pilihan header; setelah user menyentuhnya sendiri, ia INDEPENDEN (perubahan
// header tidak lagi mengubahnya, dan sebaliknya). Selama belum disentuh, ia
// tetap mengikuti header agar default konsisten saat provider/model memuat.
const proposalProviderInstanceId = ref("");
const proposalModelId = ref("");
const proposalExecutionMode = ref("queue");
const proposalTouched = ref(false);

watch(
  () => [props.providerInstanceId, props.modelId],
  ([pid, mid]) => {
    if (proposalTouched.value) return;
    proposalProviderInstanceId.value = pid || "";
    proposalModelId.value = mid || "";
  },
  { immediate: true }
);

// Model difilter mengikuti provider proposal (perilaku sama dengan header).
const proposalModelOptions = computed(() =>
  modelsFor(proposalProviderInstanceId.value)
);

function onProposalProviderChange(e) {
  proposalTouched.value = true;
  const nextId = String(e.target.value || "");
  proposalProviderInstanceId.value = nextId;
  const models = modelsFor(nextId);
  proposalModelId.value = models[0] ? models[0].id : "";
}
function onProposalModelChange(e) {
  proposalTouched.value = true;
  proposalModelId.value = String(e.target.value || "");
}

function scrollToBottom() {
  nextTick(() => {
    const el = scroller.value;
    if (el) el.scrollTop = el.scrollHeight;
  });
}

// Blok Task Proposal berpagar bahasa `task`/`task-proposal`.
// Backend (consultant/service.py) mengekstrak blok ini menjadi field
// `task_proposal`, TETAPI `reply` mentah masih memuat blok yang sama. Bila
// keduanya dirender, teks Task muncul DUA KALI (di bubble balasan + di card
// Task Proposal). Sesuai permintaan: hanya card yang menampilkan Task, jadi
// blok berpagar `task` dibersihkan dari teks bubble assistant.

// --- Copy pesan -------------------------------------------------------------
// Salin isi bubble ke clipboard. Untuk assistant: salin teks yang SAMA dengan
// yang tampil di bubble (tanpa blok fenced Task Proposal), bukan teks mentah
// yang memuat ```task. Untuk user: salin teks pesan apa adanya.
// Indeks pesan yang baru saja disalin, untuk feedback "Copied" sementara.
const copiedIndex = ref(-1);
let copiedTimer = null;

function messageCopyText(msg) {
  if (!msg) return "";
  if (msg.role === "assistant") return assistantText(msg);
  return msg.text || "";
}

async function copyMessage(msg, index) {
  const text = messageCopyText(msg);
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    return;
  }
  copiedIndex.value = index;
  if (copiedTimer) clearTimeout(copiedTimer);
  copiedTimer = setTimeout(() => {
    copiedIndex.value = -1;
    copiedTimer = null;
  }, 1400);
}


function applyCodeToEditor(msg) {
  const code = extractFirstCodeBlock(assistantText(msg));
  if (!code) return;
  emit("apply-to-editor", { code, message: msg });
}

// --- Copy Task Proposal -----------------------------------------------------
// Tombol Copy di card Task Proposal (kiri bawah), memakai pola .copy-btn yang
// sama dengan bubble chat. Isi yang disalin = teks proposal yang tampil.
const proposalCopied = ref(false);
let proposalCopiedTimer = null;

async function copyProposal(proposal) {
  const text = proposal || lastProposal.value || "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(String(text));
  } catch (e) {
    return;
  }
  proposalCopied.value = true;
  if (proposalCopiedTimer) clearTimeout(proposalCopiedTimer);
  proposalCopiedTimer = setTimeout(() => {
    proposalCopied.value = false;
    proposalCopiedTimer = null;
  }, 1400);
}

watch(messages, scrollToBottom, { deep: true });

function summarizeTools(events) {
  if (!events || !events.length) return [];
  const done = events.filter((e) => e.success !== null && e.success !== undefined);
  return done.map((e) => ({
    tool: e.tool || "",
    target: e.target || "",
    success: e.success !== false,
  }));
}



const {
  popoverVisible,
  popoverType,
  popoverItems,
  popoverIndex,
  updateSuggestions,
  applySelectedItem,
  handleKeydown: autocompleteKeydown,
  pushHistory,
  seedHistory,
  closePopover,
} = usePromptAutocomplete({
  storageKey: "aegis_consultant_prompt_history",
  onUpdateText: (val) => {
    input.value = val;
    nextTick(autoGrow);
  },
});

watch(
  () => messages.value,
  (msgs) => {
    if (!Array.isArray(msgs)) return;
    const userPrompts = msgs
      .filter((m) => m && m.role === "user" && m.text)
      .map((m) => m.text)
      .reverse(); // newest first
    if (userPrompts.length > 0) {
      seedHistory(userPrompts);
    }
  },
  { immediate: true, deep: true }
);

function onComposerInput() {
  autoGrow();
  const el = composer.value;
  const pos = el ? el.selectionStart : input.value.length;
  updateSuggestions(input.value, pos);
}

function onSelectSuggestion(item) {
  input.value = applySelectedItem(item, input.value, composer.value);
  nextTick(autoGrow);
}
let consultSeq = 0;
async function send() {
  const text = input.value.trim();
  const pending = attachments.value.slice();
  const savedDraftText = input.value;
  const savedDraftAttachments = pending;
  if ((!text && !pending.length) || sending.value) return;
  const reqSessionId = sessionId.value || null;
  const currentSeq = ++consultSeq;
  error.value = "";
  messages.value.push({
    role: "user",
    text,
    images: pending.map((a) => a.dataUrl),
  });
  pushHistory(text);
  input.value = "";
  clearAttachments();
  resetComposer();
  sending.value = true;
  emit("consultant-event", { type: "sending_started", prompt: text });
  scrollToBottom();
  try {
    const data = await consult(text, {
      sessionId: sessionId.value || null,
      providerInstanceId: props.providerInstanceId || null,
      modelId: props.modelId || null,
      projectId: props.projectId || null,
      mode: mode.value,
      activeFile: props.activeFile || (props.activeTabPath ? { path: props.activeTabPath } : null),
      images: pending.length
        ? pending.map((a) => ({
            data: a.base64,
            mime_type: a.mimeType,
            filename: a.name,
          }))
        : null,
    });
    if (currentSeq !== consultSeq || (reqSessionId && sessionId.value !== reqSessionId)) return;
    sessionId.value = data.session_id || sessionId.value;
    messages.value.push({
      role: "assistant",
      text: data.reply || "(no reply)",
      tools: summarizeTools(data.tool_events),
      taskProposal: data.task_proposal || null,
      failed: data.status === "failed",
      reasoning: data.reasoning || null,
    });
    // Refresh session list so newly created sessions appear in the tab.
    if (activeSideTab.value === "sessions") {
      await loadSessions();
    }
    emit("consultant-event", { type: "sending_completed", prompt: text, error: null, data });
  } catch (e) {
    if (currentSeq !== consultSeq || (reqSessionId && sessionId.value !== reqSessionId)) return;
    error.value = e.message || "Consultant request failed.";
    if (!input.value && savedDraftText) {
      input.value = savedDraftText;
    }
    if (!attachments.value.length && savedDraftAttachments.length) {
      restoreAttachments(savedDraftAttachments);
    }
    messages.value.push({
      role: "assistant",
      text: `Consultant error: ${error.value}`,
      tools: [],
      taskProposal: null,
      failed: true,
    });
    emit("consultant-event", { type: "sending_completed", prompt: text, error: error.value, data: null });
  } finally {
    if (currentSeq === consultSeq) {
      sending.value = false;
      scrollToBottom();
    }
  }
}

function onKeydown(e) {
  const res = autocompleteKeydown(e, input.value, composer.value);
  if (res.handled) {
    if (res.text !== undefined) {
      input.value = res.text;
      nextTick(autoGrow);
    }
    return;
  }
  // Enter = send. Shift+Enter = newline.
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
}

// Task Proposal terakhir (dari pesan assistant terakhir yang memilikinya).
const lastProposal = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i -= 1) {
    if (messages.value[i].taskProposal) return messages.value[i].taskProposal;
  }
  return null;
});

// --- Status Run Task (PER Task Proposal) ------------------------------------
// Bug yang diperbaiki: tombol Run Task SEBELUMNYA di-disable GLOBAL dari satu
// task_id (submittedTaskId) sampai task itu terminal -> selama Agent RUNNING,
// SELURUH tombol Run Task (termasuk Task Proposal BARU) ikut mati, sehingga
// task baru tidak bisa di-enqueue. Itu mencampur can_execute (slot eksekusi)
// dengan can_enqueue (submission).
//
// Sekarang anti-double-submit disimpan PER PROPOSAL (di objek message
// `runTaskId`) dan HANYA proposal yang task-nya sedang menempati slot eksekusi
// (`props.runningTaskId`, sumber tunggal = Global Task Queue via App.vue) yang
// "busy". Task yang RUNNING tidak memblokir submission proposal LAIN: enqueue
// selalu boleh, scheduler serial backend yang menentukan kapan dieksekusi.
const pendingRunIndex = ref(-1);

function proposalRunId(i) {
  const m = messages.value[i];
  return (m && m.runTaskId) || "";
}

// True HANYA untuk proposal yang task-nya sendiri sedang RUNNING (slot
// eksekusi) atau sedang dalam proses submit.
function isProposalBusy(i) {
  const id = proposalRunId(i);
  if (!id) return false;
  if (id === "__pending__") return true; // createTask sedang berjalan
  return Boolean(props.runningTaskId) && id === props.runningTaskId;
}

// Safety: bila createTask gagal, jangan biarkan penanda "__pending__" nyangkut
// (tombol tetap terkunci). Timer dibatalkan begitu App.vue membalas task_id.
const PENDING_RUN_TIMEOUT_MS = 15000;
let pendingRunTimer = null;
function clearPendingRunTimer() {
  if (pendingRunTimer) {
    clearTimeout(pendingRunTimer);
    pendingRunTimer = null;
  }
}

// App.vue membuat task dari aksi Run Task -> pasangkan task_id ke proposal yang
// MEMICU-nya (bukan global), sehingga proposal lain tetap dapat di-enqueue.
watch(
  () => props.submittedTaskId,
  (id) => {
    if (!id || pendingRunIndex.value < 0) return;
    clearPendingRunTimer();
    const m = messages.value[pendingRunIndex.value];
    if (m) m.runTaskId = id;
    pendingRunIndex.value = -1;
  }
);

function runTask(proposal, index = -1) {
  const target = proposal || lastProposal.value;
  if (!target) return;
  if (index >= 0 && isProposalBusy(index)) return;
  // Tandai proposal INI "sedang submit" sampai App.vue mengembalikan task_id.
  if (index >= 0) {
    pendingRunIndex.value = index;
    const m = messages.value[index];
    if (m) m.runTaskId = "__pending__";
    clearPendingRunTimer();
    pendingRunTimer = setTimeout(() => {
      pendingRunTimer = null;
      if (pendingRunIndex.value !== index) return;
      const pending = messages.value[index];
      if (pending && pending.runTaskId === "__pending__") pending.runTaskId = "";
      pendingRunIndex.value = -1;
    }, PENDING_RUN_TIMEOUT_MS);
  }
  // Bawa pilihan runner (provider/model DARI CARD PROPOSAL, bukan header) ke
  // alur task existing. App.vue meneruskannya sebagai metadata task sehingga
  // task benar-benar memakai provider/model ini.
  emit("run-task", {
    text: target,
    providerInstanceId: props.embedded ? (props.providerInstanceId || "") : (proposalProviderInstanceId.value || ""),
    modelId: props.embedded ? (props.modelId || "") : (proposalModelId.value || ""),
    executionMode: proposalExecutionMode.value || "queue",
  });
}

function startNewSession() {
  sessionId.value = "";
  messages.value = [];
  attachments.value = [];
  error.value = "";
  pendingRunIndex.value = -1;
  clearPendingRunTimer();
  emit("update:activeSessionId", "");
  // Persistently create a new backend session so it appears in the list.
  createNewSession();
}

onMounted(() => {
  // Only add greeting if no persisted session id was passed in.
  if (!sessionId.value) {
    messages.value.push({
      role: "assistant",
      text:
        "Halo! Saya **AEGIS Ask**. Saya siap membantu menganalisis arsitektur proyek, " +
        "menjelaskan alur kode, atau menyusun rekomendasi teknis. Pilih mode **Quick** (ringkas berbasis konteks proyek) " +
        "atau **Deep** (investigasi mendalam dengan inspeksi berkas kode). Apa yang ingin Anda diskusikan?",
      tools: [],
      taskProposal: null,
    });
  }
  scrollToBottom();
});
</script>

<template>
  <div
    class="consultant-wrapper"
    :class="{ 'consultant-embedded': embedded, 'modal-backdrop': !embedded }"
    @click.self="!embedded && $emit('close')"
  >
    <div
      class="consultant-content-pane"
      :class="{ 'consultant-embedded-pane': embedded, 'modal consultant-m': !embedded }"
      :role="embedded ? 'region' : 'dialog'"
      :aria-modal="!embedded ? 'true' : undefined"
      aria-label="AEGIS Ask"
    >
      <!-- Standalone Modal Header & Modes (When !embedded) -->
      <template v-if="!embedded">
        <div class="consultant-head">
          <div class="consultant-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2a4 4 0 0 1 4 4c0 1.95-1.4 3.58-3.25 3.93L12 22l-.75-12.07A4.001 4.001 0 0 1 12 2z"/><circle cx="12" cy="6" r="1.5" fill="currentColor" stroke="none"/><path d="M9 14l-3 3 3 3M15 14l3 3-3 3"/></svg>
            AEGIS Ask
          </div>
          <div class="consultant-selects">
            <label class="consultant-select">
              <span class="cs-label">Provider</span>
              <select class="input-a" :value="providerInstanceId" @change="onProviderChange">
                <option v-if="!providerOptions.length" value="">No provider instance</option>
                <option v-for="p in providerOptions" :key="p.id" :value="p.id">
                  {{ providerLabel(p) }}
                </option>
              </select>
            </label>
            <label class="consultant-select">
              <span class="cs-label">Model</span>
              <select
                class="input-a"
                :value="modelId"
                :disabled="!providerInstanceId"
                @change="onModelChange"
              >
                <option v-if="!modelOptions.length" value="">No model</option>
                <option v-for="m in modelOptions" :key="m.id" :value="m.id">
                  {{ m.model_name }}
                </option>
              </select>
            </label>
          </div>
          <button class="consultant-new" type="button" title="New session" @click="startNewSession">
            New
          </button>
          <button class="close-x" type="button" title="Close" @click="$emit('close')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </div>

        <div class="consultant-modes" role="group" aria-label="AEGIS mode">
          <span class="cm-label">Mode</span>
          <button
            v-for="m in MODES"
            :key="m.id"
            type="button"
            class="mode-btn"
            :class="{ active: mode === m.id }"
            :aria-pressed="mode === m.id ? 'true' : 'false'"
            :title="`${m.label} mode`"
            :disabled="sending"
            @click="setMode(m.id)"
          >
            <span class="mb-label">{{ m.label }}</span>
          </button>
          <span class="cm-hint">
            {{ mode === "fast" ? "Fast: simbol & referensi" : (mode === "deep" ? "Deep: audit arsitektur penuh" : "Balanced: callers/callees & investigasi") }}
          </span>
        </div>
      </template>

      <div class="consultant-body" :class="{ 'embedded-view': embedded }">
        <div class="consultant-chat">
          <div class="consultant-messages" ref="scroller">
        <div v-for="(msg, i) in messages" :key="i" class="cmsg" :class="msg.role">
          <span class="crole">{{ msg.role === "assistant" ? "AEGIS Ask" : "You" }}</span>
          <div v-if="msg.role === 'user' && msg.images && msg.images.length" class="cmsg-images">
            <img
              v-for="(src, ii) in msg.images"
              :key="ii"
              :src="src"
              class="cmsg-thumb"
              alt="attachment"
            />
          </div>
          <div v-if="msg.role === 'user'" class="ctext">
            <span class="ctext-body">{{ msg.text }}</span>
            <!-- Tombol copy: DI DALAM card pesan, sudut kiri bawah bubble. -->
            <div class="cmsg-actions">
              <button
                type="button"
                class="copy-btn"
                :class="{ copied: copiedIndex === i }"
                :title="copiedIndex === i ? 'Copied' : 'Copy message'"
                :aria-label="copiedIndex === i ? 'Copied' : 'Copy message'"
                @click="copyMessage(msg, i)"
              >
                <svg v-if="copiedIndex === i" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
                <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                <span class="copy-label">{{ copiedIndex === i ? "Copied" : "Copy" }}</span>
              </button>
            </div>
          </div>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <!-- Thinking Block (Reasoning Process) -->
          <div v-if="msg.reasoning" class="consultant-thinking-wrapper" style="margin-bottom: 8px;">
            <AppThinkingBlock
              title="Thinking Process"
              :collapsed="true"
            >
              <div class="thinking-content-markdown" v-html="renderMarkdown(msg.reasoning)"></div>
            </AppThinkingBlock>
          </div>

          <!-- eslint-disable-next-line vue/no-v-html -->
          <div
            v-if="msg.role === 'assistant' && assistantText(msg)"
            class="consultant-md md"
            :class="{ failed: msg.failed }"
          >
            <div class="md-body" v-html="renderMarkdown(assistantText(msg))"></div>
            <!-- Tombol copy: DI DALAM card pesan, sudut kiri bawah bubble. -->
            <div class="cmsg-actions">
              <button
                type="button"
                class="copy-btn"
                :class="{ copied: copiedIndex === i }"
                :title="copiedIndex === i ? 'Copied' : 'Copy message'"
                :aria-label="copiedIndex === i ? 'Copied' : 'Copy message'"
                @click="copyMessage(msg, i)"
              >
                <svg v-if="copiedIndex === i" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
                <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                <span class="copy-label">{{ copiedIndex === i ? "Copied" : "Copy" }}</span>
              </button>
              <button
                v-if="extractFirstCodeBlock(assistantText(msg))"
                type="button"
                class="apply-btn"
                title="Apply code to open editor"
                @click="applyCodeToEditor(msg)"
              >
                Apply to Editor
              </button>
            </div>
          </div>
          <!-- Agent Execution Details for Agent Turns -->
          <div v-if="msg.role === 'assistant' && msg.execution" class="consultant-execution-box">
            <div class="cmsg-exec-header">
              <span class="cmsg-exec-badge" :class="msg.execution.status">
                Agent Task: {{ msg.execution.status }}
              </span>
              <span v-if="msg.execution.task_id" class="cmsg-exec-id">
                #{{ String(msg.execution.task_id).slice(0, 8) }}
              </span>
            </div>
            <div v-if="msg.execution.changes && msg.execution.changes.length" class="cmsg-exec-changes">
              <span class="cmsg-changes-label">Changes:</span>
              <span v-for="(ch, ci) in msg.execution.changes" :key="ci" class="cmsg-change-chip">
                {{ ch.path || ch.file || ch }}
              </span>
            </div>
          </div>
          <div v-if="msg.role === 'assistant' && msg.tools && msg.tools.length" class="consultant-tools">
            <span v-for="(t, ti) in msg.tools" :key="ti" class="consultant-tool" :class="t.success ? 'ok' : 'err'">
              {{ t.success ? "✓" : "✗" }} {{ t.tool }}<template v-if="t.target"> {{ t.target }}</template>
            </span>
          </div>
          <!-- Task Proposal mengalir sebagai bagian dari message flow: ia
               dirender inline di dalam pesan yang menghasilkannya (bukan selalu
               di akhir container), sehingga balasan Consultant berikutnya
               muncul DI BAWAH card dan card ikut naik seperti bubble lain.
               Card tetap berada di dalam area percakapan yang scrollable.
               Card memiliki pemilihan RUNNER (Provider/Model) SENDIRI yang
               dipakai saat Run Task — terpisah dari dropdown header yang
               mengontrol CHAT. Card: title -> body -> footer (runner + tombol
               Run Task) -> aksi Copy. -->
          <div v-if="msg.role === 'assistant' && msg.taskProposal" class="consultant-proposal">
            <div class="cp-head">
              <span class="cp-title">Task Proposal</span>
            </div>
            <pre class="cp-body">{{ msg.taskProposal }}</pre>
            <!-- Footer card: pilihan runner (Provider + Model) di kiri, tombol
                 Run Task di kanan. Dipakai untuk MENJALANKAN task ini; pilihan
                 header (chat) TIDAK berubah. Hanya card MILIK task yang masih
                 aktif yang di-disable (anti double-submit PER PROPOSAL);
                 proposal LAIN tetap bisa di-enqueue meski Agent sedang RUNNING. -->
            <div class="cp-foot">
              <div v-if="!embedded" class="cp-runner">
                <label class="cp-select">
                  <span class="cs-label">Provider</span>
                  <select
                    class="input-a"
                    :value="proposalProviderInstanceId"
                    :disabled="isProposalBusy(i)"
                    @change="onProposalProviderChange"
                  >
                    <option v-if="!providerOptions.length" value="">No provider instance</option>
                    <option v-for="p in providerOptions" :key="p.id" :value="p.id">
                      {{ providerLabel(p) }}
                    </option>
                  </select>
                </label>
                <label class="cp-select">
                  <span class="cs-label">Model</span>
                  <select
                    class="input-a"
                    :value="proposalModelId"
                    :disabled="isProposalBusy(i) || !proposalProviderInstanceId"
                    @change="onProposalModelChange"
                  >
                    <option v-if="!proposalModelOptions.length" value="">No model</option>
                    <option v-for="m in proposalModelOptions" :key="m.id" :value="m.id">
                      {{ m.model_name }}
                    </option>
                  </select>
                </label>
                <label class="cp-select">
                  <span class="cs-label">Execution</span>
                  <select
                    class="input-a"
                    :value="proposalExecutionMode"
                    :disabled="isProposalBusy(i)"
                    @change="proposalExecutionMode = $event.target.value"
                  >
                    <option value="queue">Queue</option>
                    <option value="parallel">Parallel</option>
                  </select>
                </label>
              </div>
              <div v-else class="cp-runner-embedded">
                <span class="badge-dot">●</span>
                <span class="badge-brand">Aegis</span>
                <span v-if="displayModel || displayProvider" class="badge-sep">·</span>
                <span v-if="displayModel || displayProvider" class="badge-model">{{ displayModel || displayProvider }}</span>
              </div>
              <button class="run-task-btn" type="button" :disabled="isProposalBusy(i)" @click="runTask(msg.taskProposal, i)">
                <svg v-if="!isProposalBusy(i)" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
                {{ isProposalBusy(i) ? "Running…" : "Run Task" }}
              </button>
            </div>
            <!-- Tombol Copy di kiri-bawah card (pola .cmsg-actions/.copy-btn
                 sama dengan bubble chat). Isi = teks proposal yang tampil. -->
            <div class="cmsg-actions cp-actions">
              <button
                type="button"
                class="copy-btn"
                :class="{ copied: proposalCopied }"
                :title="proposalCopied ? 'Copied' : 'Copy task proposal'"
                :aria-label="proposalCopied ? 'Copied' : 'Copy task proposal'"
                @click="copyProposal(msg.taskProposal)"
              >
                <svg v-if="proposalCopied" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
                <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                <span class="copy-label">{{ proposalCopied ? "Copied" : "Copy" }}</span>
              </button>
            </div>
          </div>
        </div>

        <div v-if="sending" class="consultant-thinking">{{ mode === 'quick' ? 'AEGIS is analyzing…' : 'AEGIS is investigating…' }}</div>
      </div>

      <div v-if="error" class="wb-error">{{ error }}</div>

      <!-- Integrated Chat Card (Embedded in Right Drawer - matches Agents tab) -->
      <div v-if="embedded" class="drawer-chat-card" style="position: relative; overflow: visible;">
        <PromptAutocompletePopover
          :visible="popoverVisible"
          :type="popoverType"
          :items="popoverItems"
          :selected-index="popoverIndex"
          placement="top"
          @select="onSelectSuggestion"
          @close="closePopover"
        />
        <div class="chat-card-header">
          <div class="chat-provider-controls" :title="`Provider: ${displayProvider} · Model: ${displayModel}`">
            <span class="badge-dot">●</span>
            <select
              class="chat-header-select"
              :value="providerInstanceId"
              title="Select Provider"
              aria-label="Select Provider"
              :disabled="sending"
              @change="onProviderChange"
            >
              <option v-if="!providerOptions.length" value="">{{ displayProvider || "No provider" }}</option>
              <option v-for="p in providerOptions" :key="p.id" :value="p.id">
                {{ p.name }}
              </option>
            </select>
            <span class="chat-sep">/</span>
            <select
              class="chat-header-select"
              :value="modelId"
              title="Select Model"
              aria-label="Select Model"
              :disabled="sending || !providerInstanceId"
              @change="onModelChange"
            >
              <option v-if="!modelOptions.length" value="">{{ displayModel || "No model" }}</option>
              <option v-for="m in modelOptions" :key="m.id" :value="m.id">
                {{ m.model_name }}
              </option>
            </select>
          </div>

          <div class="chat-card-header-actions">
            <!-- + New chat icon-only button -->
            <button
              type="button"
              class="chat-icon-btn consultant-new-btn"
              title="New conversation"
              aria-label="New conversation"
              @click="startNewSession"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
            </button>
            <!-- Rename conversation button -->
            <button
              type="button"
              class="chat-icon-btn chat-rename-btn"
              :title="`Rename conversation: ${activeSessionTitle}`"
              aria-label="Rename conversation"
              @click="promptRenameCurrentSession"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>
            </button>

            <!-- Settings icon -->
            <button
              type="button"
              class="chat-icon-btn chat-settings-btn"
              title="Configure Provider in Settings"
              aria-label="Configure Provider"
              @click="$emit('open-settings', 'providers')"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </button>
          </div>
        </div>

        <div class="chat-card-body">
          <div v-if="activeTabPath" class="chat-active-file-chip" :title="`Berkas aktif: ${activeTabPath}`">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
              <polyline points="13 2 13 9 20 9"></polyline>
            </svg>
            <span class="active-file-chip-label">Active: {{ activeTabPath }}</span>
          </div>
          <textarea
            ref="composer"
            v-model="input"
            class="chat-prompt-textarea"
            rows="2"
            :placeholder="inputPlaceholder"
            :disabled="sending"
            @input="onComposerInput"
            @keydown="onKeydown"
            @click="onComposerInput"
          ></textarea>
        </div>

        <div class="chat-card-actions">
          <div class="chat-card-actions-left">
            <!-- Mode dropdown: 'Quick' / 'Deep' as compact select on the left of Send -->
            <select
              v-model="mode"
              class="consultant-mode-select"
              title="AEGIS Mode: Quick or Deep"
              aria-label="AEGIS Mode"
              :disabled="sending"
            >
              <option value="fast">Fast</option>
              <option value="balanced">Balanced</option>
              <option value="deep">Deep</option>
            </select>
          </div>

          <div class="chat-card-actions-right">
            <button
              type="button"
              class="chat-send-btn"
              :disabled="sending || !input.trim()"
              title="Send prompt (Enter)"
              aria-label="Send Message"
              @click="send"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
              <span>Send</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Standalone Modal Foot (When !embedded) -->
      <div v-else class="consultant-foot">
        <!-- Preview gambar terlampir (belum dikirim). -->
        <div v-if="attachments.length" class="attach-strip">
          <div v-for="(a, ai) in attachments" :key="ai" class="attach-item">
            <img :src="a.dataUrl" class="attach-thumb" :alt="a.name" />
            <button
              type="button"
              class="attach-remove"
              title="Remove image"
              @click="removeAttachment(ai)"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
            </button>
          </div>
        </div>
        <div class="attach-row" style="position: relative; overflow: visible;">
          <input
            ref="fileInput"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            class="attach-input"
            @change="onFilesPicked"
          />
          <button
            type="button"
            class="attach-btn"
            title="Attach image (JPEG/PNG/WebP)"
            :disabled="sending"
            @click="triggerAttach"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
          </button>
          <div v-if="activeTabPath" class="chat-active-file-chip standalone-chip" :title="`Berkas aktif: ${activeTabPath}`">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
              <polyline points="13 2 13 9 20 9"></polyline>
            </svg>
            <span class="active-file-chip-label">Active: {{ activeTabPath }}</span>
          </div>
          <textarea
            ref="composer"
            v-model="input"
            class="input-a"
            rows="1"
            :placeholder="inputPlaceholder"
            :disabled="sending"
            @input="onComposerInput"
            @keydown="onKeydown"
            @click="onComposerInput"
          ></textarea>
          <PromptAutocompletePopover
            :visible="popoverVisible"
            :type="popoverType"
            :items="popoverItems"
            :selected-index="popoverIndex"
            placement="top"
            @select="onSelectSuggestion"
            @close="closePopover"
          />
          <button class="send-btn" type="button" title="Send" :disabled="sending || (!input.trim() && !attachments.length)" @click="send">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
          </button>
        </div>
      </div>
        </div><!-- /consultant-chat -->

        <!-- Right sidebar: Sessions (default) | Tasks: ONLY rendered when !embedded -->
        <aside
          v-if="!embedded"
          class="consultant-sidebar"
          aria-label="Consultant sidebar"
        >
          <div class="consultant-tabs" role="tablist" aria-label="Consultant sidebar views">
            <button
              type="button"
              class="consultant-tab"
              :class="{ active: activeSideTab === 'sessions' }"
              role="tab"
              :aria-selected="activeSideTab === 'sessions'"
              @click="activeSideTab = 'sessions'"
            >Sessions</button>
            <span class="consultant-tab-divider" aria-hidden="true">|</span>
            <button
              type="button"
              class="consultant-tab"
              :class="{ active: activeSideTab === 'tasks' }"
              role="tab"
              :aria-selected="activeSideTab === 'tasks'"
              @click="activeSideTab = 'tasks'"
            >Tasks</button>
          </div>
          <div v-if="activeSideTab === 'sessions'" class="consultant-sessions" role="tabpanel">
            <div class="consultant-sessions-header">
              <span class="cs-hdr-title">All Conversations</span>
              <button
                type="button"
                class="cs-new-btn"
                title="Create new session"
                :disabled="sessionsLoading || sending"
                @click="createNewSession"
              >
                + New
              </button>
            </div>

            <div v-if="sessionsLoading && !sessions.length" class="consultant-session-loading">
              Loading sessions…
            </div>

            <div v-else-if="!sessions.length" class="consultant-session-empty">
              <span class="session-icon" aria-hidden="true">◌</span>
              <span>No saved sessions</span>
              <small>Start chatting to create a session</small>
            </div>

            <div v-else class="consultant-session-list">
              <div
                v-for="s in sessions"
                :key="s.session_id"
                class="consultant-session-item"
                :class="{ active: s.session_id === sessionId, disabled: sending }"
                @click="!sending && switchSession(s.session_id)"
              >
                <div class="cs-item-main">
                  <template v-if="renamingSessionId === s.session_id">
                    <input
                      v-model="renameInput"
                      class="cs-rename-input"
                      type="text"
                      @keydown.enter.stop="saveSessionRename(s.session_id)"
                      @keydown.esc.stop="renamingSessionId = null"
                      @blur="saveSessionRename(s.session_id)"
                      @click.stop
                    />
                  </template>
                  <template v-else>
                    <div class="cs-item-title" :title="s.title || 'New Chat'">
                      {{ s.title || "New Chat" }}
                    </div>
                    <div class="cs-item-meta">
                      <span class="cs-item-time">{{ formatSessionTime(s.updated_at) }}</span>
                      <span v-if="s.turn_count" class="cs-item-turns">{{ s.turn_count }} turns</span>
                    </div>
                  </template>
                </div>
                <button
                  type="button"
                  class="cs-item-edit"
                  title="Rename session"
                  @click.stop="startSessionRename(s)"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>
                </button>
                <button
                  type="button"
                  class="cs-item-del"
                  title="Delete session"
                  @click="removeSession(s.session_id, $event)"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
                </button>
              </div>
            </div>
          </div>
          <QueuePanel
            v-else
            class="consultant-queue"
            :project-id="projectId || null"
            :refresh-key="queueRefreshKey"
            @stop-task="$emit('stop-task', $event)"
            @view-task="$emit('view-task', $event)"
          />
        </aside>
      </div><!-- /consultant-body -->
    </div>
  </div>
</template>
