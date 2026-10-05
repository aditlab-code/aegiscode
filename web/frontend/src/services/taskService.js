export const HISTORY_GROUPS = Object.freeze(["TODAY", "YESTERDAY", "OLDER"]);

export const ACTIVE_STATUSES = Object.freeze([
  "running",
  "prepared",
  "planning",
  "executing",
  "validating",
]);

export const TERMINAL_STATUSES = Object.freeze([
  "completed",
  "failed",
  "cancelled",
]);

/**
 * Map task status to CSS class token.
 * @param {string} status
 * @returns {'status-on' | 'status-err' | 'status-run' | 'status-off'}
 */
export function statusTagClass(status) {
  const v = String(status || "").trim().toLowerCase();
  if (v === "completed") return "status-on";
  if (v === "failed") return "status-err";
  if (ACTIVE_STATUSES.includes(v)) return "status-run";
  return "status-off";
}

/**
 * Normalize raw execution mode string.
 * @param {unknown} raw
 * @returns {'parallel' | 'queue'}
 */
export function normalizeExecutionMode(raw) {
  const v = String(raw || "").trim().toLowerCase();
  return v === "parallel" ? "parallel" : "queue";
}

/**
 * User-facing execution mode label.
 * @param {unknown} mode
 * @returns {'Parallel' | 'Queue'}
 */
export function executionLabel(mode) {
  return normalizeExecutionMode(mode) === "parallel" ? "Parallel" : "Queue";
}

/**
 * Format ISO timestamp string for persistent task history display.
 * @param {unknown} raw
 * @returns {string}
 */
export function formatTs(raw) {
  if (!raw) return "—";
  const d = new Date(raw);
  return Number.isNaN(d.getTime()) ? String(raw) : d.toLocaleString();
}

/**
 * Classify a task item or timestamp into TODAY, YESTERDAY, or OLDER bucket.
 * @param {unknown} itemOrTimestamp
 * @returns {'TODAY' | 'YESTERDAY' | 'OLDER'}
 */
export function taskTimeGroup(itemOrTimestamp) {
  let ts = itemOrTimestamp;
  if (
    itemOrTimestamp &&
    typeof itemOrTimestamp === "object" &&
    !(itemOrTimestamp instanceof Date)
  ) {
    ts =
      itemOrTimestamp.last_timestamp ||
      itemOrTimestamp.timestamp ||
      itemOrTimestamp.created_at;
  }
  if (!ts) return "OLDER";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "OLDER";

  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart);
  yesterdayStart.setDate(yesterdayStart.getDate() - 1);

  if (d >= todayStart) return "TODAY";
  if (d >= yesterdayStart && d < todayStart) return "YESTERDAY";
  return "OLDER";
}

/**
 * Group array of history tasks into ordered non-empty buckets.
 * @param {Array<object>} tasks
 * @returns {Array<{ label: string, items: Array<object> }>}
 */
export function groupTaskHistory(tasks = []) {
  if (!Array.isArray(tasks)) return [];
  const groups = { TODAY: [], YESTERDAY: [], OLDER: [] };
  for (const t of tasks) {
    const g = taskTimeGroup(t);
    if (!groups[g]) groups[g] = [];
    groups[g].push(t);
  }
  const result = [];
  for (const key of HISTORY_GROUPS) {
    if (groups[key] && groups[key].length > 0) {
      result.push({ label: key, items: groups[key] });
    }
  }
  return result;
}

/**
 * Pure telemetry reducer over event lists.
 * @param {Array<object>} events
 * @returns {{ rounds: number, toolCalls: number, observations: number }}
 */
export function computeTaskTelemetry(events = []) {
  let rounds = 0;
  let toolCalls = 0;
  let observations = 0;
  if (!Array.isArray(events)) {
    return { rounds: 0, toolCalls: 0, observations: 0 };
  }
  for (const raw of events) {
    if (!raw) continue;
    const type = raw.event_type || raw.event || raw.type || "";
    if (type === "provider_request") {
      rounds += 1;
    } else if (type === "tool_called") {
      toolCalls += 1;
    } else if (type === "observation_received") {
      observations += 1;
    }
  }
  return { rounds, toolCalls, observations };
}
