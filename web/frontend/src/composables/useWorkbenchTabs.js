/**
 * useWorkbenchTabs.js
 *
 * Mengelola navigasi tab, pembagian split-pane horizontal/vertikal,
 * penutupan tab dengan dirty check, dan sinkronisasi model Monaco.
 */
import { ref, computed, watch } from "vue";
import {
  createEditorTabsState,
  openTab,
  openDiffTab,
  closeTab,
  selectTab,
  getActiveTab,
  setTabConflict,
  setTabDirty,
} from "../services/editorTabsService.js";
import { readFileContent } from "../api.js";
import {
  getModel,
  isDirty,
  markSaved,
  applyExternalContent,
} from "../services/monacoModelRegistry.js";

export function useWorkbenchTabs(props) {
  const pane1TabsState = createEditorTabsState();
  const pane2TabsState = createEditorTabsState();
  const editorTabsState = pane1TabsState;

  const activeCodeEditorRef = ref(null);
  const splitCodeEditorRef = ref(null);

  const splitActive = ref(Boolean(props.initialSplitActive));
  const splitDirection = ref(props.initialSplitDirection || "vertical");
  const splitRatio = ref(50);
  const activePane = ref("pane1");

  // Conflict Resolution
  const conflictFile = ref(null);
  const conflictAgentText = ref("");
  const conflictUserText = ref("");

  const conflictAddedLines = computed(() => {
    if (!conflictAgentText.value || !conflictUserText.value) return 0;
    const agentLines = new Set(conflictAgentText.value.split("\n"));
    const userLines = new Set(conflictUserText.value.split("\n"));
    return [...agentLines].filter((l) => !userLines.has(l)).length;
  });

  const conflictRemovedLines = computed(() => {
    if (!conflictAgentText.value || !conflictUserText.value) return 0;
    const agentLines = new Set(conflictAgentText.value.split("\n"));
    const userLines = new Set(conflictUserText.value.split("\n"));
    return [...userLines].filter((l) => !agentLines.has(l)).length;
  });

  async function triggerConflictResolution(filePath) {
    try {
      const data = await readFileContent(filePath);
      conflictAgentText.value = typeof data?.content === "string" ? data.content : "";
      conflictUserText.value = getModel(filePath)?.getValue?.() ?? "";
      setTabConflict(pane1TabsState, filePath, true);
      setTabConflict(pane2TabsState, filePath, true);
      conflictFile.value = filePath;
    } catch (err) {
      console.error("Conflict detection failed to load disk content:", err);
    }
  }

  async function checkAndHandleAgentFileConflict(filePath) {
    if (!filePath) return;
    const isDirtyFile =
      isDirty(filePath) ||
      pane1TabsState.tabs.value.some((t) => t.path === filePath && t.dirty) ||
      pane2TabsState.tabs.value.some((t) => t.path === filePath && t.dirty);

    if (isDirtyFile) {
      await triggerConflictResolution(filePath);
    } else {
      try {
        const data = await readFileContent(filePath);
        if (typeof data?.content === "string") {
          applyExternalContent(filePath, data.content);
          const m = getModel(filePath);
          if (m?.getAlternativeVersionId) {
            markSaved(filePath, m.getAlternativeVersionId());
          }
          setTabDirty(pane1TabsState, filePath, false);
          setTabDirty(pane2TabsState, filePath, false);
        }
      } catch {
        // Ignore background reload error
      }
    }
  }

  function resolveKeepMine() {
    if (conflictFile.value) {
      setTabConflict(pane1TabsState, conflictFile.value, false);
      setTabConflict(pane2TabsState, conflictFile.value, false);
      conflictFile.value = null;
    }
  }

  function resolveAcceptAgent() {
    if (conflictFile.value) {
      const target = conflictFile.value;
      applyExternalContent(target, conflictAgentText.value);
      const m = getModel(target);
      if (m?.getAlternativeVersionId) {
        markSaved(target, m.getAlternativeVersionId());
      }
      setTabDirty(pane1TabsState, target, false);
      setTabDirty(pane2TabsState, target, false);
      setTabConflict(pane1TabsState, target, false);
      setTabConflict(pane2TabsState, target, false);
      conflictFile.value = null;
    }
  }

  function toggleSplitEditor() {
    splitActive.value = !splitActive.value;
  }

  function toggleSplitOrientation() {
    splitDirection.value = splitDirection.value === "vertical" ? "horizontal" : "vertical";
  }

  async function resolveReviewDiff() {
    if (conflictFile.value) {
      const target = conflictFile.value;
      setTabConflict(pane1TabsState, target, false);
      setTabConflict(pane2TabsState, target, false);
      openDiffTab(pane2TabsState, target);
      if (!splitActive.value) {
        toggleSplitEditor();
      }
      conflictFile.value = null;
    }
  }

  const effectiveSplitDirection = computed(() => {
    if (props.tier === "mobile" || props.tier === "compact") {
      return "horizontal";
    }
    return splitDirection.value;
  });

  const pane1Style = computed(() => {
    if (effectiveSplitDirection.value === "vertical") {
      return {
        width: `calc(${splitRatio.value}% - 2px)`,
        height: "100%",
        flex: `0 0 calc(${splitRatio.value}% - 2px)`,
        minWidth: "0",
      };
    }
    return {
      height: `calc(${splitRatio.value}% - 2px)`,
      width: "100%",
      flex: `0 0 calc(${splitRatio.value}% - 2px)`,
      minHeight: "0",
    };
  });

  const pane2Style = computed(() => {
    if (effectiveSplitDirection.value === "vertical") {
      return {
        width: `calc(${100 - splitRatio.value}% - 2px)`,
        height: "100%",
        flex: `0 0 calc(${100 - splitRatio.value}% - 2px)`,
        minWidth: "0",
      };
    }
    return {
      height: `calc(${100 - splitRatio.value}% - 2px)`,
      width: "100%",
      flex: `0 0 calc(${100 - splitRatio.value}% - 2px)`,
      minHeight: "0",
    };
  });

  function triggerEditorLayout() {
    activeCodeEditorRef.value?.layout?.();
    splitCodeEditorRef.value?.layout?.();
  }

  // Initialize initial tabs
  if (props.initialTabs && props.initialTabs.length > 0) {
    for (const t of props.initialTabs) {
      const tab = openTab(pane1TabsState, t);
      if (tab && t && typeof t === "object" && t.dirty) {
        tab.dirty = true;
      }
    }
    if (props.initialActiveTab) {
      selectTab(pane1TabsState, props.initialActiveTab);
    }
  }

  watch(
    () => props.initialActiveTab,
    (newTab) => {
      if (newTab) {
        selectTab(pane1TabsState, newTab);
      }
    }
  );

  const pane1ActiveTab = computed(() => getActiveTab(pane1TabsState));
  const pane1ActiveTabPath = computed(() => (pane1ActiveTab.value ? pane1ActiveTab.value.path : ""));
  const isPane1TabDirty = computed(() => Boolean(pane1ActiveTab.value?.dirty));

  const pane2ActiveTab = computed(() => getActiveTab(pane2TabsState));
  const pane2ActiveTabPath = computed(() => (pane2ActiveTab.value ? pane2ActiveTab.value.path : ""));
  const isPane2TabDirty = computed(() => Boolean(pane2ActiveTab.value?.dirty));

  const activeTab = computed(() => {
    if (splitActive.value && activePane.value === "pane2") {
      return pane2ActiveTab.value || pane1ActiveTab.value;
    }
    return pane1ActiveTab.value || pane2ActiveTab.value;
  });
  const activeTabPath = computed(() => (activeTab.value ? activeTab.value.path : ""));

  return {
    pane1TabsState,
    pane2TabsState,
    editorTabsState,
    activeCodeEditorRef,
    splitCodeEditorRef,
    splitActive,
    splitDirection,
    splitRatio,
    activePane,
    conflictFile,
    conflictAgentText,
    conflictUserText,
    conflictAddedLines,
    conflictRemovedLines,
    triggerConflictResolution,
    checkAndHandleAgentFileConflict,
    resolveKeepMine,
    resolveAcceptAgent,
    resolveReviewDiff,
    toggleSplitEditor,
    toggleSplitOrientation,
    effectiveSplitDirection,
    pane1Style,
    pane2Style,
    triggerEditorLayout,
    pane1ActiveTab,
    pane1ActiveTabPath,
    isPane1TabDirty,
    pane2ActiveTab,
    pane2ActiveTabPath,
    isPane2TabDirty,
    activeTab,
    activeTabPath,
  };
}
