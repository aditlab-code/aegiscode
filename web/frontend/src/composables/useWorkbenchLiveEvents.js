/**
 * useWorkbenchLiveEvents.js
 *
 * Mengisolasi penanganan event SSE live (tool calls, tool completions,
 * validasi, file changes, dan error diagnostics) dari template utama Workbench.
 */
import { ref, computed, watch } from "vue";
import { classifyDiagnostic } from "../services/diagnosticService.js";

export function useWorkbenchLiveEvents(props, { editorDiagnostics = null, onFileModified = null, onProblemOccurred = null } = {}) {
  const localOutputLines = ref([]);
  const localProblems = ref([]);

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
      if (!text || seen.has(text)) return;
      seen.add(text);
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

  let lastProcessedEventCount = 0;
  watch(
    () => props.activityEvents,
    (events) => {
      if (!events || !events.length) {
        lastProcessedEventCount = 0;
        return;
      }
      const newEvents = events.slice(lastProcessedEventCount);
      lastProcessedEventCount = events.length;

      for (const evt of newEvents) {
        const type = evt.event_type || evt.type || evt.event || "";
        const p = evt.payload || evt.data || evt;
        const ts = evt.timestamp || Date.now();

        if (type === "tool_called") {
          localOutputLines.value.push({
            text: `[tool:call] ${p.tool || "tool"} ${p.path || p.command || p.query || ""}`.trim(),
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
            const isFileWriteTool = [
              "write_file",
              "write_to_file",
              "replace_file_content",
              "replace_content",
              "patch_file",
              "apply_patch",
            ].includes(p.tool);
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
