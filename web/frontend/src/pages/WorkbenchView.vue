<script setup>
/**
 * WorkbenchView.vue — AI-First Modern Center Workbench, Bottom Dock & Right Assistant (Phase 5).
 *
 * Implements:
 *   1. 3-column resizable IDE surface with AppSplitter dividers.
 *   2. File opening from Left Sidebar into center Monaco tabs via editorTabsService.
 *   3. Monaco editor tab strip with dirty indicator and AppBreadcrumbs hierarchy.
 *   4. Collapsible and resizable AppBottomDock (Terminal, Output, Problems).
 *   5. Task composition & stop controls in AppRightDrawer.
 *   6. 1-click "Apply to Editor" from ConsultantChat into Monaco editor.
 *   7. Responsive layout tiers (desktop, compact, mobile) with overlay backdrop.
 */
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import AppSplitter from "../components/ui/AppSplitter.vue";
import AppBreadcrumbs from "../components/ui/AppBreadcrumbs.vue";
import AppLeftSidebar from "../components/layout/AppLeftSidebar.vue";
import AppRightDrawer from "../components/layout/AppRightDrawer.vue";
import AppBottomDock from "../components/layout/AppBottomDock.vue";
import CodeEditor from "../components/CodeEditor.vue";
import MonacoDiffEditor from "../components/MonacoDiffEditor.vue";
import SettingsOverlay from "./SettingsOverlay.vue";
import WelcomeView from "../components/WelcomeView.vue";
import AppModal from "../components/ui/AppModal.vue";
import { discardProjectGitChanges, readFileContent, writeFileContent } from "../api.js";
import {
  openTab,
  openDiffTab,
  closeTab,
  selectTab,
  getActiveTab,
  setTabDirty,
} from "../services/editorTabsService.js";
import {
  isDirty,
  getModel,
  getEntry,
  getOrCreateModel,
  markSaved,
  applyExternalContent,
  releaseModel,
} from "../services/monacoModelRegistry.js";
import { languageForFile } from "../editorLanguages.js";
import { mapMonacoMarkersToDiagnostics, classifyDiagnostic } from "../services/diagnosticService.js";
import { useWorkbenchLayout } from "../composables/useWorkbenchLayout.js";
import { useWorkbenchTabs } from "../composables/useWorkbenchTabs.js";
import { useWorkbenchLiveEvents } from "../composables/useWorkbenchLiveEvents.js";
import {
  loadWorkspaceContext,
  saveWorkspaceContext,
} from "../services/workspaceContextService.js";

const props = defineProps({
  config: {
    type: Object,
    default: () => ({}),
  },
  taskHistory: {
    type: Array,
    default: () => [],
  },
  settingsTab: {
    type: String,
    default: "providers",
  },
  activeProject: {
    type: Object,
    default: null,
  },
  projects: {
    type: Array,
    default: () => [],
  },
  selectedProjectId: {
    type: String,
    default: "",
  },
  activeNav: {
    type: String,
    default: "explorer",
  },
  changes: {
    type: Array,
    default: () => [],
  },
  validation: {
    type: Object,
    default: () => ({}),
  },
  explorerRefresh: {
    type: Number,
    default: 0,
  },
  liveFsChange: {
    type: Object,
    default: null,
  },
  queueRefresh: {
    type: Number,
    default: 0,
  },
  connected: {
    type: Boolean,
    default: false,
  },
  gatewayAddress: {
    type: String,
    default: "",
  },
  agentStatus: {
    type: Object,
    default: () => ({ label: "idle", cls: "status-off" }),
  },
  task: {
    type: Object,
    default: () => ({}),
  },
  taskTag: {
    type: Object,
    default: () => ({ cls: "", label: "" }),
  },
  showTaskMeta: {
    type: Boolean,
    default: false,
  },
  taskProvider: {
    type: String,
    default: "",
  },
  taskModel: {
    type: String,
    default: "",
  },
  taskExecutionLabel: {
    type: String,
    default: "Queue",
  },
  taskRoundLabel: {
    type: String,
    default: "",
  },
  taskDurationLabel: {
    type: String,
    default: "",
  },
  taskTimerLive: {
    type: Boolean,
    default: false,
  },
  showTaskTelemetry: {
    type: Boolean,
    default: false,
  },
  taskLlmRounds: {
    type: Number,
    default: 0,
  },
  taskToolCalls: {
    type: Number,
    default: 0,
  },
  taskTokensLabel: {
    type: String,
    default: "",
  },
  taskTokensTooltip: {
    type: String,
    default: "",
  },
  lifecycleSteps: {
    type: Array,
    default: () => [],
  },
  lifecyclePct: {
    type: Number,
    default: 0,
  },
  activityPhase: {
    type: String,
    default: "",
  },
  activityEvents: {
    type: Array,
    default: () => [],
  },
  showReasoning: {
    type: Boolean,
    default: false,
  },
  activityCopied: {
    type: Boolean,
    default: false,
  },
  isRunning: {
    type: Boolean,
    default: false,
  },
  stopInProgress: {
    type: Boolean,
    default: false,
  },
  isSubmitting: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: "",
  },
  consultantProps: {
    type: Object,
    default: () => ({}),
  },
  runningTaskId: {
    type: String,
    default: "",
  },
  terminalLines: {
    type: Array,
    default: () => [],
  },
  outputLines: {
    type: Array,
    default: () => [],
  },
  problems: {
    type: Array,
    default: () => [],
  },
  tier: {
    type: String,
    default: "desktop",
  },
  activeOverlay: {
    type: String,
    default: null,
  },
  sidebarVisible: {
    type: Boolean,
    default: true,
  },
  assistantVisible: {
    type: Boolean,
    default: true,
  },
  initialTabs: {
    type: Array,
    default: () => [],
  },
  initialActiveTab: {
    type: String,
    default: "",
  },
  initialSplitActive: {
    type: Boolean,
    default: false,
  },
  initialSplitDirection: {
    type: String,
    default: "vertical",
  },
  initialSplitTab: {
    type: String,
    default: "",
  },
  providers: {
    type: Array,
    default: () => [],
  },
  providerInstanceId: {
    type: String,
    default: "",
  },
  modelId: {
    type: String,
    default: "",
  },
  mode: {
    type: String,
    default: "balanced",
  },
});

const emit = defineEmits([
  "select-project",
  "close-project",
  "open-file",
  "active-file-change",
  "stop-task",
  "view-task",
  "open-composer",
  "request-stop",
  "submit-task",
  "open-settings",
  "open-report",
  "copy-activity",
  "run-consultant-task",
  "consultant-event",
  "apply-to-editor",
  "toggle-dock",
  "cursor-change",
  "close-overlay",
  "toggle-assistant",
  "toggle-sidebar",
  "update:provider-instance-id",
  "update:model-id",
  "update:mode",
  "refresh-config",
  "refresh-history",
  "open-history-task",
  "open-consultant-session",
  "open-session",
  "open-folder",
  "delete-project",
  "open-path",
  "open-explorer",
  "branch-info-updated",
]);

// 1. Column Sizing & Visibility State (via useWorkbenchLayout)
const {
  sidebarWidth,
  sidebarVisible,
  assistantWidth,
  assistantVisible,
  assistantTab,
  bottomDockOpen,
  dockHeight,
  dockActiveTab,
  toggleSidebar,
  toggleAssistant,
  toggleBottomDock,
} = useWorkbenchLayout(props, emit);
const activeConsultantSessionId = ref("");

function handleOpenConsultantSession(sessionId) {
  assistantTab.value = "consultant";
  if (!assistantVisible.value) {
    toggleAssistant(true);
  }
  activeConsultantSessionId.value = sessionId || "";
  emit("open-session", sessionId);
  emit("open-consultant-session", sessionId);
}

function handleRunConsultantTask(taskPayload) {
  assistantTab.value = "agents";
  emit("run-consultant-task", taskPayload);
}

const rightDrawerRef = ref(null);

function handleOpenAgentComposer() {
  assistantTab.value = "agents";
  if (!assistantVisible.value) {
    toggleAssistant(true);
  }
  nextTick(() => {
    rightDrawerRef.value?.focusPrompt?.();
    const ta = document.querySelector(".chat-prompt-textarea");
    if (ta) ta.focus();
  });
}

const consultantBusy = ref(false);
const bgToast = ref(null);
let bgToastTimer = null;

function showBgToast(opts) {
  if (bgToastTimer) {
    clearTimeout(bgToastTimer);
    bgToastTimer = null;
  }
  bgToast.value = opts;
  bgToastTimer = setTimeout(() => {
    bgToast.value = null;
  }, 6000);
}

function handleOpenToastAction() {
  if (bgToast.value?.tab) {
    assistantTab.value = bgToast.value.tab;
  }
  if (!assistantVisible.value) {
    toggleAssistant(true);
  }
  bgToast.value = null;
}

function handleConsultantEvent(event) {
  if (event?.type === "sending_started") {
    consultantBusy.value = true;
  } else if (event?.type === "sending_completed") {
    consultantBusy.value = false;
    if (!assistantVisible.value) {
      showBgToast({
        type: event.error ? "error" : "success",
        title: event.error ? "Consultant Error" : "Consultant Response Ready",
        message: event.error || (event.prompt ? (event.prompt.length > 40 ? event.prompt.slice(0, 40) + "…" : event.prompt) : "New analysis available"),
        tab: "consultant",
      });
    }
  }
  emit("consultant-event", event);
}

watch(
  () => props.isRunning,
  (running, prevRunning) => {
    if (prevRunning && !running) {
      if (!assistantVisible.value) {
        const isCompleted = props.task?.status === "completed";
        const promptPreview = props.task?.prompt
          ? (props.task.prompt.length > 40 ? props.task.prompt.slice(0, 40) + "…" : props.task.prompt)
          : "";
        showBgToast({
          type: isCompleted ? "success" : "warning",
          title: isCompleted ? "Task Completed" : `Task ${props.task?.status || "Finished"}`,
          message: promptPreview,
          tab: "agents",
        });
      }
    }
  }
);

const effectiveProviderList = computed(() => {
  return props.providers?.length ? props.providers : (props.config?.provider_instances || []);
});

const effectiveProviderInstanceId = computed(() => {
  return props.providerInstanceId || props.config?.provider_instance_id || "";
});

const effectiveModelId = computed(() => {
  return props.modelId || props.config?.model_id || props.config?.model || "";
});

const activeProviderInstance = computed(() => {
  const id = effectiveProviderInstanceId.value;
  return effectiveProviderList.value.find((p) => p.id === id) || null;
});

const effectiveTaskProvider = computed(() => {
  if (props.taskProvider) return props.taskProvider;
  return activeProviderInstance.value?.name || props.config?.provider || "";
});

const effectiveTaskModel = computed(() => {
  if (props.taskModel) return props.taskModel;
  const inst = activeProviderInstance.value;
  const m = (inst?.models || []).find((x) => x.id === effectiveModelId.value);
  return m ? m.model_name : (props.config?.model || "");
});

const effectiveConsultantProps = computed(() => {
  const base = props.consultantProps || {};
  const currentTab = activeTab.value;
  return {
    ...base,
    activeSessionId: activeConsultantSessionId.value || base.activeSessionId || "",
    providers: base.providers?.length ? base.providers : effectiveProviderList.value,
    providerInstanceId: base.providerInstanceId || effectiveProviderInstanceId.value,
    modelId: base.modelId || effectiveModelId.value,
    projectId: base.projectId || props.activeProject?.id || "",
    running: typeof base.running === "boolean" ? base.running : props.isRunning,
    runningTaskId: props.runningTaskId || base.runningTaskId || props.task?.id || "",
    providerLabel: effectiveTaskProvider.value,
    modelLabel: effectiveTaskModel.value,
    activeTabPath: currentTab ? currentTab.path : "",
    activeFile: currentTab
      ? {
          path: currentTab.path,
          content: currentTab.content || null,
        }
      : null,
  };
});

// 2. Editor Diagnostics & Multi-Tab State (via useWorkbenchTabs)
const activeEditorMarkers = ref([]);
const activeEditorSyntaxErrors = ref([]);
const activeEditorLinterDiagnostics = ref([]);

const activeEditorDiagnostics = computed(() => {
  const merged = [
    ...activeEditorMarkers.value,
    ...activeEditorSyntaxErrors.value,
    ...activeEditorLinterDiagnostics.value,
  ];
  const seen = new Set();
  const unique = [];
  for (const d of merged) {
    const key = `${d.file}:${d.line}:${d.col}:${d.text}`;
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(d);
    }
  }
  return unique;
});

const {
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
} = useWorkbenchTabs(props);

// 3. Live Buffers & SSE Event Handling (via useWorkbenchLiveEvents)
const {
  localOutputLines,
  localProblems,
  effectiveOutputLines,
  effectiveProblems,
} = useWorkbenchLiveEvents(props, {
  editorDiagnostics: activeEditorDiagnostics,
  onFileModified: (p) => checkAndHandleAgentFileConflict(p),
  onProblemOccurred: () => {
    bottomDockOpen.value = true;
    dockActiveTab.value = "problems";
  },
});
const effectiveTerminalLines = computed(() => props.terminalLines || []);
// Compatibility aliases for splitTab and splitTabPath
const splitTab = computed(() => pane2ActiveTab.value);
const splitTabPath = computed(() => pane2ActiveTabPath.value);

// Initialize split pane if requested via props
if (splitActive.value) {
  if (props.initialSplitTab) {
    openTab(pane2TabsState, props.initialSplitTab);
  } else {
    const other = pane1TabsState.tabs.value.find((t) => t.path !== pane1ActiveTabPath.value);
    if (other) {
      openTab(pane2TabsState, other);
    } else if (pane1ActiveTabPath.value) {
      const activeT = pane1TabsState.tabs.value.find((t) => t.path === pane1ActiveTabPath.value);
      if (activeT) openTab(pane2TabsState, activeT);
    }
  }
}

function toggleSplitEditor() {
  if (splitActive.value) {
    closeSplitEditor(false);
    return;
  }
  splitActive.value = true;
  splitRatio.value = 50;

  // Initialize Pane 2 with a tab if empty
  if (pane2TabsState.tabs.value.length === 0) {
    if (pane1TabsState.tabs.value.length > 1) {
      const other = pane1TabsState.tabs.value.find((t) => t.path !== pane1ActiveTabPath.value);
      if (other) {
        openTab(pane2TabsState, other);
      } else if (pane1ActiveTabPath.value) {
        const activeT = pane1TabsState.tabs.value.find((t) => t.path === pane1ActiveTabPath.value);
        if (activeT) openTab(pane2TabsState, activeT);
      }
    } else if (pane1ActiveTabPath.value) {
      const activeT = pane1TabsState.tabs.value.find((t) => t.path === pane1ActiveTabPath.value);
      if (activeT) openTab(pane2TabsState, activeT);
    }
  }
  activePane.value = "pane2";

  nextTick(() => {
    activeCodeEditorRef.value?.layout();
    splitCodeEditorRef.value?.layout();
  });
  setTimeout(() => {
    activeCodeEditorRef.value?.layout();
    splitCodeEditorRef.value?.layout();
  }, 80);
}

function toggleSplitDirection() {
  splitDirection.value = splitDirection.value === "vertical" ? "horizontal" : "vertical";
  nextTick(() => {
    activeCodeEditorRef.value?.layout();
    splitCodeEditorRef.value?.layout();
  });
  setTimeout(() => {
    activeCodeEditorRef.value?.layout();
    splitCodeEditorRef.value?.layout();
  }, 80);
}

function closeSplitEditor(force = false) {
  if (!force && hasDirtyTabs(pane2TabsState)) {
    const dirtyTab = pane2TabsState.tabs.value.find((t) => t.dirty);
    closingTab.value = dirtyTab;
    closingTabPane.value = "pane2";
    closingSplitEntirely.value = true;
    confirmCloseOpen.value = true;
    return;
  }
  pane2TabsState.tabs.value = [];
  pane2TabsState.activeTab.value = "";
  splitActive.value = false;
  activePane.value = "pane1";
  closingSplitEntirely.value = false;
  nextTick(() => {
    activeCodeEditorRef.value?.layout();
  });
}

function handleSelectSplitTab(path) {
  handleSelectTab(path, "pane2");
}

let isDraggingSplit = false;
function onSplitDividerMouseDown(e) {
  e.preventDefault();
  if (typeof window === "undefined") return;
  isDraggingSplit = true;
  const container = e.currentTarget.parentElement;
  if (!container) return;
  const rect = container.getBoundingClientRect();
  const isVert = effectiveSplitDirection.value === "vertical";

  function onMouseMove(moveEvt) {
    if (!isDraggingSplit) return;
    let pct;
    if (isVert) {
      pct = ((moveEvt.clientX - rect.left) / rect.width) * 100;
    } else {
      pct = ((moveEvt.clientY - rect.top) / rect.height) * 100;
    }
    splitRatio.value = Math.max(20, Math.min(80, Math.round(pct)));
    nextTick(() => {
      activeCodeEditorRef.value?.layout();
      splitCodeEditorRef.value?.layout();
    });
  }

  function onMouseUp() {
    isDraggingSplit = false;
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", onMouseUp);
  }

  window.addEventListener("mousemove", onMouseMove);
  window.addEventListener("mouseup", onMouseUp);
}

function onSplitDividerDblClick() {
  splitRatio.value = 50;
  nextTick(() => {
    activeCodeEditorRef.value?.layout();
    splitCodeEditorRef.value?.layout();
  });
}

// Project Root Display Name for Breadcrumbs
const projectRootName = computed(() => {
  if (props.activeProject) {
    return (
      props.activeProject.name ||
      String(props.activeProject.path || "").split("/").pop() ||
      "Project"
    );
  }
  return "Workspace";
});

// File Opening Handlers
function handleOpenFile(fileOrPath, targetPane) {
  const pane = targetPane || (splitActive.value && activePane.value === "pane2" ? "pane2" : "pane1");
  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;
  const tab = openTab(state, fileOrPath);
  if (tab) {
    activePane.value = pane;
    emit("open-file", tab);
    emit("active-file-change", tab);
    nextTick(() => {
      if (pane === "pane2") {
        splitCodeEditorRef.value?.layout();
      } else {
        activeCodeEditorRef.value?.layout();
      }
    });
  }
}

function handleOpenDiff(fileOrPath, targetPane) {
  const pane = targetPane || (splitActive.value && activePane.value === "pane2" ? "pane2" : "pane1");
  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;
  const tab = openDiffTab(state, fileOrPath);
  if (tab) {
    activePane.value = pane;
    emit("open-file", tab);
    emit("active-file-change", tab);
  }
}

function handleSelectTab(path, targetPane) {
  let pane = targetPane;
  if (!pane) {
    if (splitActive.value && activePane.value === "pane2" && pane2TabsState.tabs.value.some((t) => t.path === path)) {
      pane = "pane2";
    } else if (pane1TabsState.tabs.value.some((t) => t.path === path)) {
      pane = "pane1";
    } else if (pane2TabsState.tabs.value.some((t) => t.path === path)) {
      pane = "pane2";
    } else {
      pane = "pane1";
    }
  }
  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;
  selectTab(state, path);
  activePane.value = pane;
  const tab = getActiveTab(state);
  emit("active-file-change", tab);
  nextTick(() => {
    if (pane === "pane2") {
      splitCodeEditorRef.value?.layout();
    } else {
      activeCodeEditorRef.value?.layout();
    }
  });
}

const closingTab = ref(null);
const closingTabPane = ref("pane1");
const closingSplitEntirely = ref(false);
const confirmCloseOpen = ref(false);

function handleCloseTab(path, targetPane) {
  let pane = targetPane;
  if (!pane) {
    if (splitActive.value && activePane.value === "pane2" && pane2TabsState.tabs.value.some((t) => t.path === path)) {
      pane = "pane2";
    } else if (pane1TabsState.tabs.value.some((t) => t.path === path)) {
      pane = "pane1";
    } else if (pane2TabsState.tabs.value.some((t) => t.path === path)) {
      pane = "pane2";
    } else {
      pane = "pane1";
    }
  }

  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;
  const tab = state.tabs.value.find((t) => t.path === path);
  if (tab && tab.dirty) {
    closingTab.value = tab;
    closingTabPane.value = pane;
    closingSplitEntirely.value = false;
    confirmCloseOpen.value = true;
    return;
  }

  const result = closeTab(state, path);
  if (result.closed) {
    releaseModel(path);
    const editorRef = pane === "pane2" ? splitCodeEditorRef.value : activeCodeEditorRef.value;
    editorRef?.releasePath?.(path);
    if (pane === "pane2" && pane2TabsState.tabs.value.length === 0 && splitActive.value) {
      splitActive.value = false;
      activePane.value = "pane1";
    }
    const newActive = getActiveTab(state);
    emit("active-file-change", newActive);
  }
}

async function handleConfirmCloseSave() {
  if (!closingTab.value) return;
  const targetTab = closingTab.value;
  const pane = closingTabPane.value;
  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;
  const targetPath = targetTab.path;
  const currentActive = pane === "pane2" ? pane2ActiveTabPath.value : pane1ActiveTabPath.value;
  const editorRef = pane === "pane2" ? splitCodeEditorRef.value : activeCodeEditorRef.value;

  let saveSuccess = false;
  if (currentActive === targetPath && editorRef?.save) {
    saveSuccess = await editorRef.save();
  } else {
    const entry = getEntry(targetPath);
    if (entry?.model) {
      try {
        const content = entry.model.getValue ? entry.model.getValue() : "";
        await writeFileContent(targetPath, content);
        const versionId = entry.model.getAlternativeVersionId ? entry.model.getAlternativeVersionId() : 1;
        markSaved(targetPath, versionId);
        setTabDirty(pane1TabsState, targetPath, false);
        setTabDirty(pane2TabsState, targetPath, false);
        saveSuccess = true;
      } catch (err) {
        saveSuccess = false;
        showBgToast({
          type: "error",
          title: "Save Failed",
          message: err.message || "Gagal menyimpan berkas",
        });
      }
    }
  }

  if (!saveSuccess) {
    // JANGAN tutup tab jika penyimpanan gagal (AEG-02)
    return;
  }

  const result = closeTab(state, targetPath, { force: true });
  if (result.closed) {
    releaseModel(targetPath);
    editorRef?.releasePath?.(targetPath);
  }
  confirmCloseOpen.value = false;
  closingTab.value = null;

  if (closingSplitEntirely.value) {
    closeSplitEditor(false);
    return;
  }

  if (pane === "pane2" && pane2TabsState.tabs.value.length === 0 && splitActive.value) {
    splitActive.value = false;
    activePane.value = "pane1";
  }

  const newActive = getActiveTab(state);
  emit("active-file-change", newActive);
}

function handleConfirmCloseDiscard() {
  if (!closingTab.value) return;
  const targetPath = closingTab.value.path;
  const pane = closingTabPane.value;
  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;
  const editorRef = pane === "pane2" ? splitCodeEditorRef.value : activeCodeEditorRef.value;

  const result = closeTab(state, targetPath, { force: true });
  if (result.closed) {
    releaseModel(targetPath);
    editorRef?.releasePath?.(targetPath);
  }
  confirmCloseOpen.value = false;
  closingTab.value = null;

  if (closingSplitEntirely.value) {
    closeSplitEditor(true);
    return;
  }

  if (pane === "pane2" && pane2TabsState.tabs.value.length === 0 && splitActive.value) {
    splitActive.value = false;
    activePane.value = "pane1";
  }

  const newActive = getActiveTab(state);
  emit("active-file-change", newActive);
}

function handleConfirmCloseCancel() {
  confirmCloseOpen.value = false;
  closingTab.value = null;
  closingSplitEntirely.value = false;
}

function onEditorClose(path, targetPane) {
  handleCloseTab(path, targetPane);
}

function onEditorSaved(evt, pane = "pane1") {
  const path = evt?.path || (pane === "pane2" ? pane2ActiveTabPath.value : pane1ActiveTabPath.value);
  setTabSaved(pane1TabsState, path);
  setTabSaved(pane2TabsState, path);
  setTabConflict(pane1TabsState, path, false);
  setTabConflict(pane2TabsState, path, false);
  if (conflictFile.value === path) {
    conflictFile.value = null;
  }
}

function onEditorDirtyChange(evt, pane = "pane1") {
  const path = evt?.path || (pane === "pane2" ? pane2ActiveTabPath.value : pane1ActiveTabPath.value);
  const isDirtyVal = evt?.dirty !== undefined ? evt.dirty : true;
  setTabDirty(pane1TabsState, path, isDirtyVal);
  setTabDirty(pane2TabsState, path, isDirtyVal);
}

function onCursorChange(pos) {
  emit("cursor-change", pos);
}

function onEditorError(err) {
  // Bubbled or displayed by CodeEditor
}

// --- Git Discard Changes Mechanism (Direct Non-Overlay with Toast Notification) ---
const localGitRefresh = ref(0);

async function handleDirectDiscard(filePath = null) {
  const pId = props.activeProject?.id || props.activeProject?.project_id;
  if (!pId) return;

  try {
    const res = await discardProjectGitChanges(pId, filePath);
    if (!res?.ok && res?.error) {
      showBgToast({
        type: "error",
        title: "Discard Failed",
        message: res.error,
      });
      return;
    }

    if (filePath) {
      // 1. Close diff tab if open for this file in either pane
      closeTab(pane1TabsState, `diff://${filePath}`, { force: true });
      closeTab(pane2TabsState, `diff://${filePath}`, { force: true });

      // 2. If standard editor tab for this file is open, reload it
      const regularTab1 = pane1TabsState.tabs.value.find((t) => t.path === filePath);
      if (regularTab1) {
        setTabDirty(pane1TabsState, filePath, false);
        setTabConflict(pane1TabsState, filePath, false);
        if (pane1ActiveTabPath.value === filePath && activeCodeEditorRef.value?.reload) {
          activeCodeEditorRef.value.reload();
        }
      }
      const regularTab2 = pane2TabsState.tabs.value.find((t) => t.path === filePath);
      if (regularTab2) {
        setTabDirty(pane2TabsState, filePath, false);
        setTabConflict(pane2TabsState, filePath, false);
        if (pane2ActiveTabPath.value === filePath && splitCodeEditorRef.value?.reload) {
          splitCodeEditorRef.value.reload();
        }
      }
      if (conflictFile.value === filePath) {
        conflictFile.value = null;
      }

      showBgToast({
        type: "success",
        title: "Changes Discarded",
        message: `Reverted ${filePath} to HEAD.`,
      });
    } else {
      // Discard all: close all diff tabs in both panes
      pane1TabsState.tabs.value.filter((t) => t.isDiff).forEach((t) => closeTab(pane1TabsState, t.path, { force: true }));
      pane2TabsState.tabs.value.filter((t) => t.isDiff).forEach((t) => closeTab(pane2TabsState, t.path, { force: true }));

      // Clean dirty state and reload active editors if regular
      pane1TabsState.tabs.value.forEach((t) => {
        if (!t.isDiff) {
          setTabDirty(pane1TabsState, t.path, false);
          setTabConflict(pane1TabsState, t.path, false);
        }
      });
      pane2TabsState.tabs.value.forEach((t) => {
        if (!t.isDiff) {
          setTabDirty(pane2TabsState, t.path, false);
          setTabConflict(pane2TabsState, t.path, false);
        }
      });
      conflictFile.value = null;
      if (activeCodeEditorRef.value?.reload) {
        activeCodeEditorRef.value.reload();
      }
      if (splitCodeEditorRef.value?.reload) {
        splitCodeEditorRef.value.reload();
      }

      showBgToast({
        type: "success",
        title: "All Changes Discarded",
        message: "Reverted working tree to HEAD.",
      });
    }

    // 3. Trigger git refresh across FileExplorer and ChangesPanel
    localGitRefresh.value++;
    const newActive = activeTab.value;
    emit("active-file-change", newActive);
  } catch (e) {
    showBgToast({
      type: "error",
      title: "Discard Failed",
      message: e.message || "Failed to discard changes.",
    });
  }
}

function onMarkersChange(payload) {
  if (payload?.markers) {
    activeEditorMarkers.value = mapMonacoMarkersToDiagnostics(
      payload.markers,
      payload.path || activeTabPath.value
    );
  }
}

function onSyntaxChange(payload) {
  if (payload?.errors) {
    activeEditorSyntaxErrors.value = payload.errors;
  }
}

function onDiagnosticsUpdated(payload) {
  if (payload?.diagnostics) {
    activeEditorLinterDiagnostics.value = payload.diagnostics.map((d) => ({
      id: `lint-${d.file}-${d.line}-${d.col}-${Date.now()}`,
      text: d.message,
      type: d.severity === "error" ? "error" : (d.severity === "warning" ? "lint" : "info"),
      severity: d.severity,
      label: d.severity === "error" ? "Lint Error" : "Lint / Warning",
      file: d.file,
      line: d.line,
      col: d.col,
      endLine: d.end_line,
      endCol: d.end_col,
      source: d.source || "aegis-linter",
      ruleId: d.rule_id,
      ts: Date.now(),
    }));
  }
}

watch(activeTabPath, () => {
  activeEditorMarkers.value = [];
  activeEditorSyntaxErrors.value = [];
  activeEditorLinterDiagnostics.value = [];
});

async function handleNavigateToLocation(loc) {
  if (!loc) return;
  const targetFile = loc.file;
  const line = loc.line || 1;
  const col = loc.col || 1;

  if (targetFile && targetFile !== activeTabPath.value) {
    handleOpenFile(targetFile);
    await nextTick();
  }

  activeCodeEditorRef.value?.revealPosition(line, col);
}

const settingsSubTab = ref(props.settingsTab || "providers");
watch(
  () => props.settingsTab,
  (val) => {
    if (val) settingsSubTab.value = val;
  }
);

function openSettings(tabName = "providers") {
  settingsSubTab.value = tabName;
  activePane.value = "pane1";
  openTab(pane1TabsState, {
    path: "aegis://settings",
    name: "Settings",
  });
}

function openWelcomeTab() {
  openTab(editorTabsState, {
    path: "aegis://welcome",
    name: "Welcome",
  });
}

function clearAllTabs() {
  pane1TabsState.tabs.value.forEach((t) => releaseModel(t.path));
  pane2TabsState.tabs.value.forEach((t) => releaseModel(t.path));
  pane1TabsState.tabs.value = [];
  pane1TabsState.activeTab.value = "";
  pane2TabsState.tabs.value = [];
  pane2TabsState.activeTab.value = "";
  splitActive.value = false;
  activePane.value = "pane1";
  activeCodeEditorRef.value?.layout?.();
}

function restoreProjectContext(projectId) {
  if (!projectId) return;
  const ctx = loadWorkspaceContext(projectId);
  if (Array.isArray(ctx?.editor?.tabs) && ctx.editor.tabs.length > 0) {
    ctx.editor.tabs.forEach((t) => {
      if (t.isDiff) {
        openDiffTab(pane1TabsState, t.filePath || t.path);
      } else {
        openTab(pane1TabsState, t);
      }
    });
    if (ctx.editor.activeTab) {
      pane1TabsState.activeTab.value = ctx.editor.activeTab;
    }
  }
  if (ctx?.layout) {
    if (typeof ctx.layout.bottomDockOpen === "boolean") {
      bottomDockOpen.value = ctx.layout.bottomDockOpen;
    }
    if (ctx.layout.dockActiveTab) {
      dockActiveTab.value = ctx.layout.dockActiveTab;
    }
    if (typeof ctx.layout.dockHeight === "number") {
      dockHeight.value = ctx.layout.dockHeight;
    }
    if (ctx.layout.assistantTab) {
      assistantTab.value = ctx.layout.assistantTab;
    }
  }
}

watch(
  () => props.activeProject?.id,
  (newId, oldId) => {
    if (newId !== oldId) {
      clearAllTabs();
      if (newId) {
        restoreProjectContext(newId);
      }
    }
  },
  { immediate: true }
);

watch(
  [() => pane1TabsState.tabs.value, () => pane1TabsState.activeTab.value],
  () => {
    const pId = props.activeProject?.id;
    if (!pId) return;
    const serializedTabs = (pane1TabsState.tabs.value || [])
      .filter((t) => t.path && !t.path.startsWith("aegis://welcome"))
      .map((t) => ({
        path: t.path,
        filePath: t.filePath,
        name: t.name,
        isDiff: Boolean(t.isDiff),
      }));
    saveWorkspaceContext(pId, {
      editor: {
        tabs: serializedTabs,
        activeTab: pane1TabsState.activeTab.value || "activity",
      },
    });
  },
  { deep: true }
);

watch(
  [() => bottomDockOpen.value, () => dockActiveTab.value, () => dockHeight.value, () => assistantTab.value],
  () => {
    const pId = props.activeProject?.id;
    if (!pId) return;
    saveWorkspaceContext(pId, {
      layout: {
        bottomDockOpen: Boolean(bottomDockOpen.value),
        dockActiveTab: dockActiveTab.value || "terminal",
        dockHeight: Number(dockHeight.value) || 220,
        assistantTab: assistantTab.value || "agents",
      },
    });
  }
);

const cloneGitModalOpen = ref(false);
const cloneGitUrl = ref("");
const cloneGitBusy = ref(false);
const cloneGitNotice = ref("");

function handleOpenCloneGitModal() {
  cloneGitModalOpen.value = true;
  cloneGitNotice.value = "";
  cloneGitUrl.value = "";
}

function handleCloneGitSubmit() {
  const url = cloneGitUrl.value.trim();
  if (!url) return;
  const command = `git clone ${url}`;
  if (navigator?.clipboard?.writeText) {
    navigator.clipboard
      .writeText(command)
      .then(() => {
        cloneGitNotice.value = `Command copied to clipboard: "${command}". Run it in your terminal, then use "Open Folder".`;
      })
      .catch(() => {
        cloneGitNotice.value = `Run this in your terminal: "${command}", then use "Open Folder".`;
      });
  } else {
    cloneGitNotice.value = `Run this in your terminal: "${command}", then use "Open Folder".`;
  }
}

const isCurrentTabDirty = computed(() => {
  if (splitActive.value && activePane.value === "pane2") {
    return isPane2TabDirty.value;
  }
  return isPane1TabDirty.value;
});

async function handleSaveActiveFile(targetPane) {
  const pane = targetPane || (splitActive.value && activePane.value === "pane2" ? "pane2" : "pane1");
  const editorRef = pane === "pane2" ? splitCodeEditorRef.value : activeCodeEditorRef.value;
  if (editorRef?.save) {
    await editorRef.save();
  }
}

// 1-Click "Apply to Editor" Wiring
async function handleApplyToEditor(payload) {
  const code = payload?.code ?? "";
  const targetPath = payload?.path || activeTabPath.value || "scratchpad.js";
  const pane = splitActive.value && activePane.value === "pane2" ? "pane2" : "pane1";
  const state = pane === "pane2" ? pane2TabsState : pane1TabsState;

  // 1. Pastikan model targetPath ada di registry agar kode langsung terpasang pada model yang tepat
  let entry = getEntry(targetPath);
  if (!entry) {
    try {
      const data = await readFileContent(targetPath);
      const text = typeof data?.content === "string" ? data.content : "";
      const lang = languageForFile(targetPath);
      entry = getOrCreateModel(null, targetPath, text, lang);
    } catch {
      const lang = languageForFile(targetPath);
      entry = getOrCreateModel(null, targetPath, "", lang);
    }
  }

  // 2. Terapkan kode ke model (pushEditOperations menjaga riwayat undo)
  applyExternalContent(targetPath, code);

  // 3. Buka tab dan tandai dirty
  openTab(state, targetPath);
  setTabDirty(pane1TabsState, targetPath, true);
  setTabDirty(pane2TabsState, targetPath, true);

  emit("apply-to-editor", {
    code,
    path: targetPath,
    message: payload?.message,
  });
}

// Breadcrumb Navigation
function handleBreadcrumbNavigate(path) {
  if (!path) return;
  emit("open-path", path);
  emit("open-explorer");
}

function handleBreadcrumbSelect(path) {
  handleOpenFile(path);
}

// Bottom Dock Controls
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

const terminalRunning = ref(false);
function handleTerminalCommand() {}
function handleAbortCommand() {}

function closeOverlay() {
  emit("close-overlay");
}

// Global Keyboard Shortcuts
function onKeyDown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "`") {
    e.preventDefault();
    toggleBottomDock();
    return;
  }
  if (e.key === "Escape") {
    if (props.tier !== "desktop" && props.activeOverlay) {
      e.preventDefault();
      closeOverlay();
    }
  }
}

watch(
  [() => props.tier, effectiveSplitDirection],
  () => {
    nextTick(() => triggerEditorLayout());
  }
);

onMounted(() => {
  if (typeof window !== "undefined") {
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", triggerEditorLayout);
  }
});

onBeforeUnmount(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("keydown", onKeyDown);
    window.removeEventListener("resize", triggerEditorLayout);
  }
});

defineExpose({
  editorTabsState,
  pane1TabsState,
  pane2TabsState,
  activePane,
  activeTabPath,
  activeCodeEditorRef,
  splitActive,
  splitDirection,
  splitTabPath,
  splitCodeEditorRef,
  toggleSplitEditor,
  toggleSplitDirection,
  closeSplitEditor,
  bottomDockOpen,
  dockHeight,
  dockActiveTab,
  sidebarWidth,
  sidebarVisible,
  assistantWidth,
  assistantVisible,
  assistantTab,
  terminalLines: effectiveTerminalLines,
  outputLines: effectiveOutputLines,
  problems: effectiveProblems,
  terminalRunning,
  toggleSidebar,
  toggleAssistant,
  toggleBottomDock,
  handleOpenFile,
  handleOpenDiff,
  handleCloseTab,
  handleApplyToEditor,
  handleClearDock,
  handleTerminalCommand,
  handleAbortCommand,
  openSettings,
  openWelcomeTab,
  clearAllTabs,
  handleOpenAgentComposer,
  openComposer: handleOpenAgentComposer,
});
</script>

<template>
  <div
    class="workbench-view"
    :class="[`tier-${tier}`, { 'dock-open': bottomDockOpen }]"
  >
    <div class="workbench-columns">
      <!-- 1. Left Column: Project, Explorer & Source Control Sidebar -->
      <aside
        v-if="sidebarVisible"
        class="wb-left-column"
        :style="tier !== 'mobile' ? { width: `${sidebarWidth}px` } : {}"
      >
        <AppLeftSidebar
          :active-nav="activeNav"
          :active-project="activeProject"
          :projects="projects"
          :changes="changes"
          :validation="validation"
          :explorer-refresh="explorerRefresh + localGitRefresh"
          :live-fs-change="liveFsChange"
          :queue-refresh="queueRefresh"
          :task-history="taskHistory"
          :active-session-id="activeConsultantSessionId"
          :selected-project-id="selectedProjectId"
          :connected="connected"
          :gateway-address="gatewayAddress"
          :agent-status="agentStatus"
          :open-tabs="pane1TabsState.tabs.value"
          :active-tab-path="pane1TabsState.activeTab.value"
          :open-tabs2="pane2TabsState.tabs.value"
          :active-tab-path2="pane2TabsState.activeTab.value"
          :split-active="splitActive"
          :active-pane="activePane"
          @open-file="handleOpenFile"
          @open-diff="handleOpenDiff"
          @discard-change="handleDirectDiscard"
          @select-project="emit('select-project', $event)"
          @close-project="emit('close-project')"
          @collapse-sidebar="emit('toggle-sidebar', false)"
          @stop-task="emit('stop-task', $event)"
          @view-task="emit('view-task', $event)"
          @open-history-task="emit('open-history-task', $event)"
          @refresh-history="emit('refresh-history')"
          @delete-history="emit('delete-history', $event)"
          @open-session="handleOpenConsultantSession"
          @open-consultant-session="handleOpenConsultantSession"
          @open-folder="emit('open-folder')"
          @select-tab="(path, pane) => handleSelectTab(path, pane)"
          @close-tab="(path, pane) => handleCloseTab(path, pane)"
          @clear-tabs="(pane) => clearAllTabs(pane)"
          @branch-info-updated="emit('branch-info-updated', $event)"
        />
      </aside>

      <!-- Left Splitter (Desktop only) -->
      <AppSplitter
        v-if="tier === 'desktop' && sidebarVisible"
        direction="vertical"
        v-model="sidebarWidth"
        :min="200"
        :max="450"
        :default-size="260"
      />

      <!-- 2. Center Column: Monaco Tabs Strip, Breadcrumbs, Editor, Settings & Bottom Dock -->
      <main class="wb-center-column">
        <!-- Monaco Editor Tab Strip Bar (Single-window mode only) -->
        <div v-if="!splitActive && (activeProject || pane1TabsState.tabs.value.length > 0)" class="wb-editor-tabs-bar">
          <div class="wb-editor-tabs" role="tablist" aria-label="Editor Tabs">
            <div
              v-for="tab in pane1TabsState.tabs.value"
              :key="'single-' + tab.path"
              class="wb-tab-item"
              :class="{ active: tab.path === pane1ActiveTabPath, dirty: tab.dirty }"
              role="tab"
              :aria-selected="tab.path === pane1ActiveTabPath"
              @click="handleSelectTab(tab.path, 'pane1')"
            >
              <span class="tab-icon" aria-hidden="true">
                <svg
                  v-if="tab.path === 'aegis://settings'"
                  width="13"
                  height="13"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
                <svg
                  v-else-if="tab.path === 'aegis://welcome'"
                  width="13"
                  height="13"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <polygon points="12 2 2 7 12 12 22 7 12 2" />
                  <polyline points="2 17 12 22 22 17" />
                  <polyline points="2 12 12 17 22 12" />
                </svg>
                <svg
                  v-else-if="tab.isDiff || tab.path.startsWith('diff://')"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <path d="M12 3v18" />
                </svg>
                <svg
                  v-else
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <path d="M14 2v6h6" />
                </svg>
              </span>
              <span class="tab-title" :title="tab.path">{{ tab.name }}</span>
              <span v-if="tab.conflict" class="tab-conflict-dot" title="Agent modified this file while you have unsaved edits">!</span>
              <span v-if="tab.dirty" class="tab-dot" title="Unsaved changes">●</span>
              <button
                type="button"
                class="tab-close-btn"
                title="Close Tab"
                aria-label="Close Tab"
                @click.stop="handleCloseTab(tab.path, 'pane1')"
              >
                ×
              </button>

              <!-- Inline Popover for Agent Dirty Conflict -->
              <div
                v-if="conflictFile && tab.path === conflictFile"
                class="wb-conflict-popover"
                @click.stop
              >
                <div class="conflict-header">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                    <line x1="12" y1="9" x2="12" y2="13"/>
                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                  </svg>
                  <span>Agent modified this file</span>
                </div>
                <div class="conflict-diff-preview">
                  <span class="diff-stat-add">+{{ conflictAddedLines }} lines</span>
                  <span class="diff-stat-del">-{{ conflictRemovedLines }} lines</span>
                </div>
                <div class="conflict-actions">
                  <button type="button" class="conf-btn conf-keep" @click="resolveKeepMine">Keep Mine</button>
                  <button type="button" class="conf-btn conf-accept" @click="resolveAcceptAgent">Accept Agent</button>
                  <button type="button" class="conf-btn conf-diff" @click="resolveReviewDiff">Review Diff</button>
                </div>
              </div>

              <!-- Inline Popover for Unsaved Changes -->
              <div
                v-if="closingTab && closingTabPane === 'pane1' && closingTab.path === tab.path"
                class="wb-tab-inline-popover"
                @click.stop
              >
                <div class="pop-msg">Save changes?</div>
                <div class="pop-actions">
                  <button type="button" class="pop-btn pop-save" @click="handleConfirmCloseSave">Save</button>
                  <button type="button" class="pop-btn pop-discard" @click="handleConfirmCloseDiscard">Don't Save</button>
                  <button type="button" class="pop-btn pop-cancel" @click="handleConfirmCloseCancel">Cancel</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Actions toolbar: Compact Save and Split Buttons -->
          <div v-if="pane1ActiveTabPath && !['aegis://settings', 'aegis://welcome'].includes(pane1ActiveTabPath)" class="wb-tab-actions">
            <button
              type="button"
              class="wb-tab-save-btn"
              :class="{ dirty: isPane1TabDirty }"
              :disabled="!isPane1TabDirty"
              :title="isPane1TabDirty ? 'Save (⌘S)' : 'All changes saved'"
              aria-label="Save File"
              @click="handleSaveActiveFile('pane1')"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
                <polyline points="17 21 17 13 7 13 7 21"/>
                <polyline points="7 3 7 8 15 8"/>
              </svg>
              <span v-if="isPane1TabDirty" class="save-dot">●</span>
            </button>

            <!-- Split Editor Toggle Button -->
            <button
              type="button"
              class="wb-tab-action-btn wb-tab-split-btn"
              :class="{ active: splitActive }"
              :title="splitActive ? 'Close Split Editor' : 'Split Editor Right'"
              aria-label="Split Editor"
              @click="toggleSplitEditor"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                <line x1="12" y1="3" x2="12" y2="21"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Breadcrumbs Navigation Bar (Single-window mode only) -->
        <div v-if="!splitActive && pane1ActiveTabPath" class="wb-breadcrumbs-bar">
          <div v-if="pane1ActiveTabPath === 'aegis://settings'" class="breadcrumbs-list" aria-label="Settings Breadcrumbs">
            <span class="crumb-item crumb-root">Preferences</span>
            <span class="crumb-separator" aria-hidden="true">›</span>
            <span class="crumb-item crumb-file current">Settings</span>
          </div>
          <div v-else-if="pane1ActiveTabPath === 'aegis://welcome'" class="breadcrumbs-list" aria-label="Welcome Breadcrumbs">
            <span class="crumb-item crumb-root">AEGIS</span>
            <span class="crumb-separator" aria-hidden="true">›</span>
            <span class="crumb-item crumb-file current">Welcome</span>
          </div>
          <div v-else-if="pane1ActiveTab?.isDiff || pane1ActiveTabPath.startsWith('diff://')" class="breadcrumbs-list" aria-label="Diff Breadcrumbs">
            <span class="crumb-item crumb-root">{{ projectRootName }}</span>
            <span class="crumb-separator" aria-hidden="true">›</span>
            <span class="crumb-item crumb-file current">{{ pane1ActiveTab?.name || 'Diff' }}</span>
          </div>
          <AppBreadcrumbs
            v-else
            :path="pane1ActiveTabPath"
            :root="projectRootName"
            @navigate="handleBreadcrumbNavigate"
            @select-file="(p) => handleOpenFile(p, 'pane1')"
          />
        </div>

        <!-- Central Editor Surface / Settings Tab / Welcome / Empty State Canvas -->
        <div class="wb-editor-canvas">
          <!-- 1. Settings tab -->
          <div v-if="!splitActive && pane1ActiveTabPath === 'aegis://settings'" class="wb-settings-tab">
            <SettingsOverlay
              embedded
              :open="true"
              :config="config"
              :projects="projects"
              :task-history="taskHistory"
              :active-project="activeProject"
              :provider-instance-id="providerInstanceId"
              :model-id="modelId"
              :mode="config?.mode"
              v-model:active-tab="settingsSubTab"
              @close="handleCloseTab('aegis://settings', 'pane1')"
              @refresh-config="emit('refresh-config')"
              @update:provider-instance-id="emit('update:provider-instance-id', $event)"
              @update:model-id="emit('update:model-id', $event)"
              @update:mode="emit('update:mode', $event)"
              @open-report="emit('open-report', $event)"
              @open-history-task="emit('open-history-task', $event)"
              @delete-history="emit('delete-history', $event)"
              @clear-history="emit('clear-history')"
              @open-project-policy="emit('open-project-policy', $event)"
              @delete-project="emit('delete-project', $event)"
              @open-project="emit('open-project', $event)"
            />
          </div>

          <!-- 2. Dual-Window Split Editor (Side-by-side or Stacked) -->
          <div
            v-else-if="splitActive"
            class="wb-split-editor-container"
            :class="[
              `split-${effectiveSplitDirection}`,
              `split-tier-${tier}`,
              { 'pane-primary-active': activePane === 'pane1', 'pane-split-active': activePane === 'pane2' }
            ]"
          >
            <!-- Primary Editor Pane (Window 1 / Left) -->
            <div
              class="wb-split-pane wb-split-pane-primary"
              :class="{ 'is-focused-pane': activePane === 'pane1' }"
              :style="pane1Style"
              @click="activePane = 'pane1'"
            >
              <!-- Primary Pane Tab Strip -->
              <div class="wb-editor-tabs-bar wb-pane-tabs-bar">
                <div class="wb-editor-tabs" role="tablist" aria-label="Editor Window 1">
                  <div
                    v-for="tab in pane1TabsState.tabs.value"
                    :key="'p1-' + tab.path"
                    class="wb-tab-item"
                    :class="{ active: tab.path === pane1ActiveTabPath, dirty: tab.dirty }"
                    role="tab"
                    :aria-selected="tab.path === pane1ActiveTabPath"
                    @click.stop="handleSelectTab(tab.path, 'pane1')"
                  >
                    <span class="tab-icon" aria-hidden="true">
                      <svg
                        v-if="tab.isDiff || tab.path.startsWith('diff://')"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <rect x="3" y="3" width="18" height="18" rx="2" />
                        <path d="M12 3v18" />
                      </svg>
                      <svg
                        v-else
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <path d="M14 2v6h6" />
                      </svg>
                    </span>
                    <span class="tab-title" :title="tab.path">{{ tab.name }}</span>
                    <span v-if="tab.conflict" class="tab-conflict-dot" title="Agent modified this file while you have unsaved edits">!</span>
                    <span v-if="tab.dirty" class="tab-dot" title="Unsaved changes">●</span>
                    <button
                      type="button"
                      class="tab-close-btn"
                      title="Close Tab"
                      aria-label="Close Tab"
                      @click.stop="handleCloseTab(tab.path, 'pane1')"
                    >
                      ×
                    </button>

                    <!-- Inline Popover for Agent Dirty Conflict -->
                    <div
                      v-if="conflictFile && tab.path === conflictFile"
                      class="wb-conflict-popover"
                      @click.stop
                    >
                      <div class="conflict-header">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                          <line x1="12" y1="9" x2="12" y2="13"/>
                          <line x1="12" y1="17" x2="12.01" y2="17"/>
                        </svg>
                        <span>Agent modified this file</span>
                      </div>
                      <div class="conflict-diff-preview">
                        <span class="diff-stat-add">+{{ conflictAddedLines }} lines</span>
                        <span class="diff-stat-del">-{{ conflictRemovedLines }} lines</span>
                      </div>
                      <div class="conflict-actions">
                        <button type="button" class="conf-btn conf-keep" @click="resolveKeepMine">Keep Mine</button>
                        <button type="button" class="conf-btn conf-accept" @click="resolveAcceptAgent">Accept Agent</button>
                        <button type="button" class="conf-btn conf-diff" @click="resolveReviewDiff">Review Diff</button>
                      </div>
                    </div>

                    <!-- Inline Popover for Unsaved Changes -->
                    <div
                      v-if="closingTab && closingTabPane === 'pane1' && closingTab.path === tab.path"
                      class="wb-tab-inline-popover"
                      @click.stop
                    >
                      <div class="pop-msg">Save changes?</div>
                      <div class="pop-actions">
                        <button type="button" class="pop-btn pop-save" @click="handleConfirmCloseSave">Save</button>
                        <button type="button" class="pop-btn pop-discard" @click="handleConfirmCloseDiscard">Don't Save</button>
                        <button type="button" class="pop-btn pop-cancel" @click="handleConfirmCloseCancel">Cancel</button>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Primary Pane Actions Toolbar -->
                <div class="wb-tab-actions">
                  <button
                    v-if="pane1ActiveTabPath && !['aegis://settings', 'aegis://welcome'].includes(pane1ActiveTabPath)"
                    type="button"
                    class="wb-tab-save-btn"
                    :class="{ dirty: isPane1TabDirty }"
                    :disabled="!isPane1TabDirty"
                    :title="isPane1TabDirty ? 'Save (⌘S)' : 'All changes saved'"
                    aria-label="Save File"
                    @click.stop="handleSaveActiveFile('pane1')"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
                      <polyline points="17 21 17 13 7 13 7 21"/>
                      <polyline points="7 3 7 8 15 8"/>
                    </svg>
                    <span v-if="isPane1TabDirty" class="save-dot">●</span>
                  </button>

                  <!-- Split Direction Toggle -->
                  <button
                    type="button"
                    class="wb-tab-action-btn wb-tab-orient-btn"
                    :title="splitDirection === 'vertical' ? 'Switch to Horizontal Split (Stacked)' : 'Switch to Vertical Split (Side by Side)'"
                    aria-label="Toggle Split Direction"
                    @click.stop="toggleSplitDirection"
                  >
                    <svg v-if="splitDirection === 'vertical'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                      <line x1="3" y1="12" x2="21" y2="12"/>
                    </svg>
                    <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                      <line x1="12" y1="3" x2="12" y2="21"/>
                    </svg>
                  </button>
                </div>
              </div>

              <!-- Primary Breadcrumbs Bar -->
              <div v-if="pane1ActiveTabPath" class="wb-breadcrumbs-bar">
                <div v-if="pane1ActiveTabPath === 'aegis://settings'" class="breadcrumbs-list" aria-label="Settings Breadcrumbs">
                  <span class="crumb-item crumb-root">Preferences</span>
                  <span class="crumb-separator" aria-hidden="true">›</span>
                  <span class="crumb-item crumb-file current">Settings</span>
                </div>
                <div v-else-if="pane1ActiveTabPath === 'aegis://welcome'" class="breadcrumbs-list" aria-label="Welcome Breadcrumbs">
                  <span class="crumb-item crumb-root">AEGIS</span>
                  <span class="crumb-separator" aria-hidden="true">›</span>
                  <span class="crumb-item crumb-file current">Welcome</span>
                </div>
                <AppBreadcrumbs
                  v-else
                  :path="pane1ActiveTabPath"
                  :root="projectRootName"
                  @navigate="handleBreadcrumbNavigate"
                  @select-file="(p) => handleOpenFile(p, 'pane1')"
                />
              </div>

              <!-- Primary Editor Canvas -->
              <div class="wb-pane-editor-canvas">
                <div v-if="pane1ActiveTabPath === 'aegis://settings'" class="wb-settings-tab">
                  <SettingsOverlay
                    embedded
                    :open="true"
                    :config="config"
                    :projects="projects"
                    :task-history="taskHistory"
                    :active-project="activeProject"
                    :provider-instance-id="providerInstanceId"
                    :model-id="modelId"
                    :mode="config?.mode"
                    v-model:active-tab="settingsSubTab"
                    @close="handleCloseTab('aegis://settings', 'pane1')"
                    @refresh-config="emit('refresh-config')"
                    @update:provider-instance-id="emit('update:provider-instance-id', $event)"
                    @update:model-id="emit('update:model-id', $event)"
                    @update:mode="emit('update:mode', $event)"
                    @open-report="emit('open-report', $event)"
                    @open-history-task="emit('open-history-task', $event)"
                    @delete-history="emit('delete-history', $event)"
                    @clear-history="emit('clear-history')"
                    @open-project-policy="emit('open-project-policy', $event)"
                    @delete-project="emit('delete-project', $event)"
                  />
                </div>
                <MonacoDiffEditor
                  v-if="pane1ActiveTab?.isDiff || pane1ActiveTabPath.startsWith('diff://')"
                  :key="'p1-diff-' + pane1ActiveTabPath"
                  :path="pane1ActiveTabPath"
                  :file-path="pane1ActiveTab?.filePath"
                  :name="pane1ActiveTab?.name"
                  :project="activeProject"
                  instance-id="primary"
                  embedded
                  @edit-file="(f) => handleOpenFile(f, 'pane1')"
                  @discard="handleDirectDiscard"
                  @close="handleCloseTab(pane1ActiveTabPath, 'pane1')"
                />
                <CodeEditor
                  v-else-if="pane1ActiveTabPath"
                  ref="activeCodeEditorRef"
                  :path="pane1ActiveTabPath"
                  :project-id="activeProject?.id || ''"
                  instance-id="primary"
                  embedded
                  @saved="(e) => onEditorSaved(e, 'pane1')"
                  @dirty-change="(e) => onEditorDirtyChange(e, 'pane1')"
                  @cursor-change="onCursorChange"
                  @markers-change="onMarkersChange"
                  @syntax-change="onSyntaxChange"
                  @diagnostics-updated="onDiagnosticsUpdated"
                  @error="onEditorError"
                  @close="handleCloseTab(pane1ActiveTabPath, 'pane1')"
                />
                <div v-else class="empty-split-pane">
                  <p>No open tabs in Window 1</p>
                  <span>Select a file from Explorer to open</span>
                </div>
              </div>
            </div>

            <!-- Draggable / Responsive Split Divider -->
            <div
              class="wb-split-divider"
              :class="[`divider-${effectiveSplitDirection}`]"
              role="separator"
              :aria-orientation="effectiveSplitDirection"
              title="Drag to resize split, double click to center"
              @mousedown="onSplitDividerMouseDown"
              @dblclick="onSplitDividerDblClick"
            >
              <div class="divider-handle"></div>
            </div>

            <!-- Secondary Editor Pane (Window 2 / Right) -->
            <div
              class="wb-split-pane wb-split-pane-secondary"
              :class="{ 'is-focused-pane': activePane === 'pane2' }"
              :style="pane2Style"
              @click="activePane = 'pane2'"
            >
              <!-- Secondary Pane Tab Strip -->
              <div class="wb-editor-tabs-bar wb-pane-tabs-bar">
                <div class="wb-editor-tabs" role="tablist" aria-label="Editor Window 2">
                  <div
                    v-for="tab in pane2TabsState.tabs.value"
                    :key="'p2-' + tab.path"
                    class="wb-tab-item"
                    :class="{ active: tab.path === pane2ActiveTabPath, dirty: tab.dirty }"
                    role="tab"
                    :aria-selected="tab.path === pane2ActiveTabPath"
                    @click.stop="handleSelectTab(tab.path, 'pane2')"
                  >
                    <span class="tab-icon" aria-hidden="true">
                      <svg
                        v-if="tab.isDiff || tab.path.startsWith('diff://')"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <rect x="3" y="3" width="18" height="18" rx="2" />
                        <path d="M12 3v18" />
                      </svg>
                      <svg
                        v-else
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <path d="M14 2v6h6" />
                      </svg>
                    </span>
                    <span class="tab-title" :title="tab.path">{{ tab.name }}</span>
                    <span v-if="tab.conflict" class="tab-conflict-dot" title="Agent modified this file while you have unsaved edits">!</span>
                    <span v-if="tab.dirty" class="tab-dot" title="Unsaved changes">●</span>
                    <button
                      type="button"
                      class="tab-close-btn"
                      title="Close Tab"
                      aria-label="Close Tab"
                      @click.stop="handleCloseTab(tab.path, 'pane2')"
                    >
                      ×
                    </button>

                    <!-- Inline Popover for Agent Dirty Conflict -->
                    <div
                      v-if="conflictFile && tab.path === conflictFile"
                      class="wb-conflict-popover"
                      @click.stop
                    >
                      <div class="conflict-header">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                          <line x1="12" y1="9" x2="12" y2="13"/>
                          <line x1="12" y1="17" x2="12.01" y2="17"/>
                        </svg>
                        <span>Agent modified this file</span>
                      </div>
                      <div class="conflict-diff-preview">
                        <span class="diff-stat-add">+{{ conflictAddedLines }} lines</span>
                        <span class="diff-stat-del">-{{ conflictRemovedLines }} lines</span>
                      </div>
                      <div class="conflict-actions">
                        <button type="button" class="conf-btn conf-keep" @click="resolveKeepMine">Keep Mine</button>
                        <button type="button" class="conf-btn conf-accept" @click="resolveAcceptAgent">Accept Agent</button>
                        <button type="button" class="conf-btn conf-diff" @click="resolveReviewDiff">Review Diff</button>
                      </div>
                    </div>

                    <!-- Inline Popover for Unsaved Changes -->
                    <div
                      v-if="closingTab && closingTabPane === 'pane2' && closingTab.path === tab.path"
                      class="wb-tab-inline-popover"
                      @click.stop
                    >
                      <div class="pop-msg">Save changes?</div>
                      <div class="pop-actions">
                        <button type="button" class="pop-btn pop-save" @click="handleConfirmCloseSave">Save</button>
                        <button type="button" class="pop-btn pop-discard" @click="handleConfirmCloseDiscard">Don't Save</button>
                        <button type="button" class="pop-btn pop-cancel" @click="handleConfirmCloseCancel">Cancel</button>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Secondary Pane Actions Toolbar -->
                <div class="wb-tab-actions">
                  <button
                    v-if="pane2ActiveTabPath"
                    type="button"
                    class="wb-tab-save-btn"
                    :class="{ dirty: isPane2TabDirty }"
                    :disabled="!isPane2TabDirty"
                    :title="isPane2TabDirty ? 'Save (⌘S)' : 'All changes saved'"
                    aria-label="Save File"
                    @click.stop="handleSaveActiveFile('pane2')"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
                      <polyline points="17 21 17 13 7 13 7 21"/>
                      <polyline points="7 3 7 8 15 8"/>
                    </svg>
                    <span v-if="isPane2TabDirty" class="save-dot">●</span>
                  </button>

                  <!-- Close Split Pane Button -->
                  <button
                    type="button"
                    class="wb-tab-action-btn split-pane-close-btn"
                    title="Close Split Editor"
                    aria-label="Close Split Editor"
                    @click.stop="closeSplitEditor(false)"
                  >
                    <span style="font-size: 16px; line-height: 1;">×</span>
                  </button>
                </div>
              </div>

              <!-- Secondary Breadcrumbs Bar -->
              <div v-if="pane2ActiveTabPath" class="wb-breadcrumbs-bar split-breadcrumbs">
                <div v-if="pane2ActiveTabPath === 'aegis://settings'" class="breadcrumbs-list" aria-label="Settings Breadcrumbs">
                  <span class="crumb-item crumb-root">Preferences</span>
                  <span class="crumb-separator" aria-hidden="true">›</span>
                  <span class="crumb-item crumb-file current">Settings</span>
                </div>
                <div v-else-if="pane2ActiveTabPath === 'aegis://welcome'" class="breadcrumbs-list" aria-label="Welcome Breadcrumbs">
                  <span class="crumb-item crumb-root">AEGIS</span>
                  <span class="crumb-separator" aria-hidden="true">›</span>
                  <span class="crumb-item crumb-file current">Welcome</span>
                </div>
                <AppBreadcrumbs
                  v-else
                  :path="pane2ActiveTabPath"
                  :root="projectRootName"
                  @navigate="handleBreadcrumbNavigate"
                  @select-file="(p) => handleOpenFile(p, 'pane2')"
                />
              </div>

              <!-- Secondary Editor Canvas -->
              <div class="wb-pane-editor-canvas">
                <div v-if="pane2ActiveTabPath === 'aegis://settings'" class="wb-settings-tab">
                  <SettingsOverlay
                    embedded
                    :open="true"
                    :config="config"
                    :projects="projects"
                    :task-history="taskHistory"
                    :active-project="activeProject"
                    :provider-instance-id="providerInstanceId"
                    :model-id="modelId"
                    :mode="config?.mode"
                    v-model:active-tab="settingsSubTab"
                    @close="handleCloseTab('aegis://settings', 'pane2')"
                    @refresh-config="emit('refresh-config')"
                    @update:provider-instance-id="emit('update:provider-instance-id', $event)"
                    @update:model-id="emit('update:model-id', $event)"
                    @update:mode="emit('update:mode', $event)"
                    @open-report="emit('open-report', $event)"
                    @open-history-task="emit('open-history-task', $event)"
                    @delete-history="emit('delete-history', $event)"
                    @clear-history="emit('clear-history')"
                    @open-project-policy="emit('open-project-policy', $event)"
                    @delete-project="emit('delete-project', $event)"
                  />
                </div>
                <MonacoDiffEditor
                  v-if="pane2ActiveTab?.isDiff || pane2ActiveTabPath.startsWith('diff://')"
                  :key="'p2-diff-' + pane2ActiveTabPath"
                  :path="pane2ActiveTabPath"
                  :file-path="pane2ActiveTab?.filePath"
                  :name="pane2ActiveTab?.name"
                  :project="activeProject"
                  instance-id="split"
                  embedded
                  @edit-file="(f) => handleOpenFile(f, 'pane2')"
                  @discard="handleDirectDiscard"
                  @close="handleCloseTab(pane2ActiveTabPath, 'pane2')"
                />
                <CodeEditor
                  v-else-if="pane2ActiveTabPath"
                  ref="splitCodeEditorRef"
                  :path="pane2ActiveTabPath"
                  :project-id="activeProject?.id || ''"
                  instance-id="split"
                  embedded
                  @saved="(e) => onEditorSaved(e, 'pane2')"
                  @dirty-change="(e) => onEditorDirtyChange(e, 'pane2')"
                  @cursor-change="onCursorChange"
                  @markers-change="onMarkersChange"
                  @syntax-change="onSyntaxChange"
                  @diagnostics-updated="onDiagnosticsUpdated"
                  @error="onEditorError"
                  @close="handleCloseTab(pane2ActiveTabPath, 'pane2')"
                />
                <div v-else class="empty-split-pane">
                  <p>No open tabs in Window 2</p>
                  <span>Select a file from Explorer to open</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 3. Monaco Diff Editor (Git Working Tree vs HEAD - Read Only, Single Pane) -->
          <MonacoDiffEditor
            v-else-if="pane1ActiveTab?.isDiff || pane1ActiveTabPath.startsWith('diff://')"
            :key="'single-diff-' + pane1ActiveTabPath"
            :path="pane1ActiveTabPath"
            :file-path="pane1ActiveTab?.filePath"
            :name="pane1ActiveTab?.name"
            :project="activeProject"
            instance-id="primary"
            embedded
            @edit-file="(f) => handleOpenFile(f, 'pane1')"
            @discard="handleDirectDiscard"
            @close="handleCloseTab(pane1ActiveTabPath, 'pane1')"
          />

          <!-- 4. Code Editor (Monaco, Single Pane) -->
          <CodeEditor
            v-else-if="pane1ActiveTabPath"
            ref="activeCodeEditorRef"
            :path="pane1ActiveTabPath"
            :project-id="activeProject?.id || ''"
            instance-id="primary"
            embedded
            @saved="(e) => onEditorSaved(e, 'pane1')"
            @dirty-change="(e) => onEditorDirtyChange(e, 'pane1')"
            @cursor-change="onCursorChange"
            @markers-change="onMarkersChange"
            @syntax-change="onSyntaxChange"
            @diagnostics-updated="onDiagnosticsUpdated"
            @error="onEditorError"
            @close="handleCloseTab(pane1ActiveTabPath, 'pane1')"
          />

          <!-- 5. Active Workspace Empty Canvas (Zero tabs open, project active) -->
          <div v-else-if="activeProject" class="wb-welcome welcome-view-root">
            <div class="welcome-container">
              <div class="welcome-grid">
                <!-- Left Column: Hero & Start Actions -->
                <div class="welcome-col welcome-col-main">
                  <header class="welcome-card hero-card" aria-label="AegisCode Studio Overview">
                    <div class="welcome-hero">
                      <div class="hero-brand-row">
                        <div class="brand-logo-wrap" aria-hidden="true">
                          <svg
                            class="brand-logo-svg"
                            width="36"
                            height="36"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="1.8"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                          >
                            <path d="m4.5 8.5-3 3.5 3 3.5" />
                            <path d="m19.5 8.5 3 3.5-3 3.5" />
                            <path d="M12 3c.4 3.8 2.2 5.6 6 6-3.8.4-5.6 2.2-6 6-.4-3.8-2.2-5.6-6-6 3.8-.4 5.6-2.2 6-6Z" />
                            <circle cx="12" cy="12" r="1.5" fill="currentColor" />
                          </svg>
                        </div>
                        <div class="brand-text-block">
                          <h1 class="brand-title welcome-title">AegisCode Studio</h1>
                          <span class="version-tag">v0.2.05</span>
                        </div>
                      </div>
                      <p class="brand-tagline welcome-project">
                        {{ activeProject?.path || activeProject?.root || "No Project Selected" }}
                      </p>
                    </div>
                  </header>

                  <!-- Start Actions Card -->
                  <section class="welcome-card start-card" aria-labelledby="start-heading">
                    <h2 id="start-heading" class="card-heading">
                      <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        aria-hidden="true"
                      >
                        <polygon points="5 3 19 12 5 21 5 3" />
                      </svg>
                      <span>Start</span>
                    </h2>
                    <div class="action-buttons-list">
                      <button
                        type="button"
                        class="action-btn"
                        @click="handleOpenAgentComposer"
                      >
                        <svg
                          class="action-icon"
                          width="18"
                          height="18"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="1.8"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          aria-hidden="true"
                        >
                          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                        </svg>
                        <div class="action-btn-text">
                          <span class="btn-label">New Agent Task…</span>
                          <span class="btn-sub">Compose and run an autonomous AI agent task</span>
                        </div>
                      </button>

                      <button
                        type="button"
                        class="action-btn"
                        @click="toggleBottomDock()"
                      >
                        <svg
                          class="action-icon"
                          width="18"
                          height="18"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="1.8"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          aria-hidden="true"
                        >
                          <polyline points="4 17 10 11 4 5" />
                          <line x1="12" y1="19" x2="20" y2="19" />
                        </svg>
                        <div class="action-btn-text">
                          <span class="btn-label">Open Terminal…</span>
                          <span class="btn-sub">Toggle bottom shell terminal dock</span>
                        </div>
                      </button>
                    </div>
                  </section>
                </div>

                <!-- Right Column: Key Bindings -->
                <div class="welcome-col welcome-col-side">
                  <section class="welcome-card shortcuts-card" aria-labelledby="shortcuts-heading">
                    <h2 id="shortcuts-heading" class="card-heading">
                      <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        aria-hidden="true"
                      >
                        <rect x="2" y="4" width="20" height="16" rx="2" />
                        <path d="M6 8h.001M10 8h.001M14 8h.001M18 8h.001M8 12h.001M12 12h.001M16 12h.001M6 16h12" />
                      </svg>
                      <span>Key Bindings</span>
                    </h2>

                    <div class="shortcuts-grid">
                      <div class="shortcut-row">
                        <span class="sc-label">Quick Open File</span>
                        <span class="sc-kbd-group"><kbd>Cmd</kbd> + <kbd>P</kbd></span>
                      </div>
                      <div class="shortcut-row">
                        <span class="sc-label">Command Palette</span>
                        <span class="sc-kbd-group"><kbd>Cmd</kbd> + <kbd>K</kbd></span>
                      </div>
                      <div class="shortcut-row">
                        <span class="sc-label">Toggle Sidebar</span>
                        <span class="sc-kbd-group"><kbd>Cmd</kbd> + <kbd>B</kbd></span>
                      </div>
                      <div class="shortcut-row">
                        <span class="sc-label">Toggle AI Assistant</span>
                        <span class="sc-kbd-group"><kbd>Cmd</kbd> + <kbd>J</kbd></span>
                      </div>
                      <div class="shortcut-row">
                        <span class="sc-label">Toggle Terminal Dock</span>
                        <span class="sc-kbd-group"><kbd>Ctrl</kbd> + <kbd>`</kbd></span>
                      </div>
                    </div>
                  </section>
                </div>
              </div>
            </div>
          </div>

          <!-- 4. Standalone Fullscreen Getting Started View (No Active Project) -->
          <div v-else class="wb-getting-started-wrapper">
            <WelcomeView
              :projects="projects"
              :last-project="projects[0] || null"
              :active-project="null"
              @open-folder="emit('open-folder')"
              @clone-git="handleOpenCloneGitModal"
              @new-task="emit('open-folder')"
              @open-project="emit('select-project', $event)"
              @delete-project="emit('delete-project', $event)"
              @open-settings="openSettings('providers')"
            />
          </div>
        </div>

        <!-- Bottom Dock Splitter -->
        <AppSplitter
          v-if="bottomDockOpen"
          direction="horizontal"
          v-model="dockHeight"
          :min="150"
          :max="400"
          :default-size="220"
          inverted
        />

        <!-- Collapsible Bottom Dock -->
        <AppBottomDock
          :open="bottomDockOpen"
          :height="dockHeight"
          :active-tab="dockActiveTab"
          :terminal-lines="effectiveTerminalLines"
          :output-lines="effectiveOutputLines"
          :editor-diagnostics="activeEditorDiagnostics"
          :problems="effectiveProblems"
          :terminal-running="terminalRunning"
          :project-id="activeProject?.id || ''"
          @update:open="bottomDockOpen = $event"
          @update:active-tab="dockActiveTab = $event"
          @clear="handleClearDock"
          @close="bottomDockOpen = false"
          @navigate-to-location="handleNavigateToLocation"
        />
      </main>

      <!-- Right Splitter (Desktop only) -->
      <AppSplitter
        v-if="tier === 'desktop' && assistantVisible"
        direction="vertical"
        v-model="assistantWidth"
        :min="320"
        :max="650"
        :default-size="380"
        inverted
      />

      <!-- 3. Right Column: AI Assistant Drawer -->
      <aside
        v-show="assistantVisible"
        class="wb-right-column"
        :style="tier !== 'mobile' ? { width: `${assistantWidth}px` } : {}"
      >
        <AppRightDrawer
          ref="rightDrawerRef"
          v-model:active-tab="assistantTab"
          :task="task"
          :task-history="taskHistory"
          :task-tag="taskTag"
          :show-task-meta="showTaskMeta"
          :task-provider="effectiveTaskProvider"
          :task-model="effectiveTaskModel"
          :task-execution-label="taskExecutionLabel"
          :task-round-label="taskRoundLabel"
          :task-duration-label="taskDurationLabel"
          :task-timer-live="taskTimerLive"
          :show-task-telemetry="showTaskTelemetry"
          :task-llm-rounds="taskLlmRounds"
          :task-tool-calls="taskToolCalls"
          :task-tokens-label="taskTokensLabel"
          :task-tokens-tooltip="taskTokensTooltip"
          :lifecycle-steps="lifecycleSteps"
          :lifecycle-pct="lifecyclePct"
          :activity-phase="activityPhase"
          :activity-events="activityEvents"
          :show-reasoning="showReasoning"
          :activity-copied="activityCopied"
          :is-running="isRunning"
          :is-submitting="isSubmitting"
          :stop-in-progress="stopInProgress"
          :error="error"
          :consultant-props="effectiveConsultantProps"
          :providers="effectiveProviderList"
          :provider-instance-id="effectiveProviderInstanceId"
          :model-id="effectiveModelId"
          :mode="props.mode || props.config?.mode || 'balanced'"
          @close="toggleAssistant(false)"
          @open-composer="handleOpenAgentComposer"
          @request-stop="emit('request-stop')"
          @submit-task="emit('submit-task', $event)"
          @open-settings="emit('open-settings', $event)"
          @open-report="emit('open-report', $event)"
          @copy-activity="emit('copy-activity')"
          @run-consultant-task="handleRunConsultantTask"
          @consultant-event="handleConsultantEvent"
          @apply-to-editor="handleApplyToEditor"
          @update:provider-instance-id="emit('update:provider-instance-id', $event)"
          @update:model-id="emit('update:model-id', $event)"
          @update:mode="emit('update:mode', $event)"
          @update:active-session-id="activeConsultantSessionId = $event"
        />
      </aside>
    </div>

    <!-- Clone Git Repository Modal -->
    <AppModal
      v-if="cloneGitModalOpen"
      :model-value="cloneGitModalOpen"
      title="Clone Git Repository"
      max-width="480px"
      @close="cloneGitModalOpen = false"
    >
      <div class="clone-git-dialog">
        <p class="clone-git-desc">
          Direct Git clone via UI is coming soon. Enter a remote Git repository URL below to generate and copy the clone command.
        </p>
        <div class="form-group">
          <label class="form-label" for="git-repo-url">Repository URL</label>
          <input
            id="git-repo-url"
            v-model="cloneGitUrl"
            type="text"
            class="form-control mono"
            placeholder="https://github.com/username/repository.git"
            :disabled="cloneGitBusy"
            @keydown.enter="handleCloneGitSubmit"
          />
        </div>
        <div v-if="cloneGitNotice" class="clone-git-notice">
          {{ cloneGitNotice }}
        </div>
        <div class="clone-git-actions">
          <button
            type="button"
            class="btn btn-ghost"
            :disabled="cloneGitBusy"
            @click="cloneGitModalOpen = false"
          >
            Close
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="!cloneGitUrl.trim() || cloneGitBusy"
            @click="handleCloneGitSubmit"
          >
            <span>Copy Clone Command</span>
          </button>
        </div>
      </div>
    </AppModal>

    <!-- Background Task Completion Toast Notification -->
    <transition name="toast-slide">
      <div
        v-if="bgToast"
        class="wb-bg-toast"
        :class="`toast-${bgToast.type}`"
        role="alert"
      >
        <div class="toast-dot" :class="`dot-${bgToast.type}`"></div>
        <div class="toast-body">
          <div class="toast-title">{{ bgToast.title }}</div>
          <div v-if="bgToast.message" class="toast-msg">{{ bgToast.message }}</div>
        </div>
        <div class="toast-actions">
          <button
            type="button"
            class="toast-btn-action"
            @click="handleOpenToastAction"
          >
            Open
          </button>
          <button
            type="button"
            class="toast-btn-dismiss"
            title="Dismiss notification"
            aria-label="Dismiss notification"
            @click="bgToast = null"
          >
            ✕
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<style>
.clone-git-dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px 0;
}
.clone-git-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-dim, #888888);
  line-height: 1.4;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.form-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text, #cccccc);
}
.form-control {
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--bg-surface, #252526);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.1));
  color: var(--text-bright, #ffffff);
  font-size: 13px;
  outline: none;
}
.form-control:focus {
  border-color: var(--accent, #10f09a);
}
.clone-git-notice {
  font-size: 12px;
  color: var(--accent, #10f09a);
  background: rgba(16, 240, 154, 0.08);
  border: 1px solid rgba(16, 240, 154, 0.25);
  padding: 8px 12px;
  border-radius: 6px;
}
.clone-git-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}

/* Background Process Toast Notification */
.wb-bg-toast {
  position: absolute;
  bottom: 24px;
  right: 24px;
  z-index: 1050;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 280px;
  max-width: 420px;
  padding: 10px 14px;
  background: var(--bg-surface, #1e1d24);
  border: 1px solid var(--border-soft, #383447);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  font-size: 13px;
  color: var(--text-bright, #ffffff);
}

.toast-success {
  border-left: 4px solid var(--accent, #10f09a);
}

.toast-warning {
  border-left: 4px solid var(--color-warning, #f59e0b);
}

.toast-error {
  border-left: 4px solid var(--color-danger, #ef4444);
}

.toast-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-success {
  background: var(--accent, #10f09a);
  box-shadow: 0 0 6px var(--accent, #10f09a);
}

.dot-warning {
  background: var(--color-warning, #f59e0b);
  box-shadow: 0 0 6px var(--color-warning, #f59e0b);
}

.dot-error {
  background: var(--color-danger, #ef4444);
  box-shadow: 0 0 6px var(--color-danger, #ef4444);
}

.toast-body {
  flex: 1;
  min-width: 0;
}

.toast-title {
  font-weight: 600;
  font-size: 13px;
  line-height: 1.2;
}

.toast-msg {
  font-size: 11px;
  color: var(--text-dim, #999999);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toast-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.toast-btn-action {
  padding: 4px 10px;
  border-radius: 4px;
  background: var(--accent, #10f09a);
  color: #0b0f19;
  font-size: 11px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.toast-btn-action:hover {
  opacity: 0.9;
}

.toast-btn-dismiss {
  background: none;
  border: none;
  color: var(--text-dim, #888888);
  font-size: 13px;
  cursor: pointer;
  padding: 4px;
  line-height: 1;
  transition: color 0.15s ease;
}

.toast-btn-dismiss:hover {
  color: var(--text-bright, #ffffff);
}

.toast-slide-enter-active,
.toast-slide-leave-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.toast-slide-enter-from {
  opacity: 0;
  transform: translateY(16px) scale(0.96);
}

.toast-slide-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}

/* Conflict dot on tab strip */
.tab-conflict-dot {
  font-size: 11px;
  font-weight: 700;
  color: var(--danger, #ef4444);
  margin-left: 2px;
  line-height: 1;
}

/* Smart Conflict Popover */
.wb-conflict-popover {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 250;
  background: var(--bg-card, #1a1b26);
  border: 1px solid var(--danger, #ef4444);
  border-radius: 6px;
  padding: 10px 12px;
  min-width: 230px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
  cursor: default;
  text-align: left;
}

.conflict-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--danger, #ef4444);
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 6px;
}

.conflict-diff-preview {
  display: flex;
  gap: 10px;
  font-size: 11px;
  font-family: var(--mono, monospace);
  margin-bottom: 8px;
}

.diff-stat-add {
  color: var(--success, #4ec9b0);
}

.diff-stat-del {
  color: var(--danger, #ef4444);
}

.conflict-actions {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}

.conf-btn {
  font-size: 11px;
  font-weight: 500;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.conf-keep {
  background: var(--bg-panel, #24283b);
  color: var(--text, #c0caf5);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.12));
}

.conf-keep:hover {
  background: var(--bg-hover, rgba(255, 255, 255, 0.08));
}

.conf-accept {
  background: var(--accent, #7aa2f7);
  color: #0b0f19;
  border: none;
}

.conf-accept:hover {
  opacity: 0.9;
}

.conf-diff {
  background: transparent;
  color: var(--accent, #7aa2f7);
  border: 1px solid var(--accent, #7aa2f7);
}

.conf-diff:hover {
  background: rgba(122, 162, 247, 0.1);
}
</style>
