// Aegis Workbench — Logika Lifecycle Olympus Autonomous Workflow.
//
// Alur kerja otonom Olympus framework terdiri dari 6 tahapan dinamis:
//   0. DEFINE : Spesifikasi, PRD, requirements, dan wawancara
//   1. PLAN   : Perencanaan arsitektur dan pemecahan task
//   2. BUILD  : Implementasi inkremental & simplifikasi kode
//   3. VERIFY : Pengujian, debugging, error recovery
//   4. REVIEW : Code review multi-axis & verifikasi kualitas
//   5. SHIP   : Peluncuran, staged rollout, deployment readiness
//
// Dua konsep dipisah:
//   - current activity phase : step yang SEDANG aktif (active).
//   - milestones             : step yang SUDAH pernah dicapai (tetap done).

export const OLYMPUS_PHASES = [
  "DEFINE",
  "PLAN",
  "BUILD",
  "VERIFY",
  "REVIEW",
  "SHIP",
];

export const LIFECYCLE_STEP_COUNT = OLYMPUS_PHASES.length;

// Mapping nama phase (Olympus primer + kompatibilitas alias aktivitas) ke index 0..5
const ACTIVITY_PHASE_INDEX = {
  // 0: DEFINE
  define: 0,
  defining: 0,
  spec: 0,
  interview: 0,

  // 1: PLAN
  plan: 1,
  planning: 1,

  // 2: BUILD
  build: 2,
  building: 2,
  inspecting: 2,
  editing: 2,

  // 3: VERIFY
  verify: 3,
  verifying: 3,
  running: 3,
  validating: 3,
  validation: 3,
  test: 3,
  testing: 3,

  // 4: REVIEW
  review: 4,
  reviewing: 4,
  code_review: 4,

  // 5: SHIP
  ship: 5,
  shipping: 5,
  completed: 5,
};

export const VERIFYING_STEP = 3;
export const VALIDATING_STEP = 3;

/**
 * Index step lifecycle untuk sebuah activity phase.
 *
 * @param {string} phase
 * @returns {number} 0..5 untuk phase yang dikenal, -1 untuk phase tak dikenal
 */
export function activityPhaseIndex(phase) {
  if (phase == null) return -1;
  const key = String(phase).trim().toLowerCase();
  return Object.prototype.hasOwnProperty.call(ACTIVITY_PHASE_INDEX, key)
    ? ACTIVITY_PHASE_INDEX[key]
    : -1;
}

/** True bila nilai ini activity phase UI yang dikenal (bukan nilai internal). */
export function isActivityPhase(phase) {
  return activityPhaseIndex(phase) >= 0;
}

/**
 * Tambahkan milestone step yang SUDAH dicapai (immutable).
 *
 * @param {number[]} milestones daftar index yang sudah dicapai.
 * @param {number} index index step (0..count-1).
 * @param {number} [count=LIFECYCLE_STEP_COUNT]
 * @returns {number[]} array baru (unik, terurut); array lama bila tidak berubah.
 */
export function addMilestone(milestones, index, count = LIFECYCLE_STEP_COUNT) {
  const list = Array.isArray(milestones) ? milestones : [];
  if (!Number.isInteger(index) || index < 0 || index >= count) return list;
  if (list.includes(index)) return list;
  return [...list, index].sort((a, b) => a - b);
}

function normalizeMilestones(milestones, count) {
  const set = new Set();
  for (const i of milestones || []) {
    if (Number.isInteger(i) && i >= 0 && i < count) set.add(i);
  }
  return set;
}

function maxMilestone(milestones) {
  let max = -1;
  for (const i of milestones || []) {
    if (Number.isInteger(i) && i > max) max = i;
  }
  return max;
}

/**
 * Hitung STATE tiap step lifecycle dari state frontend.
 *
 * @returns {string[]} array state (""|"done"|"active") sepanjang `count`.
 */
export function buildLifecycleStates({
  hasTask,
  status,
  currentPhase,
  milestones,
  count = LIFECYCLE_STEP_COUNT,
}) {
  const states = new Array(Math.max(0, count | 0)).fill("");
  if (!hasTask || states.length === 0) return states;

  const s = String(status || "").toLowerCase();
  const done = normalizeMilestones(milestones, states.length);
  const phaseIdx = activityPhaseIndex(currentPhase);
  const lastIndex = states.length - 1;

  let activeIdx;
  if (s === "completed") {
    // Terminal sukses: seluruh step sampai REVIEW tercapai, SHIP titik akhir.
    for (let i = 0; i < lastIndex; i += 1) done.add(i);
    activeIdx = lastIndex;
  } else if (s === "failed" || s === "cancelled") {
    // Gagal/dibatalkan BUKAN SHIP: pertahankan aktivitas terakhir nyata.
    activeIdx = phaseIdx >= 0 ? phaseIdx : maxMilestone(milestones);
  } else {
    // Berjalan: ikuti activity phase terakhir; sebelum ada -> DEFINE (index 0).
    activeIdx = phaseIdx >= 0 ? phaseIdx : maxMilestone(milestones);
  }
  if (activeIdx < 0) activeIdx = 0;
  if (activeIdx > lastIndex) activeIdx = lastIndex;

  for (let i = 0; i < states.length; i += 1) {
    if (i === activeIdx) states[i] = "active";
    else if (done.has(i)) states[i] = "done";
    else states[i] = "";
  }
  return states;
}

/**
 * Rekonstruksi lifecycle dari daftar event.
 */
export function lifecycleFromEvents(events) {
  let milestones = [];
  let currentPhase = "";
  for (const raw of events || []) {
    const type = (raw && (raw.event_type || raw.event)) || "";
    const payload = (raw && (raw.payload || raw.data)) || {};
    if (type === "task_started") {
      milestones = addMilestone(milestones, 0);
      if (!currentPhase) currentPhase = "define";
    } else if (type === "phase_changed") {
      const idx = activityPhaseIndex(payload.phase);
      if (idx >= 0) {
        milestones = addMilestone(milestones, idx);
        currentPhase = String(payload.phase).trim().toLowerCase();
      }
    } else if (type === "validation_started") {
      milestones = addMilestone(milestones, VALIDATING_STEP);
      currentPhase = "verify";
    }
  }
  return { milestones, currentPhase };
}
