<script setup>
// Agent Activity (compact activity feed).
//
// Semua aktivitas satu Task ditampilkan dalam SATU alur chronological, tetapi
// tiap aktivitas adalah BARIS RINGKAS (bukan blok besar):
//
//   [05:38:26] Reading source   src/core         10 files      completed  ▸ detail
//   [05:38:29] Searching code   needle           13 matches    completed  ▸ detail
//   [05:38:38] Exploring files  .                4 directories completed  ▸ detail
//   [05:38:36] Running command   npm run build                  completed  ▸ detail
//   [05:39:25] Task completed
//
// Dua lapisan informasi (pola CLI/agent modern):
//   1. Baris ringkas   : waktu + ikon + aksi manusiawi + scope + hasil + status
//   2. Detail opsional : daftar file/dir + event mentah yang SUDAH ADA
//                        (TOOL / RESULT / OBSERVATION) + report final
//
// Grouping: aktivitas berurutan dari tool yang sama (mis. 10x read_file)
// digabung menjadi SATU baris. Grouping dilakukan murni di layer tampilan ini;
// sumber event (SSE live #51 atau Activity API/persistent log) tidak diubah dan
// isi raw event tidak dimodifikasi.
//
// Ini BUKAN terminal mentah: observation ditampilkan sebagai ringkasan angka
// (jumlah file/baris/match), bukan dump JSON/file panjang.
//
// Agent Report final (task_completed.data.result) ditampilkan UTUH di alur ini
// tanpa truncate/ellipsis, memakai Markdown renderer yang sama dengan
// ReportViewer (apps/frontend/src/markdown.js). Teks report asli juga dipakai
// tombol Copy kecil (pojok kiri bawah area report) yang memakai pola
// .cmsg-actions/.copy-btn yang sama dengan Consultant Chat.
import { computed, nextTick, ref, watch } from "vue";
import { renderMarkdown } from "../../markdown.js";
import AppThinkingBlock from "../ui/AppThinkingBlock.vue";
import { buildAgentActivityCopy } from "../../activityCopy.js";
const props = defineProps({
  events: { type: Array, default: () => [] },
  status: { type: String, default: "idle" },
  // Live "Agent reasoning." indicator.
  isReasoning: { type: Boolean, default: false },
  // Lifecycle milestone steps: [{ label, state: 'done'|'active'|'pending' }]
  lifecycleSteps: { type: Array, default: () => [] },
  // Current phase string — used to contextualise milestone ordering.
  activityPhase: { type: String, default: "" },
});

const emit = defineEmits(["submit-reply"]);

const questionReplies = ref({});

function handleAnswerQuestion(item, replyText) {
  if (!replyText || !replyText.trim()) return;
  item.answered = true;
  item.answerText = replyText.trim();
  emit("submit-reply", replyText.trim());
}

const scroller = ref(null);

async function scrollToLatest() {
  await nextTick();
  const el = scroller.value;
  if (el) el.scrollTop = el.scrollHeight;
}

// Waktu event -> HH:MM:SS (mendukung epoch detik/ms dan ISO string).
function formatTime(raw) {
  if (raw == null) return "";
  if (typeof raw === "number") {
    const d = new Date(raw < 1e12 ? raw * 1000 : raw);
    return Number.isNaN(d.getTime()) ? "" : d.toTimeString().slice(0, 8);
  }
  const d = new Date(raw);
  return Number.isNaN(d.getTime()) ? "" : d.toTimeString().slice(0, 8);
}

// Normalisasi dua bentuk event ke { type, data, ts }.
function normalize(e) {
  return {
    type: e.event_type || e.event || "",
    data: e.payload || e.data || {},
    ts: formatTime(e.timestamp),
  };
}

// ---------------------------------------------------------------------------
// Label manusiawi per tool (menggantikan nama tool mentah di baris utama).
// ---------------------------------------------------------------------------
const TOOL_META = {
  list_files: { icon: "folder", verb: "Exploring files" },
  read_file: { icon: "book", verb: "Reading source" },
  search_code: { icon: "search", verb: "Searching code" },
  write_file: { icon: "edit", verb: "Editing files" },
  edit_file: { icon: "edit", verb: "Editing files" },
  run_command: { icon: "play", verb: "Running command" },
  hybrid_search: { icon: "search", verb: "Hybrid search" },
  semantic_search: { icon: "search", verb: "Semantic search" },
  atlas_query: { icon: "target", verb: "Querying Code Atlas" },
  rig_query: { icon: "target", verb: "Querying RIG graph" },
};


// Ikon SVG terpadu (gaya Lucide, stroke currentColor) pengganti emotikon.
const ICON_PATHS = {
  folder: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
  book: '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
  search: '<circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  tool: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94z"/>',
  check: '<path d="M20 6L9 17l-5-5"/>',
  x: '<path d="M18 6L6 18M6 6l12 12"/>',
  warn: '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  brain: '<circle cx="12" cy="12" r="9"/><path d="M9 10h.01M15 10h.01M9 15c1.5 1 4.5 1 6 0"/>',
  zap: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
  target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
};

function iconSvg(name) {
  return ICON_PATHS[name] || ICON_PATHS.tool;
}

// Label event mentah (dipakai di layer detail) — mempertahankan istilah yang
// sudah dipakai timeline Aegis.
const RAW_LABEL = {
  tool_called: "TOOL",
  tool_completed: "RESULT",
  observation_received: "OBSERVATION",
};

function rawLabel(type) {
  return RAW_LABEL[type] || "EVENT";
}

function rawClass(type) {
  if (type === "tool_called") return "tool";
  if (type === "tool_completed") return "result";
  if (type === "observation_received") return "observation";
  return "status";
}

function uniqueList(list) {
  const out = [];
  (list || []).forEach((value) => {
    const text = value == null ? "" : String(value);
    if (text && !out.includes(text)) out.push(text);
  });
  return out;
}

function shortName(path) {
  const text = String(path == null ? "" : path).replace(/[\\/]+$/, "");
  const parts = text.replace(/[\\/]+/g, "/").split("/");
  return parts[parts.length - 1] || text;
}

function stamp(ts) {
  return ts ? `[${ts}]` : "";
}

// Konten observation bisa berupa objek (jalur tool loop) atau string JSON
// (jalur payload tool). Parse aman, tanpa melempar error.
function asObject(content) {
  if (content && typeof content === "object") return content;
  if (typeof content === "string") {
    const text = content.trim();
    if (text.startsWith("{") || text.startsWith("[")) {
      try {
        const parsed = JSON.parse(text);
        if (parsed && typeof parsed === "object") return parsed;
      } catch (e) {
        return null;
      }
    }
  }
  return null;
}

// Ukur hasil observation: jumlah file/dir (list_files) atau match (search_code).
function measure(tool, content) {
  const obj = asObject(content);
  if (!obj) return null;
  if (tool === "list_files" && Array.isArray(obj.entries)) {
    let files = 0;
    let dirs = 0;
    obj.entries.forEach((entry) => {
      if (entry && entry.type === "dir") dirs += 1;
      else files += 1;
    });
    return { files, dirs };
  }
  if (tool === "search_code" && typeof obj.count === "number") {
    return { matches: obj.count };
  }
  if ((tool === "hybrid_search" || tool === "semantic_search") && typeof obj.total_results === "number") {
    return { matches: obj.total_results };
  }
  if (tool === "atlas_query" && typeof obj.returned === "number") {
    return { matches: obj.returned };
  }
  if (typeof obj.total_lines === "number") return { lines: obj.total_lines };
  return null;
}


function isRepeatContent(content) {
  const obj = asObject(content);
  return Boolean(obj && (obj.already_available || obj.already_searched));
}

// ---------------------------------------------------------------------------
// Pengelompokan event (murni tampilan) -> daftar unit tool.
// ---------------------------------------------------------------------------
function buildUnits(events) {
  const units = [];
  const lastByTool = new Map();
  const openByTool = new Map();
  let seq = 0;

  events.forEach((raw, index) => {
    const e = normalize(raw);
    const type = e.type;
    if (type !== "tool_called" && type !== "tool_completed" && type !== "observation_received") {
      return;
    }
    const d = e.data || {};
    const tool = String(d.tool || "");

    let unit = null;
    if (type !== "tool_called") {
      unit = openByTool.get(tool) || lastByTool.get(tool) || null;
    }
    if (!unit) {
      unit = {
        key: `tool-${tool}-${seq++}`,
        tool,
        at: index,
        atEnd: index,
        ts: e.ts,
        events: [],
        targets: [],
        called: 0,
        done: 0,
        success: true,
        error: "",
        measures: [],
        repeated: false,
      };
      units.push(unit);
    }
    unit.atEnd = index;
    unit.ts = unit.ts || e.ts;
    unit.events.push({ type, ts: e.ts, data: d });
    lastByTool.set(tool, unit);

    if (type === "tool_called") {
      unit.called += 1;
      if (d.target) unit.targets.push(String(d.target));
      openByTool.set(tool, unit);
      return;
    }
    if (type === "tool_completed") {
      unit.done += 1;
      if (d.target) unit.targets.push(String(d.target));
      if (d.success === false) {
        unit.success = false;
        if (d.error) unit.error = String(d.error);
      }
      return;
    }
    // observation_received: hasil akhir satu panggilan tool.
    if (d.success === false) unit.success = false;
    const measured = measure(tool, d.content);
    if (measured) unit.measures.push(measured);
    if (isRepeatContent(d.content)) unit.repeated = true;
    openByTool.delete(tool);
  });

  return units;
}

// Gabungkan unit BERURUTAN dari tool yang sama menjadi satu baris aktivitas,
// kecuali ada event non-tool (mis. commentary) di antaranya.
function mergeUnits(units, nonToolIdx) {
  const groups = [];
  units.forEach((u) => {
    const last = groups[groups.length - 1];
    const adjacent =
      Boolean(last) &&
      last.tool === u.tool &&
      !nonToolIdx.some((idx) => idx > last.atEnd && idx < u.at);
    if (adjacent) {
      last.events = last.events.concat(u.events);
      last.targets = last.targets.concat(u.targets);
      last.measures = last.measures.concat(u.measures);
      last.called += u.called;
      last.done += u.done;
      last.atEnd = Math.max(last.atEnd, u.atEnd);
      if (!u.success) {
        last.success = false;
        last.error = last.error || u.error;
      }
      if (u.repeated) last.repeated = true;
      return;
    }
    groups.push({
      key: u.key,
      tool: u.tool,
      at: u.at,
      atEnd: u.atEnd,
      ts: u.ts,
      events: u.events.slice(),
      targets: u.targets.slice(),
      measures: u.measures.slice(),
      called: u.called,
      done: u.done,
      success: u.success,
      error: u.error,
      repeated: u.repeated,
    });
  });
  return groups;
}

// "4 files", "4 directories", "3 files, 1 directory", "13 matches".
function countLabel(group) {
  if (group.tool === "list_files") {
    let files = 0;
    let dirs = 0;
    group.measures.forEach((m) => {
      files += m.files || 0;
      dirs += m.dirs || 0;
    });
    const parts = [];
    if (files) parts.push(`${files} file${files === 1 ? "" : "s"}`);
    if (dirs) parts.push(`${dirs} director${dirs === 1 ? "y" : "ies"}`);
    return parts.join(", ");
  }
  if (
    group.tool === "search_code" ||
    group.tool === "hybrid_search" ||
    group.tool === "semantic_search" ||
    group.tool === "atlas_query"
  ) {
    const total = group.measures.reduce((acc, m) => acc + (m.matches || 0), 0);
    return total ? `${total} match${total === 1 ? "" : "es"}` : "";
  }
  if (group.tool === "run_command") {
    const total = group.measures.length || group.called;
    return total > 1 ? `${total} commands` : "";
  }
  const total = uniqueList(group.targets).length || group.called;
  return total > 1 ? `${total} files` : "";
}

// Scope ringkas (direktori bersama, file tunggal, query, atau command).
function scopeLabel(tool, targets) {
  if (!targets.length) return "";
  if (
    tool === "search_code" ||
    tool === "run_command" ||
    tool === "hybrid_search" ||
    tool === "semantic_search" ||
    tool === "atlas_query" ||
    tool === "rig_query"
  ) return targets[0];

  if (targets.length === 1) return targets[0];
  const dirs = uniqueList(
    targets.map((target) => {
      const parts = String(target).replace(/[\\/]+/g, "/").split("/");
      parts.pop();
      return parts.join("/");
    })
  );
  return dirs.length === 1 ? dirs[0] : "";
}

function describeTool(group, status) {
  const meta = TOOL_META[group.tool] || { icon: "tool", verb: group.tool || "Tool" };
  const targets = uniqueList(group.targets);
  const failed = !group.success;
  const running = !failed && group.done === 0 && status === "running";

  let state = "ok";
  let stateText = "completed";
  let stateIcon = "check";
  if (failed) {
    state = "err";
    stateText = "failed";
    stateIcon = "x";
  } else if (running) {
    state = "run";
    stateText = "running";
    stateIcon = "clock";
  } else if (group.repeated) {
    state = "warn";
    stateText = "repeated";
    stateIcon = "warn";
  }

  return {
    key: group.key,
    at: group.at,
    ts: group.ts,
    kind: "tool",
    icon: meta.icon,
    title: meta.verb,
    scope: scopeLabel(group.tool, targets),
    count: countLabel(group),
    state,
    stateText,
    stateIcon,
    error: failed ? group.error : "",
    files: targets.map(shortName),
    events: group.events,
  };
}

// Dispatcher terstruktur untuk event non-tool
const EVENT_DESCRIBERS = {
  agent_commentary: (d, base, index) => {
    const text = String(d.text || "").trim();
    if (!text) return null;
    return {
      ...base,
      key: `agent-${index}`,
      kind: "reasoning",
      icon: "brain",
      title: "Reasoning",
      detailText: text,
    };
  },
  warning: (d, base, index) => {
    const msg = String(d.message || d.text || d.warning || "").trim();
    if (!msg) return null;
    return {
      ...base,
      key: `warn-${index}`,
      kind: "notice",
      icon: "warn",
      title: "Warning",
      scope: d.target || d.tool || "",
      detailText: msg,
    };
  },
  agent_reasoning_delta: (d, base, index) => {
    const delta = String(d.delta || d.reasoning || "").trim();
    if (!delta) return null;
    return {
      ...base,
      key: `reasoning-delta-${index}`,
      kind: "reasoning",
      icon: "brain",
      title: "Reasoning",
      detailText: delta,
    };
  },
  provider_response: (d, base, index) => {
    if (!d.error) return null;
    const pName = d.provider ? (d.provider.charAt(0).toUpperCase() + d.provider.slice(1)) : "Provider";
    return {
      ...base,
      key: `prov-err-${index}`,
      kind: "notice",
      icon: "x",
      title: `${pName} error`,
      scope: d.model || "",
      error: String(d.error),
      detailText: `[PROVIDER ERROR]\nProvider: ${d.provider || "Unknown"}\nModel: ${d.model || "-"}\nError: ${d.error}`,
    };
  },
  task_started: (d, base, index) => ({
    ...base,
    key: `status-${index}`,
    kind: "status",
    icon: "play",
    title: "Task started",
  }),
  task_completed: (d, base, index) => {
    const report = typeof d.result === "string" ? d.result : "";
    return {
      ...base,
      key: `status-${index}`,
      kind: "status",
      icon: "check",
      title: "Task completed",
      reportText: report,
      reportHtml: report ? renderMarkdown(report) : "",
    };
  },
  task_failed: (d, base, index) => {
    const errText = String(d.error || d.reason || d.message || "").trim();
    return {
      ...base,
      key: `status-${index}`,
      kind: "status",
      icon: "x",
      title: "Task failed",
      error: errText || null,
      detailText: errText ? `[FAILURE]\n${errText}` : null,
    };
  },
  task_cancelled: (d, base, index) => ({
    ...base,
    key: `status-${index}`,
    kind: "status",
    icon: "warn",
    title: "Task cancelled",
  }),
  validation_started: (d, base, index) => ({
    ...base,
    key: `notice-${index}`,
    kind: "notice",
    icon: "check",
    title: "Validating",
  }),
  validation_completed: (d, base, index) => ({
    ...base,
    key: `notice-${index}`,
    kind: "notice",
    icon: d.success === false ? "x" : "check",
    title: d.success === false ? "Validation failed" : "Validation completed",
  }),
  recovery_started: (d, base, index) => ({
    ...base,
    key: `notice-${index}`,
    kind: "notice",
    icon: "warn",
    title: "Recovery started",
  }),
  recovery_completed: (d, base, index) => ({
    ...base,
    key: `notice-${index}`,
    kind: "notice",
    icon: "check",
    title: "Recovery completed",
  }),
  policy_applied: () => null,
  policy_escalated: () => null,
  question_asked: (d, base, index) => ({
    ...base,
    key: `question-${d.question_id || index}`,
    kind: "question",
    icon: "brain",
    title: "Question for user",
    questionText: d.question || d.text || d.message || "",
    options: Array.isArray(d.options) ? d.options : [],
    placeholder: d.placeholder || "",
    answered: Boolean(d.answered),
    answerText: d.answer || "",
    questionId: d.question_id || `q-${index}`,
  }),
  agent_question: (d, base, index) => ({
    ...base,
    key: `question-${d.question_id || index}`,
    kind: "question",
    icon: "brain",
    title: "Agent Question",
    questionText: d.question || d.text || d.prompt || d.message || "",
    options: Array.isArray(d.options) ? d.options : [],
    placeholder: d.placeholder || "",
    answered: Boolean(d.answered),
    answerText: d.answer || "",
    questionId: d.question_id || `q-${index}`,
  }),
  clarification_requested: (d, base, index) => ({
    ...base,
    key: `clarification-${d.id || index}`,
    kind: "question",
    icon: "brain",
    title: "Clarification Needed",
    questionText: d.prompt || d.question || d.message || "",
    options: Array.isArray(d.options) ? d.options : [],
    placeholder: d.placeholder || "",
    answered: Boolean(d.answered),
    answerText: d.answer || "",
    questionId: d.id || `c-${index}`,
  }),
};

// Aktivitas non-tool -> baris status/notice ringkas via dispatcher
function describeEvent(e, index) {
  const d = e.data || {};
  const base = { at: index, ts: e.ts, events: [] };
  const handler = EVENT_DESCRIBERS[e.type];
  return handler ? handler(d, base, index) : null;
}
// Timeline chronological: lifecycle milestones (done → active → events → pending)
// + merged tool groups + non-tool events, sorted by virtual position.
const timeline = computed(() => {
  const events = props.events || [];
  const nonToolIdx = [];

  events.forEach((raw, index) => {
    const type = (raw && (raw.event_type || raw.event)) || "";
    if (type !== "tool_called" && type !== "tool_completed" && type !== "observation_received") {
      nonToolIdx.push(index);
    }
  });

  const items = [];

  mergeUnits(buildUnits(events), nonToolIdx).forEach((group) => {
    items.push(describeTool(group, props.status));
  });

  events.forEach((raw, index) => {
    const item = describeEvent(normalize(raw), index);
    if (item) items.push(item);
  });

  items.sort((a, b) => a.at - b.at);

  const mergedItems = [];
  for (const item of items) {
    const prev = mergedItems[mergedItems.length - 1];
    if (
      prev &&
      prev.kind === "reasoning" &&
      item.kind === "reasoning" &&
      item.key?.startsWith("reasoning-delta-") &&
      prev.key?.startsWith("reasoning-delta-")
    ) {
      prev.detailText += item.detailText;
    } else {
      mergedItems.push({ ...item });
    }
  }
  // Inject lifecycle milestones: done steps first, active just before events,
  // pending steps trail at the end.
  const steps = props.lifecycleSteps || [];
  if (steps.length) {
    const doneSteps = steps.filter((s) => s.state === "done");
    const activeStep = steps.find((s) => s.state === "active");
    const pendingSteps = steps.filter((s) => s.state !== "done" && s.state !== "active");
    const milestones = [];

    doneSteps.forEach((step, i) => {
      milestones.push({
        key: `ms-done-${i}`,
        at: -(steps.length + 2 - i),
        kind: "milestone",
        title: step.label,
        state: "done",
      });
    });
    if (activeStep) {
      milestones.push({
        key: "ms-active",
        at: -1,
        kind: "milestone",
        title: activeStep.label,
        state: "active",
      });
    }
    pendingSteps.forEach((step, i) => {
      milestones.push({
        key: `ms-pending-${i}`,
        at: events.length + 1 + i,
        kind: "milestone",
        title: step.label,
        state: "pending",
      });
    });

    return [...mergedItems, ...milestones].sort((a, b) => a.at - b.at);
  }

  return mergedItems;
});

const empty = computed(() => !timeline.value.length);

// Aktivitas berulang: target yang dibaca lebih dari sekali.
const repeats = computed(() => {
  const counts = new Map();
  (props.events || []).forEach((raw) => {
    const e = normalize(raw);
    if (e.type !== "observation_received") return;
    const d = e.data || {};
    if (String(d.tool || "") !== "read_file") return;
    const obj = asObject(d.content);
    const path = (obj && obj.path) || d.target || "";
    if (!path) return;
    const key = String(path);
    counts.set(key, (counts.get(key) || 0) + 1);
  });
  const out = [];
  counts.forEach((count, path) => {
    if (count > 1) out.push({ name: shortName(path), path, count });
  });
  return out.sort((a, b) => b.count - a.count);
});

// --- Detail opsional (buka/tutup per baris, state lokal di komponen) --------
const expanded = ref({});

function isOpen(key) {
  return expanded.value[key] === true;
}

function toggle(key) {
  expanded.value = { ...expanded.value, [key]: !expanded.value[key] };
}

function hasDetail(item) {
  return Boolean(
    (item.detailText && item.detailText.length) ||
      (item.files && item.files.length) ||
      (item.events && item.events.length)
  );
}

// Satu baris teks ringkas (tanpa newline ganda) dengan batas panjang.
function oneLine(value, max) {
  const text = String(value == null ? "" : value).replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.substring(0, max)}…` : text;
}

function safeJson(value) {
  try {
    return JSON.stringify(value);
  } catch (e) {
    return String(value);
  }
}

// Ringkasan isi observation (angka/field kunci) — BUKAN dump isi file.
function rawPreview(content) {
  if (content == null) return "";
  if (typeof content === "string") return oneLine(content, 300);
  const obj = asObject(content) || content;
  const parts = [];
  if (typeof obj.count === "number") {
    parts.push(`${obj.count} ${obj.query ? "matches" : "items"}`);
  }
  if (typeof obj.total_lines === "number") parts.push(`${obj.total_lines} lines`);
  if (Array.isArray(obj.entries)) parts.push(`${obj.entries.length} entries`);
  if (Array.isArray(obj.matches)) parts.push(`${obj.matches.length} matches`);
  if (obj.path) parts.push(String(obj.path));
  if (obj.exit_code !== undefined && obj.exit_code !== null) parts.push(`exit ${obj.exit_code}`);
  if (obj.already_available || obj.already_searched) parts.push("already available");
  return parts.length ? oneLine(parts.join(" · "), 300) : oneLine(safeJson(obj), 300);
}

// Teks satu event mentah (label TOOL/RESULT/OBSERVATION + isinya).
function rawText(ev) {
  const d = ev.data || {};
  const tool = d.tool || "";
  const target = d.target ? ` ${d.target}` : "";
  if (ev.type === "tool_called") return `${tool}${target}`.trim();
  if (ev.type === "tool_completed") {
    const ok = d.success !== false;
    const error = !ok && d.error ? ` — ${d.error}` : "";
    return `${ok ? "check" : "x"} ${tool}${target}${error}`.trim();
  }
  if (ev.type === "observation_received") {
    const ok = d.success !== false;
    const body = rawPreview(d.content);
    const head = `${ok ? "check" : "x"} ${tool}`;
    return body ? `${head} → ${body}` : head;
  }
  return "";
}

function rawTextClass(ev) {
  if (ev.type === "tool_completed" || ev.type === "observation_received") {
    return ev.data && ev.data.success === false ? "err" : "ok";
  }
  return "";
}

// --- Copy final report ------------------------------------------------------
// Salin SELURUH isi final report (teks Markdown sumber dari LLM), bukan hanya
// teks yang terlihat di viewport dan bukan markup HTML hasil render. Memakai
// pola .cmsg-actions/.copy-btn yang sama dengan tombol Copy di Consultant Chat
// (termasuk feedback label "Copied" sementara).
const copiedReportKey = ref(null);
let copiedTimer = null;

// --- Copy Timeline / Activity snapshot ---
const copiedTimeline = ref(false);
let copiedTimelineTimer = null;

async function copyTimeline() {
  const text = buildAgentActivityCopy({
    events: props.events,
    agentStatus: props.status,
  });
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    copiedTimeline.value = true;
    if (copiedTimelineTimer) clearTimeout(copiedTimelineTimer);
    copiedTimelineTimer = setTimeout(() => {
      copiedTimeline.value = false;
      copiedTimelineTimer = null;
    }, 1500);
  } catch (_) {}
}
async function copyReport(item) {
  const text = item && typeof item.reportText === "string" ? item.reportText : "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    return;
  }
  copiedReportKey.value = item.key;
  if (copiedTimer) clearTimeout(copiedTimer);
  copiedTimer = setTimeout(() => {
    copiedReportKey.value = null;
    copiedTimer = null;
  }, 1400);
}

watch(timeline, scrollToLatest, { flush: "post" });

// Saat reasoning status MUNCUL, pastikan barisnya terlihat (scroll ke bawah)
// tanpa mengubah mekanisme scroll yang sudah ada.
watch(
  () => props.isReasoning,
  (on) => {
    if (on) scrollToLatest();
  },
  { flush: "post" }
);
</script>

<template>
  <div ref="scroller" class="act-body">
    <!-- Olympus Stepper Header -->
    <div v-if="lifecycleSteps && lifecycleSteps.length" class="olympus-stepper" role="navigation" aria-label="Olympus Workflow Stepper">
      <div
        v-for="(step, idx) in lifecycleSteps"
        :key="step.label"
        class="olympus-step"
        :class="[step.state, { active: step.state === 'active', done: step.state === 'done' }]"
        :title="`${step.label} (${step.state || 'pending'})`"
      >
        <div class="olympus-step-indicator">
          <svg v-if="step.state === 'done'" class="act-svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          <span v-else-if="step.state === 'active'" class="olympus-step-pulse"></span>
          <span v-else class="olympus-step-num">{{ idx + 1 }}</span>
        </div>
        <span class="olympus-step-label">{{ step.label }}</span>
        <div v-if="idx < lifecycleSteps.length - 1" class="olympus-step-line" :class="{ filled: step.state === 'done' }"></div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="empty" class="vtl-empty">
      <template v-if="status === 'running'">AEGIS is working…</template>
      <template v-else>Give AEGIS a task to begin. Its activity will appear here.</template>
    </div>

    <!-- Vertical Timeline -->
    <div v-else class="vtl">
      <template v-for="item in timeline" :key="item.key">

        <!-- ── Milestone divider ── -->
        <div v-if="item.kind === 'milestone'" :class="['vtl-milestone', item.state]">
          <div class="vtl-node-col">
            <div class="vtl-dot vtl-ms-dot"></div>
          </div>
          <span class="vtl-ms-label">{{ item.title }}</span>
          <span v-if="item.state === 'done'" class="vtl-ms-badge done"><svg class="act-svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" v-html="iconSvg('check')"></svg></span>
          <span v-else-if="item.state === 'active'" class="vtl-ms-badge active">running</span>
        </div>

        <!-- ── Reasoning row with AppThinkingBlock ── -->
        <template v-else-if="item.kind === 'reasoning'">
          <div class="vtl-row reasoning ok">
            <div class="vtl-node-col">
              <div class="vtl-dot"></div>
            </div>
            <div class="vtl-content" style="padding: 0; width: 100%;">
              <AppThinkingBlock
                :title="item.title"
                :collapsed="false"
              >
                <div class="act-detail-text" style="padding: 8px;">{{ item.detailText }}</div>
              </AppThinkingBlock>
            </div>
          </div>
        </template>

        <!-- ── Interactive Questioning Dialog (Agent asks the user back) ── -->
        <template v-else-if="item.kind === 'question'">
          <div class="vtl-row question active">
            <div class="vtl-node-col">
              <div class="vtl-dot question-dot"></div>
            </div>
            <div class="vtl-content question-card-content">
              <div class="act-question-box">
                <div class="act-question-header">
                  <span class="act-question-badge">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <circle cx="12" cy="12" r="10"></circle>
                      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                      <line x1="12" y1="17" x2="12.01" y2="17"></line>
                    </svg>
                    <span>Agent Question</span>
                  </span>
                  <span class="act-time">{{ stamp(item.ts) }}</span>
                </div>
                <div class="act-question-text">{{ item.questionText }}</div>

                <div v-if="item.options && item.options.length" class="act-question-options">
                  <button
                    v-for="(opt, oi) in item.options"
                    :key="oi"
                    type="button"
                    class="act-opt-btn"
                    :disabled="item.answered"
                    @click="handleAnswerQuestion(item, opt)"
                  >
                    {{ opt }}
                  </button>
                </div>

                <div v-if="!item.answered" class="act-question-reply-box">
                  <input
                    v-model="questionReplies[item.key]"
                    type="text"
                    class="act-question-input"
                    :placeholder="item.placeholder || 'Type your reply to the agent…'"
                    @keydown.enter="handleAnswerQuestion(item, questionReplies[item.key])"
                  />
                  <button
                    type="button"
                    class="act-reply-btn"
                    :disabled="!questionReplies[item.key] || !questionReplies[item.key].trim()"
                    @click="handleAnswerQuestion(item, questionReplies[item.key])"
                  >
                    <span>Reply</span>
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <line x1="22" y1="2" x2="11" y2="13"></line>
                      <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                    </svg>
                  </button>
                </div>
                <div v-else class="act-question-answered">
                  <span class="answered-tag">✓ Replied:</span>
                  <span class="answered-text">{{ item.answerText }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- ── Activity row (tool / status / notice) ── -->
        <template v-else>
          <div :class="['vtl-row', item.kind, item.state]">
            <div class="vtl-node-col">
              <div class="vtl-dot"></div>
            </div>
            <div class="vtl-content">
              <span class="act-time">{{ stamp(item.ts) }}</span>
              <span class="act-ico" aria-hidden="true"><svg class="act-svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" v-html="iconSvg(item.icon)"></svg></span>
              <span class="act-title" :title="item.title">{{ item.title }}</span>
              <span v-if="item.scope" class="act-scope" :title="item.scope">{{ item.scope }}</span>
              <span v-if="item.count" class="act-count">{{ item.count }}</span>
              <span v-if="item.error" class="act-error" :title="item.error">{{ item.error }}</span>
              <span v-if="item.stateText" class="act-state" :class="item.state"><svg class="act-svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" v-html="iconSvg(item.stateIcon)"></svg> {{ item.stateText }}</span>
              <button
                v-if="hasDetail(item)"
                type="button"
                class="act-toggle"
                :class="{ open: isOpen(item.key) }"
                :aria-expanded="isOpen(item.key) ? 'true' : 'false'"
                :title="isOpen(item.key) ? 'Hide detail' : 'Show detail'"
                @click="toggle(item.key)"
              >
                <span class="act-caret">{{ isOpen(item.key) ? "▾" : "▸" }}</span>
                <span class="act-toggle-label">{{ isOpen(item.key) ? "hide" : "detail" }}</span>
              </button>
            </div>
          </div>

          <!-- Detail panel -->
          <div v-if="isOpen(item.key)" class="vtl-detail">
            <div v-if="item.detailText" class="act-detail-text">{{ item.detailText }}</div>
            <div v-if="item.files && item.files.length" class="act-files">
              <span v-for="(name, fi) in item.files" :key="fi" class="act-file">{{ name }}</span>
            </div>
            <div v-if="item.events && item.events.length" class="act-raw">
              <div v-for="(ev, ei) in item.events" :key="ei" class="act-raw-row">
                <span class="act-label" :class="rawClass(ev.type)">{{ rawLabel(ev.type) }}</span>
                <span class="act-body-col">
                  <span v-if="ev.ts" class="act-ts">[{{ ev.ts }}]</span>
                  <span class="act-text" :class="rawTextClass(ev)">{{ rawText(ev) }}</span>
                </span>
              </div>
            </div>
          </div>

          <!-- Final agent report (rendered Markdown) -->
          <div v-if="item.reportHtml" class="act-report-block">
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div class="md act-report" v-html="item.reportHtml"></div>
            <div class="cmsg-actions">
              <button
                type="button"
                class="copy-btn"
                :class="{ copied: copiedReportKey === item.key }"
                :title="copiedReportKey === item.key ? 'Copied' : 'Copy final report'"
                :aria-label="copiedReportKey === item.key ? 'Copied' : 'Copy final report'"
                @click="copyReport(item)"
              >
                <svg v-if="copiedReportKey === item.key" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
                <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                <span class="copy-label">{{ copiedReportKey === item.key ? "Copied" : "Copy" }}</span>
              </button>
            </div>
          </div>
        </template>

      </template>

      <!-- Repeated-file notice -->
      <div v-if="repeats.length" class="vtl-row tool warn">
        <div class="vtl-node-col">
          <div class="vtl-dot"></div>
        </div>
        <div class="vtl-content">
          <span class="act-ico" aria-hidden="true"><svg class="act-svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" v-html="iconSvg('warn')"></svg></span>
          <span class="act-title">Repeated reads</span>
          <span v-for="(rep, ri) in repeats" :key="ri" class="act-repeat-item">
            {{ rep.name }}
          </span>
        </div>
      </div>

      <!-- Live reasoning indicator -->
      <div
        v-if="isReasoning"
        class="vtl-row reasoning reasoning-indicator"
        role="status"
        aria-live="polite"
      >
        <div class="vtl-node-col">
          <div class="vtl-dot vtl-reasoning-dot"></div>
        </div>
        <div class="vtl-content">
          <span class="act-ico" aria-hidden="true"><svg class="act-svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" v-html="iconSvg('brain')"></svg></span>
          <span class="act-text reasoning-text">
            Agent reasoning<span class="reasoning-dots" aria-hidden="true"><i>.</i><i>.</i><i>.</i></span>
          </span>
        </div>
      </div>

      <!-- Running cursor -->
      <div v-if="!empty && status === 'running'" class="vtl-cursor-row">
        <div class="vtl-node-col">
          <span class="cursor"></span>
        </div>
      </div>
    </div>
  </div>
</template>

