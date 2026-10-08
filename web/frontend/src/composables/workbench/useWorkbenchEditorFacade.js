/**
 * useWorkbenchEditorFacade.js
 *
 * Facade composable mengorkestrasi siklus hidup editor Monaco, tab multi-pane,
 * pembagian split horizontal/vertikal, penanganan konflik edit eksternal,
 * diagnostik sintaks/linter, serta penyimpanan konteks workspace.
 */
import { ref, computed, watch, nextTick } from "vue";
import { useWorkbenchTabs } from "../useWorkbenchTabs.js";
import {
  openTab,
  openDiffTab,
  closeTab,
  selectTab,
  getActiveTab,
  hasDirtyTabs,
  setTabSaved,
  setTabDirty,
  setTabConflict,
} from "../../services/editorTabsService.js";
import {
  readFileContent,
  writeFileContent,
  discardProjectGitChanges,
} from "../../api.js";
import { languageForFile } from "../../editorLanguages.js";
import {
  getEntry,
  getOrCreateModel,
  releaseModel,
  markSaved,
  applyExternalContent,
} from "../../services/monacoModelRegistry.js";
import { mapMonacoMarkersToDiagnostics } from "../../services/diagnosticService.js";
import {
  loadWorkspaceContext,
  saveWorkspaceContext,
} from "../../services/workspaceContextService.js";

export function useWorkbenchEditorFacade(props, emit, options = {}) {
  const { showBgToast } = options;

  // 1. Editor Diagnostics
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

  // 2. Multi-Tab State & Monaco Tabs via useWorkbenchTabs
  const tabsComposables = useWorkbenchTabs(props);
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
    pane1ActiveTab,
    pane1ActiveTabPath,
    isPane1TabDirty,
    pane2ActiveTab,
    pane2ActiveTabPath,
    isPane2TabDirty,
    activeTab,
    activeTabPath,
  } = tabsComposables;

  // Async DOM Guard for triggerEditorLayout (debounced + requestAnimationFrame)
  function triggerEditorLayout() {
    if (typeof window === "undefined") return;
    requestAnimationFrame(() => {
      try {
        activeCodeEditorRef.value?.layout?.();
        splitCodeEditorRef.value?.layout?.();
      } catch {
        // Safe guard against unmounted layout race condition
      }
    });
  }

  const activeFile = computed(() => {
    const cur = activeTab.value;
    return cur ? { path: cur.path, content: cur.content || null } : null;
  });

  // Compatibility aliases
  const splitTab = computed(() => pane2ActiveTab.value);
  const splitTabPath = computed(() => pane2ActiveTabPath.value);

  // Initialize split pane if requested via props
  if (splitActive.value) {
    if (props.initialSplitTab) {
      openTab(pane2TabsState, props.initialSplitTab);
    } else {
      const other = pane1TabsState.tabs.value.find(
        (t) => t.path !== pane1ActiveTabPath.value
      );
      if (other) {
        openTab(pane2TabsState, other);
      } else if (pane1ActiveTabPath.value) {
        const activeT = pane1TabsState.tabs.value.find(
          (t) => t.path === pane1ActiveTabPath.value
        );
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
        const other = pane1TabsState.tabs.value.find(
          (t) => t.path !== pane1ActiveTabPath.value
        );
        if (other) {
          openTab(pane2TabsState, other);
        } else if (pane1ActiveTabPath.value) {
          const activeT = pane1TabsState.tabs.value.find(
            (t) => t.path === pane1ActiveTabPath.value
          );
          if (activeT) openTab(pane2TabsState, activeT);
        }
      } else if (pane1ActiveTabPath.value) {
        const activeT = pane1TabsState.tabs.value.find(
          (t) => t.path === pane1ActiveTabPath.value
        );
        if (activeT) openTab(pane2TabsState, activeT);
      }
    }
    activePane.value = "pane2";

    nextTick(() => {
      triggerEditorLayout();
    });
    setTimeout(() => {
      triggerEditorLayout();
    }, 80);
  }

  function toggleSplitDirection() {
    splitDirection.value =
      splitDirection.value === "vertical" ? "horizontal" : "vertical";
    nextTick(() => {
      triggerEditorLayout();
    });
    setTimeout(() => {
      triggerEditorLayout();
    }, 80);
  }

  const closingTab = ref(null);
  const closingTabPane = ref("pane1");
  const closingSplitEntirely = ref(false);
  const confirmCloseOpen = ref(false);

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
      triggerEditorLayout();
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
        triggerEditorLayout();
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
      triggerEditorLayout();
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
    const pane =
      targetPane ||
      (splitActive.value && activePane.value === "pane2" ? "pane2" : "pane1");
    const state = pane === "pane2" ? pane2TabsState : pane1TabsState;
    const tab = openTab(state, fileOrPath);
    if (tab) {
      activePane.value = pane;
      emit("open-file", tab);
      emit("active-file-change", tab);
      nextTick(() => {
        triggerEditorLayout();
      });
    }
  }

  function handleOpenDiff(fileOrPath, targetPane) {
    const pane =
      targetPane ||
      (splitActive.value && activePane.value === "pane2" ? "pane2" : "pane1");
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
      if (
        splitActive.value &&
        activePane.value === "pane2" &&
        pane2TabsState.tabs.value.some((t) => t.path === path)
      ) {
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
      triggerEditorLayout();
    });
  }

  function handleCloseTab(path, targetPane) {
    let pane = targetPane;
    if (!pane) {
      if (
        splitActive.value &&
        activePane.value === "pane2" &&
        pane2TabsState.tabs.value.some((t) => t.path === path)
      ) {
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
      const editorRef =
        pane === "pane2" ? splitCodeEditorRef.value : activeCodeEditorRef.value;
      editorRef?.releasePath?.(path);
      if (
        pane === "pane2" &&
        pane2TabsState.tabs.value.length === 0 &&
        splitActive.value
      ) {
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
    const currentActive =
      pane === "pane2" ? pane2ActiveTabPath.value : pane1ActiveTabPath.value;
    const editorRef =
      pane === "pane2" ? splitCodeEditorRef.value : activeCodeEditorRef.value;

    let saveSuccess = false;
    if (currentActive === targetPath && editorRef?.save) {
      saveSuccess = await editorRef.save();
    } else {
      const entry = getEntry(targetPath);
      if (entry?.model) {
        try {
          const content = entry.model.getValue ? entry.model.getValue() : "";
          await writeFileContent(targetPath, content);
          const versionId = entry.model.getAlternativeVersionId
            ? entry.model.getAlternativeVersionId()
            : 1;
          markSaved(targetPath, versionId);
          setTabDirty(pane1TabsState, targetPath, false);
          setTabDirty(pane2TabsState, targetPath, false);
          saveSuccess = true;
        } catch (err) {
          saveSuccess = false;
          if (showBgToast) {
            showBgToast({
              type: "error",
              title: "Save Failed",
              message: err.message || "Gagal menyimpan berkas",
            });
          }
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

    if (
      pane === "pane2" &&
      pane2TabsState.tabs.value.length === 0 &&
      splitActive.value
    ) {
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
    const editorRef =
      pane === "pane2" ? splitCodeEditorRef.value : activeCodeEditorRef.value;

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

    if (
      pane === "pane2" &&
      pane2TabsState.tabs.value.length === 0 &&
      splitActive.value
    ) {
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

  function onEditorSaved(evt, pane = "pane1") {
    const path =
      evt?.path ||
      (pane === "pane2"
        ? pane2ActiveTabPath.value
        : pane1ActiveTabPath.value);
    setTabSaved(pane1TabsState, path);
    setTabSaved(pane2TabsState, path);
    setTabConflict(pane1TabsState, path, false);
    setTabConflict(pane2TabsState, path, false);
    if (conflictFile.value === path) {
      conflictFile.value = null;
    }
  }

  function onEditorDirtyChange(evt, pane = "pane1") {
    const path =
      evt?.path ||
      (pane === "pane2"
        ? pane2ActiveTabPath.value
        : pane1ActiveTabPath.value);
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

  // --- Git Discard Changes Mechanism ---
  const localGitRefresh = ref(0);

  async function handleDirectDiscard(filePath = null) {
    const pId = props.activeProject?.id || props.activeProject?.project_id;
    if (!pId) return;

    try {
      const res = await discardProjectGitChanges(pId, filePath);
      if (!res?.ok && res?.error) {
        if (showBgToast) {
          showBgToast({
            type: "error",
            title: "Discard Failed",
            message: res.error,
          });
        }
        return;
      }

      if (filePath) {
        // Close diff tab if open for this file in either pane
        closeTab(pane1TabsState, `diff://${filePath}`, { force: true });
        closeTab(pane2TabsState, `diff://${filePath}`, { force: true });

        const regularTab1 = pane1TabsState.tabs.value.find(
          (t) => t.path === filePath
        );
        if (regularTab1) {
          setTabDirty(pane1TabsState, filePath, false);
          setTabConflict(pane1TabsState, filePath, false);
          if (
            pane1ActiveTabPath.value === filePath &&
            activeCodeEditorRef.value?.reload
          ) {
            activeCodeEditorRef.value.reload();
          }
        }
        const regularTab2 = pane2TabsState.tabs.value.find(
          (t) => t.path === filePath
        );
        if (regularTab2) {
          setTabDirty(pane2TabsState, filePath, false);
          setTabConflict(pane2TabsState, filePath, false);
          if (
            pane2ActiveTabPath.value === filePath &&
            splitCodeEditorRef.value?.reload
          ) {
            splitCodeEditorRef.value.reload();
          }
        }
        if (conflictFile.value === filePath) {
          conflictFile.value = null;
        }

        if (showBgToast) {
          showBgToast({
            type: "success",
            title: "Changes Discarded",
            message: `Reverted ${filePath} to HEAD.`,
          });
        }
      } else {
        // Discard all
        pane1TabsState.tabs.value
          .filter((t) => t.isDiff)
          .forEach((t) => closeTab(pane1TabsState, t.path, { force: true }));
        pane2TabsState.tabs.value
          .filter((t) => t.isDiff)
          .forEach((t) => closeTab(pane2TabsState, t.path, { force: true }));

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

        if (showBgToast) {
          showBgToast({
            type: "success",
            title: "All Changes Discarded",
            message: "Reverted working tree to HEAD.",
          });
        }
      }

      localGitRefresh.value++;
      const newActive = activeTab.value;
      emit("active-file-change", newActive);
    } catch (e) {
      if (showBgToast) {
        showBgToast({
          type: "error",
          title: "Discard Failed",
          message: e.message || "Failed to discard changes.",
        });
      }
    }
  }

  function handleCheckpointCreated(result) {
    localGitRefresh.value++;
    const diffTabs1 = pane1TabsState.tabs.value.filter((t) => t.isDiff);
    const diffTabs2 = pane2TabsState.tabs.value.filter((t) => t.isDiff);
    diffTabs1.forEach((t) => closeTab(pane1TabsState, t.path, { force: true }));
    diffTabs2.forEach((t) => closeTab(pane2TabsState, t.path, { force: true }));
    emit("checkpoint-created", result);
  }

  function handleStageChange({ path, unstage } = {}) {
    localGitRefresh.value++;
    if (showBgToast) {
      showBgToast({
        type: "success",
        title: unstage ? "Changes Unstaged" : "Changes Staged",
        message: path
          ? `${unstage ? "Unstaged" : "Staged"} ${path}.`
          : `${unstage ? "Unstaged all changes" : "Staged all changes"}.`,
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
        type:
          d.severity === "error"
            ? "error"
            : d.severity === "warning"
            ? "lint"
            : "info",
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
    triggerEditorLayout();
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
    if (ctx?.layout && options.restoreLayout) {
      options.restoreLayout(ctx.layout);
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

  const isCurrentTabDirty = computed(() => {
    if (splitActive.value && activePane.value === "pane2") {
      return isPane2TabDirty.value;
    }
    return isPane1TabDirty.value;
  });

  async function handleSaveActiveFile(targetPane) {
    const pane =
      targetPane ||
      (splitActive.value && activePane.value === "pane2" ? "pane2" : "pane1");
    const editorRef =
      pane === "pane2" ? splitCodeEditorRef.value : activeCodeEditorRef.value;
    if (editorRef?.save) {
      await editorRef.save();
    }
  }

  async function handleApplyToEditor(payload) {
    const code = payload?.code ?? "";
    const targetPath = payload?.path || activeTabPath.value || "scratchpad.js";
    const pane =
      splitActive.value && activePane.value === "pane2" ? "pane2" : "pane1";
    const state = pane === "pane2" ? pane2TabsState : pane1TabsState;

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

    applyExternalContent(targetPath, code);

    openTab(state, targetPath);
    setTabDirty(pane1TabsState, targetPath, true);
    setTabDirty(pane2TabsState, targetPath, true);

    emit("apply-to-editor", {
      code,
      path: targetPath,
      message: payload?.message,
    });
  }

  function handleBreadcrumbNavigate(path) {
    if (!path) return;
    emit("open-path", path);
    emit("open-explorer");
  }

  function handleBreadcrumbSelect(path) {
    handleOpenFile(path);
  }

  return {
    // Tab states
    pane1TabsState,
    pane2TabsState,
    editorTabsState,
    activeCodeEditorRef,
    splitCodeEditorRef,
    splitActive,
    splitDirection,
    splitRatio,
    activePane,
    splitTab,
    splitTabPath,
    effectiveSplitDirection,
    pane1Style,
    pane2Style,
    pane1ActiveTab,
    pane1ActiveTabPath,
    isPane1TabDirty,
    pane2ActiveTab,
    pane2ActiveTabPath,
    isPane2TabDirty,
    activeTab,
    activeTabPath,
    activeFile,
    isCurrentTabDirty,

    // Conflict
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

    // Diagnostics
    activeEditorMarkers,
    activeEditorSyntaxErrors,
    activeEditorLinterDiagnostics,
    activeEditorDiagnostics,
    onMarkersChange,
    onSyntaxChange,
    onDiagnosticsUpdated,

    // Split & Layout
    toggleSplitEditor,
    toggleSplitDirection,
    closeSplitEditor,
    handleSelectSplitTab,
    onSplitDividerMouseDown,
    onSplitDividerDblClick,
    triggerEditorLayout,

    // Tab handlers
    handleOpenFile,
    handleOpenDiff,
    handleSelectTab,
    handleCloseTab,
    handleConfirmCloseSave,
    handleConfirmCloseDiscard,
    handleConfirmCloseCancel,
    closingTab,
    closingTabPane,
    closingSplitEntirely,
    confirmCloseOpen,
    onEditorSaved,
    onEditorDirtyChange,
    onCursorChange,
    onEditorError,

    // Actions
    handleSaveActiveFile,
    handleApplyToEditor,
    handleDirectDiscard,
    handleCheckpointCreated,
    handleStageChange,
    localGitRefresh,
    handleNavigateToLocation,
    handleBreadcrumbNavigate,
    handleBreadcrumbSelect,

    // Settings & Context
    projectRootName,
    settingsSubTab,
    openSettings,
    openWelcomeTab,
    clearAllTabs,
    restoreProjectContext,
  };
}
