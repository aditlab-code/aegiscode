/**
 * useWorkbenchDockFacade.js
 *
 * Facade composable mengelola state bottom dock (Terminal, Output, Problems),
 * konsumsi live buffer SSE via useWorkbenchLiveEvents, pembersihan tab dock,
 * dan auto-reveal dock saat terdeteksi galat diagnosa/eksekusi.
 */
import { ref, computed } from "vue";
import { useWorkbenchLiveEvents } from "../useWorkbenchLiveEvents.js";

export function useWorkbenchDockFacade(props, emit, options = {}) {
  const {
    activeEditorDiagnostics,
    checkAndHandleAgentFileConflict,
    bottomDockOpen,
    dockActiveTab,
  } = options;

  // Live Buffers & SSE Event Handling
  const {
    localOutputLines,
    localProblems,
    effectiveOutputLines,
    effectiveProblems,
  } = useWorkbenchLiveEvents(props, {
    editorDiagnostics: activeEditorDiagnostics || ref([]),
    onFileModified: (p) => {
      if (checkAndHandleAgentFileConflict) {
        checkAndHandleAgentFileConflict(p);
      }
    },
    onProblemOccurred: () => {
      if (bottomDockOpen) bottomDockOpen.value = true;
      if (dockActiveTab) dockActiveTab.value = "problems";
    },
  });

  const effectiveTerminalLines = computed(() => props.terminalLines || []);

  const terminalRunning = ref(false);

  function handleClearDock(tab) {
    if (tab === "output") {
      localOutputLines.value = [];
    } else if (tab === "problems") {
      localProblems.value = [];
    } else {
      localOutputLines.value = [];
      localProblems.value = [];
    }
  }

  function handleTerminalCommand() {}
  function handleAbortCommand() {}

  return {
    localOutputLines,
    localProblems,
    effectiveOutputLines,
    effectiveProblems,
    effectiveTerminalLines,
    terminalRunning,
    handleClearDock,
    handleTerminalCommand,
    handleAbortCommand,
  };
}
