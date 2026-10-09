/**
 * useProjectContext.js
 *
 * Mengelola state proyek aktif, daftar proyek, sinkronisasi git branch,
 * dan operasi buka/tutup/buat/hapus workspace proyek.
 */
import { ref, watch } from "vue";
import {
  getProjects,
  createProject,
  deleteProject,
  getActiveProject,
  setActiveProject,
  closeActiveProject,
  pickFolder,
  getProjectGitBranches,
} from "../api.js";
import {
  loadWorkspaceContext,
  saveGlobalActiveProjectId,
  getGlobalActiveProjectId,
} from "../services/workspaceContextService.js";

export function useProjectContext(options = {}) {
  const activeProject = ref(null);
  const projects = ref([]);
  const lastProject = ref(null);
  const launcherBusy = ref(false);
  const gitBranchInfo = ref(null);

  const error = options.error || ref("");
  const workspaceGen = options.workspaceGen;
  const activeNav = options.activeNav;
  const closeConfirmOpen = options.closeConfirmOpen;
  const workbenchRef = options.workbenchRef;
  const setWorkspaceProject = options.setWorkspaceProject;
  const fetchWorkspaceFiles = options.fetchWorkspaceFiles;
  const invalidateFileCache = options.invalidateFileCache;
  const resetTaskState = options.resetTaskState;
  const refreshAllConfig = options.refreshAllConfig;
  const refreshTaskHistory = options.refreshTaskHistory;
  const syncActiveRunningTask = options.syncActiveRunningTask;
  const handleViewTask = options.handleViewTask;
  const runningTaskId = options.runningTaskId;

  async function loadProjects() {
    launcherBusy.value = true;
    try {
      projects.value = (await getProjects())?.projects || [];
    } catch (err) {
      if (error) error.value = `Failed to load projects: ${err.message || err}`;
    } finally {
      launcherBusy.value = false;
    }
  }

  async function loadActiveProject() {
    try {
      const r = await getActiveProject();
      let p = r?.active_project || r?.project || null;
      if (!p) {
        const savedPid = getGlobalActiveProjectId();
        if (savedPid) {
          try {
            const res = await setActiveProject(savedPid);
            p = res?.active_project || res?.project || null;
          } catch (_) {}
        }
      }
      if (p) {
        activeProject.value = lastProject.value = p;
        saveGlobalActiveProjectId(p.id);
        if (typeof setWorkspaceProject === "function") setWorkspaceProject(p.id);
        if (typeof fetchWorkspaceFiles === "function") fetchWorkspaceFiles(true);
        const ctx = loadWorkspaceContext(p.id);
        if (ctx?.activeNav && activeNav) {
          activeNav.value = ctx.activeNav;
        }
      }
    } catch (_) {}
  }

  async function refreshGitBranchInfo() {
    const pId = activeProject.value?.id;
    if (!pId) {
      gitBranchInfo.value = null;
      return;
    }
    try {
      const data = await getProjectGitBranches(pId);
      gitBranchInfo.value = data?.branch_info || null;
    } catch {
      gitBranchInfo.value = null;
    }
  }

  watch(
    () => activeProject.value?.id,
    () => {
      refreshGitBranchInfo();
    },
    { immediate: true }
  );

  async function handleOpenProject(target) {
    if (!target) return;
    const id = typeof target === "string" ? target : target.id;
    if (!id) return;
    if (workspaceGen) workspaceGen.value += 1;
    launcherBusy.value = true;
    if (error) error.value = "";
    try {
      const res = await setActiveProject(id);
      activeProject.value =
        res?.active_project ||
        (typeof target === "object" ? target : null) ||
        projects.value.find((p) => p.id === id) ||
        null;
      lastProject.value = activeProject.value;
      saveGlobalActiveProjectId(id);
      if (typeof setWorkspaceProject === "function") setWorkspaceProject(id);
      if (typeof resetTaskState === "function") resetTaskState();
      workbenchRef?.value?.clearAllTabs?.();
      if (typeof invalidateFileCache === "function") invalidateFileCache(id);
      const ctx = loadWorkspaceContext(id);
      if (ctx?.activeNav && activeNav) {
        activeNav.value = ctx.activeNav;
      }
      if (typeof refreshAllConfig === "function") await refreshAllConfig();
      if (typeof refreshTaskHistory === "function") await refreshTaskHistory();
      if (typeof syncActiveRunningTask === "function") await syncActiveRunningTask();
      if (
        (!runningTaskId || !runningTaskId.value) &&
        ctx?.task?.viewedTaskId &&
        typeof handleViewTask === "function"
      ) {
        await handleViewTask(ctx.task.viewedTaskId);
      }
      if (typeof fetchWorkspaceFiles === "function") fetchWorkspaceFiles(true);
    } catch (err) {
      if (error) error.value = `Failed to open project: ${err.message || err}`;
    } finally {
      launcherBusy.value = false;
    }
  }

  async function handleCreateProject(name, path) {
    launcherBusy.value = true;
    try {
      const res = await createProject(name, path);
      const p = res?.project || res;
      if (p) {
        await loadProjects();
        await handleOpenProject(p);
      }
    } catch (err) {
      if (error) error.value = `Failed to create project: ${err.message || err}`;
    } finally {
      launcherBusy.value = false;
    }
  }

  async function handleDeleteProject(id) {
    try {
      await deleteProject(id);
      if (activeProject.value?.id === id) await handleCloseProject();
      await loadProjects();
    } catch (err) {
      if (error) error.value = `Failed to delete project: ${err.message || err}`;
    }
  }

  async function handleCloseProject() {
    if (workspaceGen) workspaceGen.value += 1;
    try {
      await closeActiveProject();
      activeProject.value = null;
      saveGlobalActiveProjectId(null);
      if (closeConfirmOpen) closeConfirmOpen.value = false;
      if (typeof setWorkspaceProject === "function") setWorkspaceProject(null);
      if (typeof resetTaskState === "function") resetTaskState();
      await loadProjects();
      workbenchRef?.value?.clearAllTabs?.();
      if (typeof invalidateFileCache === "function") invalidateFileCache();
    } catch (err) {
      if (error) error.value = `Failed to close project: ${err.message || err}`;
    }
  }

  async function handleOpenFolder() {
    launcherBusy.value = true;
    if (error) error.value = "";
    try {
      const res = await pickFolder();
      if (!res || !res.ok || !res.path) {
        if (res && res.reason !== "cancelled" && res.message && error) error.value = res.message;
        return;
      }
      const p = res.path;
      const exist = projects.value.find((x) => x.path === p || x.root === p);
      if (exist) {
        await handleOpenProject(exist.id);
        return;
      }
      const segs = String(p).split(/[\\/]+/).filter(Boolean);
      const n = segs.length ? segs[segs.length - 1] : "workspace";
      const cr = await createProject(n, p);
      const np = cr?.project || cr;
      await loadProjects();
      if (np?.id) await handleOpenProject(np.id);
    } catch (err) {
      if (error) error.value = `Failed to open folder: ${err.message || err}`;
    } finally {
      launcherBusy.value = false;
    }
  }

  return {
    activeProject,
    projects,
    lastProject,
    launcherBusy,
    gitBranchInfo,
    loadProjects,
    loadActiveProject,
    refreshGitBranchInfo,
    handleOpenProject,
    handleCreateProject,
    handleDeleteProject,
    handleCloseProject,
    handleOpenFolder,
  };
}
