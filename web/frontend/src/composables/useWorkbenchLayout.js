/**
 * useWorkbenchLayout.js
 *
 * Mengelola state tata letak Workbench: sidebar width, assistant drawer width,
 * bottom dock height, visibilitas kolom, dan penyesuaian splitter constraints.
 */
import { ref, watch } from "vue";

export function useWorkbenchLayout(props, emit) {
  const sidebarWidth = ref(260);
  const sidebarVisible = ref(props.sidebarVisible ?? true);
  const assistantWidth = ref(380);
  const assistantVisible = ref(props.assistantVisible ?? true);
  const assistantTab = ref("agents");

  const bottomDockOpen = ref(false);
  const dockHeight = ref(220);
  const dockActiveTab = ref("terminal");

  watch(
    () => props.sidebarVisible,
    (val) => {
      if (typeof val === "boolean") sidebarVisible.value = val;
    }
  );

  watch(
    () => props.assistantVisible,
    (val) => {
      if (typeof val === "boolean") assistantVisible.value = val;
    }
  );

  function toggleSidebar(forceState) {
    if (typeof forceState === "boolean") {
      sidebarVisible.value = forceState;
    } else {
      sidebarVisible.value = !sidebarVisible.value;
    }
    if (emit) emit("toggle-sidebar", sidebarVisible.value);
  }

  function toggleAssistant(forceState) {
    if (typeof forceState === "boolean") {
      assistantVisible.value = forceState;
    } else {
      assistantVisible.value = !assistantVisible.value;
    }
    if (emit) emit("toggle-assistant", assistantVisible.value);
  }

  function toggleBottomDock(tab = "terminal") {
    if (!bottomDockOpen.value) {
      bottomDockOpen.value = true;
      if (tab) dockActiveTab.value = tab;
    } else if (tab && dockActiveTab.value !== tab) {
      dockActiveTab.value = tab;
    } else {
      bottomDockOpen.value = false;
    }
    if (emit) emit("toggle-dock", tab);
  }

  return {
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
  };
}
