/**
 * useWorkbenchLiveEvents.js
 *
 * Mengisolasi penanganan event SSE live (tool calls, tool completions,
 * validasi, file changes, dan error diagnostics) dari template utama Workbench.
 */
import { ref, computed, watch } from "vue";
import { classifyDiagnostic } from "../services/diagnosticService.js";

export const MAX_LIVE_BUFFER = 500;

export function useWorkbenchLiveEvents(props, { editorDiagnostics = null, onFileModified = null, onProblemOccurred = null, onSequenceGap = null, maxBufferSize = MAX_LIVE_BUFFER } = {}) {
  const localOutputLines = ref([]);
  const localProblems = ref([]);
  let lastObservedSequence = 0;
  const effectiveOutputLines = computed(() => {
    return props.outputLines && props.outputLines.length
      ? props.outputLines
      : localOutputLines.value;
  });

  const effectiveProblems = computed(() => {
    const list = [];
    const seen = new Set();

    function addProblem(item) {
      const text = typeof item === "string" ? item : (item?.text || item?.message || "");
      if (!text) return;
      const file = item?.file || "";
      const line = item?.line || 0;
      const col = item?.col || 0;
      const key = `${file}:${line}:${col}:${text}`;
      if (seen.has(key)) return;
      seen.add(key);
      list.push(typeof item === "object" ? item : { text, ts: Date.now() });
    }
    const diags = typeof editorDiagnostics === "function" ? editorDiagnostics() : editorDiagnostics?.value;
    if (Array.isArray(diags)) {
      for (const d of diags) {
        if (d && d.type !== "info") {
          addProblem(d);
        }
      }
    }

    if (Array.isArray(effectiveOutputLines.value)) {
      for (let i = 0; i < effectiveOutputLines.value.length; i++) {
        const line = effectiveOutputLines.value[i];
        const parsed = classifyDiagnostic(line, i);
        if (parsed.type === "syntax" || parsed.type === "type" || parsed.type === "error") {
          addProblem(parsed);
        }
      }
    }

    const explicitProblems = props.problems && props.problems.length
      ? props.problems
      : localProblems.value;
    for (const p of explicitProblems) {
      addProblem(p);
    }

    return list;
  });

  function getEventKey(evt, index) {
    if (!evt) return String(index);
    if (evt.event_id) return String(evt.event_id);
    if (evt.id) return String(evt.id);
    if (evt.sequence !== undefined && evt.sequence !== null) return `seq-${evt.sequence}`;
    const type = evt.event_type || evt.type || evt.event || "";
    const ts = evt.timestamp || "";
    const p = evt.payload || evt.data || {};
    return `${type}:${ts}:${JSON.stringify(p)}`;
  }

  const processedEventKeys = new Set();
  const MAX_PROCESSED_KEYS = 2000;

  watch(
    () => props.activityEvents,
    (events) => {
      if (!events || !events.length) {
        processedEventKeys.clear();
        lastObservedSequence = 0;
        return;
      }

      for (let i = 0; i < events.length; i++) {
        const evt = events[i];
        const key = getEventKey(evt, i);
        if (processedEventKeys.has(key)) {
          continue;
        }
        processedEventKeys.add(key);

        // Validasi sequence gap
        const seq = typeof evt.sequence === "number" ? evt.sequence : null;
        if (seq !== null && seq > 0) {
          if (lastObservedSequence > 0 && seq > lastObservedSequence + 1) {
            if (typeof onSequenceGap === "function") {
              onSequenceGap({
                lastSequence: lastObservedSequence,
                receivedSequence: seq,
                missingFrom: lastObservedSequence + 1,
                missingTo: seq - 1,
                event: evt,
              });
            }
          }
          if (seq > lastObservedSequence) {
            lastObservedSequence = seq;
          }
        }

        const type = evt.event_type || evt.type || evt.event || "";
        const p = evt.payload || evt.data || evt;
        const ts = evt.timestamp || Date.now();
        if (type === "tool_called") {
          const displayTool = p.canonical_tool || p.tool || "tool";
          localOutputLines.value.push({
            text: `[tool:call] ${displayTool} ${p.path || p.target || p.command || p.query || ""}`.trim(),
            ts,
          });
        } else if (type === "tool_completed") {
          const isSuccess = p.success !== false && !p.error;
          if (!isSuccess) {
            localProblems.value.push({
              text: `Tool '${p.tool || "tool"}' error: ${p.error || "Execution failed"}`,
              ts,
            });
          } else {
            const toolName = p.canonical_tool || p.tool || "";
            const isFileWriteTool = [
              "write_file",
              "edit_file",
              "write_to_file",
              "replace_file_content",
              "replace_content",
              "patch_file",
              "apply_patch",
            ].includes(toolName);
            const writtenPath = p.path || p.target || p.file_path || p.file;
            if (isFileWriteTool && writtenPath && onFileModified) {
              onFileModified(writtenPath);
            }
          }
        } else if (type === "file_written" || type === "file_modified") {
          const writtenPath = p.path || p.target || p.file_path || p.file;
          if (writtenPath && onFileModified) {
            onFileModified(writtenPath);
          }
        } else if (type === "validation_completed") {
          if (p.success === false || p.passed === false || p.error) {
            localProblems.value.push({
              text: `Validation failed: ${p.error || p.message || "Checks did not pass"}`,
              ts,
            });
          }
        } else if (type === "task_failed") {
          localProblems.value.push({
            text: `Task failed: ${p.error || "Unknown error"}`,
            ts,
          });
          localOutputLines.value.push({
            text: `[task:failed] ${p.error || "Unknown error"}`,
            ts,
          });
        }
      }

      if (processedEventKeys.size > MAX_PROCESSED_KEYS) {
        const toDelete = Array.from(processedEventKeys).slice(0, 500);
        for (const k of toDelete) {
          processedEventKeys.delete(k);
        }
      }

      if (localOutputLines.value.length > maxBufferSize) {
        localOutputLines.value = localOutputLines.value.slice(-maxBufferSize);
      }
      if (localProblems.value.length > maxBufferSize) {
        localProblems.value = localProblems.value.slice(-maxBufferSize);
      }
    },
    { deep: true }
  );

  let lastProblemCount = 0;
  watch(effectiveProblems, (problems) => {
    if (problems.length > lastProblemCount) {
      lastProblemCount = problems.length;
      if (onProblemOccurred) onProblemOccurred();
    } else if (problems.length === 0) {
      lastProblemCount = 0;
    }
  });

  watch(
    () => props.error,
    (newErr) => {
      if (newErr) {
        localProblems.value.push({ text: newErr, ts: Date.now() });
        localOutputLines.value.push({ text: `[error] ${newErr}`, ts: Date.now() });
        if (localProblems.value.length > maxBufferSize) {
          localProblems.value = localProblems.value.slice(-maxBufferSize);
        }
        if (localOutputLines.value.length > maxBufferSize) {
          localOutputLines.value = localOutputLines.value.slice(-maxBufferSize);
        }
      }
    }
  );

  return {
    localOutputLines,
    localProblems,
    effectiveOutputLines,
    effectiveProblems,
  };
}
