<script setup>
import { ref, computed, watch } from "vue";
import AppButton from "../ui/AppButton.vue";
import {
  checkoutProjectGitBranch,
  createProjectGitBranch,
  deleteProjectGitBranch,
  mergeProjectGitBranch,
  stashProjectGitChanges,
  listProjectGitStashes,
  popProjectGitStash,
  applyProjectGitStash,
  dropProjectGitStash,
  pushProjectGit,
  pullProjectGit,
  fetchProjectGit,
  getProjectGitRemotes,
  addProjectGitRemote,
  cloneProjectGit,
  getGithubConfig,
  saveGithubConfig,
  testGithubConnection,
  deinitProjectGit,
} from "../../api.js";

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
  action: {
    type: String,
    default: "create_branch", // 'create_branch' | 'switch_branch' | 'delete_branch' | 'merge' | 'stash' | 'manage_stashes' | 'push' | 'pull' | 'fetch' | 'clone' | 'manage_remotes'
  },
  project: {
    type: Object,
    default: null,
  },
  branchInfo: {
    type: Object,
    default: () => ({}),
  },
});

const emit = defineEmits(["close", "success"]);

const busy = ref(false);
const error = ref("");
const searchFilter = ref("");

// Form state
const branchName = ref("");
const startPoint = ref("");
const checkoutAfterCreate = ref(true);
const forceDelete = ref(false);
const isRemoteDelete = ref(false);
const deleteRemoteName = ref("origin");
const targetBranch = ref("");
const mergeMessage = ref("");
const mergeNoFf = ref(false);
const stashMessage = ref("");
const stashIncludeUntracked = ref(true);
const pushRemote = ref("origin");
const pushBranch = ref("");
const pushSetUpstream = ref(false);
const pushForce = ref(false);
const pullRemote = ref("origin");
const pullBranch = ref("");
const pullRebase = ref(false);
const fetchRemote = ref("");
const fetchPrune = ref(true);
const cloneUrl = ref("");
const cloneTargetDir = ref("");
const newRemoteName = ref("origin");
const newRemoteUrl = ref("");
const configForm = ref({
  repository: "",
  branch: "main",
  token: "",
  excludeText: "",
});
const configNotice = ref("");
const testConnectionBusy = ref(false);
const saveConfigBusy = ref(false);
const confirmDeinit = ref(false);
const deinitBusy = ref(false);

// Stashes and remotes list state
const stashes = ref([]);
const remotesList = ref([]);

const pId = computed(() => props.project?.id || props.project?.project_id);

const localBranches = computed(() => props.branchInfo?.local_branches || []);
const remoteBranches = computed(() => props.branchInfo?.remote_branches || []);
const currentBranch = computed(() => props.branchInfo?.current || "main");

const modalTitle = computed(() => {
  switch (props.action) {
    case "create_branch":
      return "Create New Branch";
    case "switch_branch":
      return "Switch / Checkout Branch";
    case "delete_branch":
      return "Delete Branch";
    case "merge":
      return `Merge into '${currentBranch.value}'`;
    case "stash":
      return "Stash Changes";
    case "manage_stashes":
      return "Git Stashes";
    case "push":
      return "Push to Remote";
    case "pull":
      return "Pull from Remote";
    case "fetch":
      return "Fetch from Remote";
    case "clone":
      return "Clone Repository";
    case "manage_remotes":
      return "Manage Remotes";
    case "remote_settings":
      return "Remote & Authentication Settings";
    default:
      return "Git Operation";
  }
});

const filteredLocalBranches = computed(() => {
  const q = searchFilter.value.trim().toLowerCase();
  if (!q) return localBranches.value;
  return localBranches.value.filter((b) => b.toLowerCase().includes(q));
});

const filteredRemoteBranches = computed(() => {
  const q = searchFilter.value.trim().toLowerCase();
  if (!q) return remoteBranches.value;
  return remoteBranches.value.filter((b) => b.toLowerCase().includes(q));
});

watch(
  () => [props.show, props.action],
  async ([show, act]) => {
    if (!show) return;
    error.value = "";
    searchFilter.value = "";
    branchName.value = "";
    startPoint.value = currentBranch.value;
    checkoutAfterCreate.value = true;
    forceDelete.value = false;
    isRemoteDelete.value = false;
    deleteRemoteName.value = "origin";
    targetBranch.value = "";
    mergeMessage.value = "";
    mergeNoFf.value = false;
    stashMessage.value = "";
    stashIncludeUntracked.value = true;
    pushRemote.value = "origin";
    pushBranch.value = currentBranch.value;
    pushSetUpstream.value = !props.branchInfo?.upstream;
    pushForce.value = false;
    pullRemote.value = "origin";
    pullBranch.value = currentBranch.value;
    pullRebase.value = false;
    fetchRemote.value = "";
    fetchPrune.value = true;
    cloneUrl.value = "";
    cloneTargetDir.value = "";
    newRemoteName.value = "origin";
    newRemoteUrl.value = "";

    if (act === "manage_stashes") {
      await loadStashes();
    } else if (act === "manage_remotes") {
      await loadRemotes();
    } else if (act === "remote_settings") {
      await loadRemoteSettings();
    }
  }
);

async function loadStashes() {
  if (!pId.value) return;
  busy.value = true;
  try {
    const res = await listProjectGitStashes(pId.value);
    stashes.value = res?.stashes || [];
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function loadRemotes() {
  if (!pId.value) return;
  busy.value = true;
  try {
    const res = await getProjectGitRemotes(pId.value);
    remotesList.value = res?.remotes || [];
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function handleCreateBranch() {
  if (!branchName.value.trim()) {
    error.value = "Branch name is required.";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const res = await createProjectGitBranch(
      pId.value,
      branchName.value.trim(),
      startPoint.value.trim() || null,
      checkoutAfterCreate.value
    );
    if (!res.ok) {
      error.value = res.error || "Failed to create branch.";
      return;
    }
    emit("success", { message: `Branch '${branchName.value.trim()}' created successfully.` });
    emit("close");
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function handleSwitchBranch(target) {
  const b = target || targetBranch.value;
  if (!b) return;
  busy.value = true;
  error.value = "";
  try {
    const res = await checkoutProjectGitBranch(pId.value, b);
    if (!res.ok) {
      error.value = res.error || `Failed to switch to branch '${b}'.`;
      return;
    }
    emit("success", { message: `Switched to branch '${b}'.` });
    emit("close");
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function handleDeleteBranch() {
  if (!targetBranch.value) {
    error.value = "Please select a branch to delete.";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const res = await deleteProjectGitBranch(
      pId.value,
      targetBranch.value,
      forceDelete.value,
      isRemoteDelete.value,
      deleteRemoteName.value
    );
    if (!res.ok) {
      error.value = res.error || `Failed to delete branch '${targetBranch.value}'.`;
      return;
    }
    emit("success", { message: `Branch '${targetBranch.value}' deleted successfully.` });
    emit("close");
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function handleMerge() {
  if (!targetBranch.value) {
    error.value = "Please select a branch to merge.";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const res = await mergeProjectGitBranch(
      pId.value,
      targetBranch.value,
      mergeMessage.value.trim() || null,
      mergeNoFf.value
    );
    if (!res.ok) {
      error.value = res.error || `Merge conflict or failure while merging '${targetBranch.value}'.`;
      return;
    }
    emit("success", { message: `Successfully merged '${targetBranch.value}' into '${currentBranch.value}'.` });
    emit("close");
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function handleStash() {
  busy.value = true;
  error.value = "";
  try {
    const res = await stashProjectGitChanges(
      pId.value,
      stashMessage.value.trim() || null,
      stashIncludeUntracked.value
    );
    if (!res.ok) {
      error.value = res.error || "Failed to stash changes.";
      return;
    }
    emit("success", { message: "Changes stashed successfully." });
    emit("close");
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function handlePopStash(idx) {
  busy.value = true;
  error.value = "";
  try {
    const res = await popProjectGitStash(pId.value, idx);
    if (!res.ok) {
      error.value = res.error || `Failed to pop stash@{${idx}}.`;
      return;
    }
    emit("success", { message: `Stash@{${idx}} popped successfully.` });
    await loadStashes();
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function handleApplyStash(idx) {
  busy.value = true;
  error.value = "";
  try {
    const res = await applyProjectGitStash(pId.value, idx);
    if (!res.ok) {
      error.value = res.error || `Failed to apply stash@{${idx}}.`;
      return;
    }
    emit("success", { message: `Stash@{${idx}} applied successfully.` });
    await loadStashes();
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function handleDropStash(idx) {
  busy.value = true;
  error.value = "";
  try {
    const res = await dropProjectGitStash(pId.value, idx);
    if (!res.ok) {
      error.value = res.error || `Failed to drop stash@{${idx}}.`;
      return;
    }
    emit("success", { message: `Stash@{${idx}} dropped.` });
    await loadStashes();
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function handlePush() {
  busy.value = true;
  error.value = "";
  try {
    const res = await pushProjectGit(
      pId.value,
      pushRemote.value.trim() || null,
      pushBranch.value.trim() || null,
      pushSetUpstream.value,
      pushForce.value
    );
    if (!res.ok) {
      error.value = res.error || "Git push failed.";
      return;
    }
    emit("success", { message: "Push completed successfully." });
    emit("close");
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function handlePull() {
  busy.value = true;
  error.value = "";
  try {
    const res = await pullProjectGit(
      pId.value,
      pullRemote.value.trim() || null,
      pullBranch.value.trim() || null,
      pullRebase.value
    );
    if (!res.ok) {
      error.value = res.error || "Git pull failed.";
      return;
    }
    emit("success", { message: "Pull completed successfully." });
    emit("close");
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function handleFetch() {
  busy.value = true;
  error.value = "";
  try {
    const res = await fetchProjectGit(
      pId.value,
      fetchRemote.value.trim() || null,
      fetchPrune.value
    );
    if (!res.ok) {
      error.value = res.error || "Git fetch failed.";
      return;
    }
    emit("success", { message: "Fetch completed successfully." });
    emit("close");
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function handleClone() {
  if (!cloneUrl.value.trim()) {
    error.value = "Repository URL is required.";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const res = await cloneProjectGit(
      pId.value,
      cloneUrl.value.trim(),
      cloneTargetDir.value.trim() || null
    );
    if (!res.ok) {
      error.value = res.error || "Git clone failed.";
      return;
    }
    emit("success", { message: "Repository cloned successfully." });
    emit("close");
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function handleAddRemote() {
  if (!newRemoteName.value.trim() || !newRemoteUrl.value.trim()) {
    error.value = "Remote name and URL are required.";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const res = await addProjectGitRemote(
      pId.value,
      newRemoteName.value.trim(),
      newRemoteUrl.value.trim()
    );
    if (!res.ok) {
      error.value = res.error || "Failed to add remote.";
      return;
    }
    emit("success", { message: `Remote '${newRemoteName.value.trim()}' added.` });
    newRemoteName.value = "";
    newRemoteUrl.value = "";
    await loadRemotes();
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function loadRemoteSettings() {
  if (!pId.value) return;
  busy.value = true;
  configNotice.value = "";
  confirmDeinit.value = false;
  try {
    const cfg = await getGithubConfig(pId.value);
    configForm.value.repository = cfg?.repository || "";
    configForm.value.branch = cfg?.branch || "main";
    configForm.value.token = "";
    configForm.value.excludeText = (cfg?.exclude || []).join("\n");
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    busy.value = false;
  }
}

async function handleTestRemote() {
  if (!pId.value) return;
  testConnectionBusy.value = true;
  error.value = "";
  configNotice.value = "";
  try {
    const payload = {
      repository: configForm.value.repository,
      branch: configForm.value.branch,
    };
    if (configForm.value.token) payload.token = configForm.value.token;
    const res = await testGithubConnection(pId.value, payload);
    if (res?.ok) {
      configNotice.value = res.message || "Connected successfully.";
    } else {
      error.value = res?.message || "Connection failed.";
    }
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    testConnectionBusy.value = false;
  }
}

async function handleSaveRemote() {
  if (!pId.value) return;
  saveConfigBusy.value = true;
  error.value = "";
  configNotice.value = "";
  try {
    const exclude = configForm.value.excludeText
      .split("\n")
      .map((s) => s.trim())
      .filter((s) => s && !s.startsWith("#"));
    const payload = {
      repository: configForm.value.repository,
      branch: configForm.value.branch,
      exclude,
    };
    if (configForm.value.token) payload.token = configForm.value.token;
    await saveGithubConfig(pId.value, payload);
    emit("success", { message: "Remote configuration saved securely." });
    emit("close");
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    saveConfigBusy.value = false;
  }
}

async function handleDeinit() {
  if (!pId.value) return;
  deinitBusy.value = true;
  error.value = "";
  try {
    const res = await deinitProjectGit(pId.value);
    if (res?.ok) {
      emit("success", { message: "Git repository de-initialized successfully." });
      emit("close");
    } else {
      error.value = res?.error || "Failed to de-initialize Git repository.";
    }
  } catch (err) {
    error.value = err.message || String(err);
  } finally {
    deinitBusy.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="unified-popup-backdrop git-dialog-backdrop"
      @click.self="emit('close')"
    >
      <div
        class="unified-popup-card git-dialog-card"
        role="dialog"
        aria-modal="true"
        :aria-label="modalTitle"
      >
        <!-- Modal Head -->
        <div class="unified-popup-head git-dialog-head">
          <div class="unified-popup-meta">
            <span class="unified-popup-title">{{ modalTitle }}</span>
          </div>
          <AppButton
            variant="ghost"
            size="sm"
            class="unified-popup-close-btn"
            title="Close dialog"
            aria-label="Close dialog"
            @click="emit('close')"
          >
            &times;
          </AppButton>
        </div>

        <!-- Alert Error -->
        <div v-if="error" class="git-dialog-error">
          <span>{{ error }}</span>
          <button type="button" class="git-dialog-error-close" @click="error = ''">&times;</button>
        </div>

        <!-- Alert Notice -->
        <div v-if="configNotice" class="git-dialog-notice">
          <span>{{ configNotice }}</span>
          <button type="button" class="git-dialog-error-close" @click="configNotice = ''">&times;</button>
        </div>

        <!-- Modal Body -->
        <div class="unified-popup-body git-dialog-body">
          <!-- 1. CREATE BRANCH -->
          <div v-if="action === 'create_branch'" class="git-form-stack">
            <label class="git-field">
              <span class="git-field-label">Branch Name</span>
              <input
                v-model="branchName"
                class="git-input mono"
                placeholder="e.g. feature/new-module or fix/bug-1"
                autofocus
                @keydown.enter="handleCreateBranch"
              />
            </label>
            <label class="git-field">
              <span class="git-field-label">Start Point (Base)</span>
              <input
                v-model="startPoint"
                class="git-input mono"
                placeholder="HEAD or branch name"
              />
            </label>
            <label class="git-checkbox-label">
              <input v-model="checkoutAfterCreate" type="checkbox" class="git-checkbox" />
              <span>Checkout branch immediately after creation</span>
            </label>
          </div>

          <!-- 2. SWITCH / CHECKOUT BRANCH -->
          <div v-else-if="action === 'switch_branch'" class="git-form-stack">
            <div class="git-search-box">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <input
                v-model="searchFilter"
                class="git-search-input"
                placeholder="Search branches..."
                autofocus
              />
            </div>

            <!-- Local Branches List -->
            <div class="git-branch-section-title">LOCAL BRANCHES</div>
            <div class="git-branch-select-list">
              <div
                v-for="b in filteredLocalBranches"
                :key="b"
                class="git-branch-item"
                :class="{ active: b === currentBranch }"
                @click="handleSwitchBranch(b)"
              >
                <div class="git-branch-item-name mono">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>
                  </svg>
                  <span>{{ b }}</span>
                </div>
                <span v-if="b === currentBranch" class="git-active-badge">current</span>
              </div>
              <div v-if="!filteredLocalBranches.length" class="git-empty-msg">No local branches found.</div>
            </div>

            <!-- Remote Branches List -->
            <div v-if="remoteBranches.length" class="git-branch-section-title">REMOTE BRANCHES</div>
            <div v-if="remoteBranches.length" class="git-branch-select-list">
              <div
                v-for="rb in filteredRemoteBranches"
                :key="rb"
                class="git-branch-item remote"
                @click="handleSwitchBranch(rb)"
              >
                <div class="git-branch-item-name mono">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>
                  </svg>
                  <span>{{ rb }}</span>
                </div>
                <span class="git-remote-tag">track</span>
              </div>
            </div>
          </div>

          <!-- 3. DELETE BRANCH -->
          <div v-else-if="action === 'delete_branch'" class="git-form-stack">
            <label class="git-field">
              <span class="git-field-label">Target Branch</span>
              <select v-model="targetBranch" class="git-select mono">
                <option value="" disabled>-- Select branch to delete --</option>
                <option
                  v-for="b in localBranches.filter((br) => br !== currentBranch)"
                  :key="b"
                  :value="b"
                >
                  {{ b }} (local)
                </option>
                <option
                  v-for="rb in remoteBranches"
                  :key="rb"
                  :value="rb"
                >
                  {{ rb }} (remote)
                </option>
              </select>
            </label>
            <label class="git-checkbox-label">
              <input v-model="forceDelete" type="checkbox" class="git-checkbox" />
              <span>Force delete (-D)</span>
            </label>
            <label v-if="targetBranch.includes('/')" class="git-checkbox-label">
              <input v-model="isRemoteDelete" type="checkbox" class="git-checkbox" />
              <span>Delete from remote server</span>
            </label>
          </div>

          <!-- 4. MERGE -->
          <div v-else-if="action === 'merge'" class="git-form-stack">
            <div class="git-dialog-hint">
              Merge changes from another branch into current active branch <strong>{{ currentBranch }}</strong>.
            </div>
            <label class="git-field">
              <span class="git-field-label">Source Branch to Merge</span>
              <select v-model="targetBranch" class="git-select mono">
                <option value="" disabled>-- Select branch --</option>
                <option
                  v-for="b in localBranches.filter((br) => br !== currentBranch)"
                  :key="b"
                  :value="b"
                >
                  {{ b }}
                </option>
                <option
                  v-for="rb in remoteBranches"
                  :key="rb"
                  :value="rb"
                >
                  {{ rb }}
                </option>
              </select>
            </label>
            <label class="git-field">
              <span class="git-field-label">Custom Commit Message (Optional)</span>
              <input
                v-model="mergeMessage"
                class="git-input"
                :placeholder="`Merge branch '${targetBranch || '...'}' into ${currentBranch}`"
              />
            </label>
            <label class="git-checkbox-label">
              <input v-model="mergeNoFf" type="checkbox" class="git-checkbox" />
              <span>Create merge commit even if fast-forward is possible (--no-ff)</span>
            </label>
          </div>

          <!-- 5. STASH -->
          <div v-else-if="action === 'stash'" class="git-form-stack">
            <label class="git-field">
              <span class="git-field-label">Stash Message (Optional)</span>
              <input
                v-model="stashMessage"
                class="git-input"
                placeholder="e.g. WIP changes before switching tasks"
                autofocus
                @keydown.enter="handleStash"
              />
            </label>
            <label class="git-checkbox-label">
              <input v-model="stashIncludeUntracked" type="checkbox" class="git-checkbox" />
              <span>Include untracked files (-u)</span>
            </label>
          </div>

          <!-- 6. MANAGE STASHES -->
          <div v-else-if="action === 'manage_stashes'" class="git-form-stack">
            <div v-if="!stashes.length && !busy" class="git-empty-msg">
              No stashes saved in repository.
            </div>
            <div v-else class="git-stash-list">
              <div v-for="st in stashes" :key="st.index" class="git-stash-card">
                <div class="git-stash-head">
                  <span class="git-stash-ref mono">{{ st.ref }}</span>
                  <span class="git-stash-date">{{ st.date }}</span>
                </div>
                <div class="git-stash-msg">{{ st.message || "(No message)" }}</div>
                <div class="git-stash-actions">
                  <AppButton
                    variant="ghost"
                    size="sm"
                    :disabled="busy"
                    title="Pop stash (apply and remove from stash list)"
                    @click="handlePopStash(st.index)"
                  >
                    Pop
                  </AppButton>
                  <AppButton
                    variant="ghost"
                    size="sm"
                    :disabled="busy"
                    title="Apply stash (keep in stash list)"
                    @click="handleApplyStash(st.index)"
                  >
                    Apply
                  </AppButton>
                  <AppButton
                    variant="danger"
                    size="sm"
                    :disabled="busy"
                    title="Delete stash"
                    @click="handleDropStash(st.index)"
                  >
                    Drop
                  </AppButton>
                </div>
              </div>
            </div>
          </div>

          <!-- 7. PUSH -->
          <div v-else-if="action === 'push'" class="git-form-stack">
            <label class="git-field">
              <span class="git-field-label">Remote</span>
              <input v-model="pushRemote" class="git-input mono" placeholder="origin" />
            </label>
            <label class="git-field">
              <span class="git-field-label">Branch</span>
              <input v-model="pushBranch" class="git-input mono" placeholder="main" />
            </label>
            <label class="git-checkbox-label">
              <input v-model="pushSetUpstream" type="checkbox" class="git-checkbox" />
              <span>Set upstream tracking reference (-u)</span>
            </label>
            <label class="git-checkbox-label danger">
              <input v-model="pushForce" type="checkbox" class="git-checkbox" />
              <span>Force push (--force) - use with extreme caution</span>
            </label>
          </div>

          <!-- 8. PULL -->
          <div v-else-if="action === 'pull'" class="git-form-stack">
            <label class="git-field">
              <span class="git-field-label">Remote</span>
              <input v-model="pullRemote" class="git-input mono" placeholder="origin" />
            </label>
            <label class="git-field">
              <span class="git-field-label">Branch</span>
              <input v-model="pullBranch" class="git-input mono" placeholder="main" />
            </label>
            <label class="git-checkbox-label">
              <input v-model="pullRebase" type="checkbox" class="git-checkbox" />
              <span>Rebase local commits instead of merging (--rebase)</span>
            </label>
          </div>

          <!-- 9. FETCH -->
          <div v-else-if="action === 'fetch'" class="git-form-stack">
            <label class="git-field">
              <span class="git-field-label">Remote (leave blank for --all)</span>
              <input v-model="fetchRemote" class="git-input mono" placeholder="origin or empty for all" />
            </label>
            <label class="git-checkbox-label">
              <input v-model="fetchPrune" type="checkbox" class="git-checkbox" />
              <span>Prune remote-tracking references that no longer exist on remote</span>
            </label>
          </div>

          <!-- 10. CLONE -->
          <div v-else-if="action === 'clone'" class="git-form-stack">
            <label class="git-field">
              <span class="git-field-label">Repository URL</span>
              <input
                v-model="cloneUrl"
                class="git-input mono"
                placeholder="https://github.com/owner/repository.git"
                autofocus
              />
            </label>
            <label class="git-field">
              <span class="git-field-label">Target Directory (Optional)</span>
              <input
                v-model="cloneTargetDir"
                class="git-input mono"
                placeholder="Leave blank for project root"
              />
            </label>
          </div>

          <!-- 11. MANAGE REMOTES -->
          <div v-else-if="action === 'manage_remotes'" class="git-form-stack">
            <div class="git-remotes-list">
              <div v-for="rm in remotesList" :key="rm.name" class="git-remote-card">
                <div class="git-remote-header">
                  <span class="git-remote-name mono">{{ rm.name }}</span>
                </div>
                <div class="git-remote-urls mono">
                  <div v-if="rm.fetch_url">fetch: {{ rm.fetch_url }}</div>
                  <div v-if="rm.push_url">push: {{ rm.push_url }}</div>
                </div>
              </div>
              <div v-if="!remotesList.length && !busy" class="git-empty-msg">No remotes configured.</div>
            </div>

            <div class="git-add-remote-section">
              <div class="git-subhead">Add Remote</div>
              <label class="git-field">
                <span class="git-field-label">Remote Name</span>
                <input v-model="newRemoteName" class="git-input mono" placeholder="origin" />
              </label>
              <label class="git-field">
                <span class="git-field-label">Remote URL</span>
                <input v-model="newRemoteUrl" class="git-input mono" placeholder="https://github.com/..." />
              </label>
              <AppButton
                variant="primary"
                size="sm"
                :busy="busy"
                :disabled="!newRemoteName.trim() || !newRemoteUrl.trim()"
                @click="handleAddRemote"
              >
                Add Remote
              </AppButton>
            </div>
          </div>

          <!-- 12. REMOTE & AUTH CONFIGURATION -->
          <div v-else-if="action === 'remote_settings'" class="git-form-stack">
            <label class="git-field">
              <span class="git-field-label">Repository URL</span>
              <input
                v-model="configForm.repository"
                class="git-input mono"
                placeholder="https://github.com/owner/repository.git"
              />
            </label>
            <label class="git-field">
              <span class="git-field-label">Target Remote Branch</span>
              <input
                v-model="configForm.branch"
                class="git-input mono"
                placeholder="main"
              />
            </label>
            <label class="git-field">
              <span class="git-field-label">Personal Access Token <span class="git-field-hint">(Optional — stored securely)</span></span>
              <input
                v-model="configForm.token"
                type="password"
                class="git-input mono"
                autocomplete="new-password"
                placeholder="ghp_*** or token"
              />
            </label>
            <label class="git-field">
              <span class="git-field-label">Exclude Patterns <span class="git-field-hint">(One per line)</span></span>
              <textarea
                v-model="configForm.excludeText"
                class="git-textarea mono"
                rows="3"
                placeholder="node_modules/&#10;dist/&#10;.env"
              ></textarea>
            </label>

            <!-- Danger Zone inside modal -->
            <div class="git-danger-card">
              <div class="git-danger-title">Danger Zone</div>
              <div v-if="!confirmDeinit" class="git-danger-row">
                <span class="git-danger-desc">Remove local .git repository directory</span>
                <AppButton variant="danger" size="sm" :disabled="busy || deinitBusy" @click="confirmDeinit = true">
                  De-init Git
                </AppButton>
              </div>
              <div v-else class="git-danger-confirm-card">
                <span class="git-danger-warn-text">Are you sure? This will delete the local .git directory and commit history.</span>
                <div class="git-danger-confirm-actions">
                  <AppButton variant="ghost" size="sm" :disabled="deinitBusy" @click="confirmDeinit = false">Cancel</AppButton>
                  <AppButton variant="danger" size="sm" :busy="deinitBusy" @click="handleDeinit">Confirm Delete .git</AppButton>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Modal Foot -->
        <div class="unified-popup-foot git-dialog-foot">
          <AppButton variant="ghost" size="sm" :disabled="busy" @click="emit('close')">
            {{ action === 'manage_stashes' || action === 'manage_remotes' || action === 'switch_branch' ? 'Close' : 'Cancel' }}
          </AppButton>

          <AppButton
            v-if="action === 'create_branch'"
            variant="primary"
            size="sm"
            :busy="busy"
            :disabled="!branchName.trim()"
            @click="handleCreateBranch"
          >
            Create Branch
          </AppButton>

          <AppButton
            v-else-if="action === 'delete_branch'"
            variant="danger"
            size="sm"
            :busy="busy"
            :disabled="!targetBranch"
            @click="handleDeleteBranch"
          >
            Delete Branch
          </AppButton>

          <AppButton
            v-else-if="action === 'merge'"
            variant="primary"
            size="sm"
            :busy="busy"
            :disabled="!targetBranch"
            @click="handleMerge"
          >
            Merge Branch
          </AppButton>

          <AppButton
            v-else-if="action === 'stash'"
            variant="primary"
            size="sm"
            :busy="busy"
            @click="handleStash"
          >
            Stash Changes
          </AppButton>

          <AppButton
            v-else-if="action === 'push'"
            variant="primary"
            size="sm"
            :busy="busy"
            @click="handlePush"
          >
            Push Commits
          </AppButton>

          <AppButton
            v-else-if="action === 'pull'"
            variant="primary"
            size="sm"
            :busy="busy"
            @click="handlePull"
          >
            Pull Changes
          </AppButton>

          <AppButton
            v-else-if="action === 'fetch'"
            variant="primary"
            size="sm"
            :busy="busy"
            @click="handleFetch"
          >
            Fetch
          </AppButton>

          <AppButton
            v-else-if="action === 'clone'"
            variant="primary"
            size="sm"
            :busy="busy"
            :disabled="!cloneUrl.trim()"
            @click="handleClone"
          >
            Clone
          </AppButton>

          <template v-else-if="action === 'remote_settings'">
            <AppButton
              variant="ghost"
              size="sm"
              :busy="testConnectionBusy"
              @click="handleTestRemote"
            >
              Test Connection
            </AppButton>
            <AppButton
              variant="primary"
              size="sm"
              :busy="saveConfigBusy"
              @click="handleSaveRemote"
            >
              Save Configuration
            </AppButton>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.git-dialog-backdrop {
  z-index: 1050;
  display: flex;
  align-items: center;
  justify-content: center;
}

.git-dialog-card {
  width: 90vw;
  max-width: 480px;
  max-height: 82vh;
  display: flex;
  flex-direction: column;
}

.git-dialog-head {
  padding: 10px 14px;
}

.git-dialog-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 14px 10px;
  padding: 7px 10px;
  font-size: 11.5px;
  color: var(--alert-err-text);
  background: var(--alert-err-bg);
  border: 1px solid var(--alert-err-border);
  border-radius: var(--radius-sm, 4px);
}

.git-dialog-notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 14px 10px;
  padding: 7px 10px;
  font-size: 11.5px;
  color: var(--alert-ok-text);
  background: var(--alert-ok-bg);
  border: 1px solid var(--alert-ok-border);
  border-radius: var(--radius-sm, 4px);
}

.git-field-hint {
  font-size: 10px;
  color: var(--text-faint);
  font-weight: 400;
}

.git-textarea {
  width: 100%;
  padding: 6px 10px;
  font-size: 11.5px;
  background: var(--bg-deep);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 4px);
  color: var(--text);
  box-sizing: border-box;
  resize: vertical;
}

.git-textarea:focus {
  outline: none;
  border-color: var(--accent);
}

.git-danger-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-deep);
  border: 1px dashed var(--alert-err-border);
  border-radius: var(--radius-sm, 4px);
  margin-top: 4px;
}

.git-danger-title {
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--alert-err-text);
}

.git-danger-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.git-danger-desc {
  font-size: 11px;
  color: var(--text-dim);
}

.git-danger-confirm-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.git-danger-warn-text {
  font-size: 11px;
  color: var(--alert-err-text);
  line-height: 1.4;
}

.git-danger-confirm-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.git-dialog-error-close {
  background: transparent;
  border: none;
  color: inherit;
  font-size: 14px;
  cursor: pointer;
}

.git-dialog-body {
  padding: 8px 14px 16px;
}

.git-dialog-foot {
  padding: 10px 14px;
  gap: 8px;
}

.git-form-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.git-dialog-hint {
  font-size: 11.5px;
  color: var(--text-dim);
  line-height: 1.45;
}

.git-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.git-field-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-dim);
}

.git-input,
.git-select {
  width: 100%;
  padding: 6px 10px;
  font-size: 12px;
  background: var(--bg-deep);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 4px);
  color: var(--text);
  box-sizing: border-box;
}

.git-input:focus,
.git-select:focus {
  outline: none;
  border-color: var(--accent);
}

.git-checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11.5px;
  color: var(--text);
  cursor: pointer;
}

.git-checkbox-label.danger {
  color: var(--alert-err-text);
}

.git-checkbox {
  accent-color: var(--accent);
}

.git-search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  background: var(--bg-deep);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 4px);
  color: var(--text-dim);
}

.git-search-input {
  flex: 1;
  background: transparent;
  border: none;
  font-size: 12px;
  color: var(--text);
  outline: none;
}

.git-branch-section-title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--text-faint);
  margin-top: 4px;
}

.git-branch-select-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 190px;
  overflow-y: auto;
}

.git-branch-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-radius: var(--radius-sm, 4px);
  cursor: pointer;
  font-size: 11.5px;
  transition: background 0.12s;
}

.git-branch-item:hover {
  background: var(--bg-hover);
}

.git-branch-item.active {
  background: var(--selection);
  color: var(--accent);
  font-weight: 600;
}

.git-branch-item-name {
  display: flex;
  align-items: center;
  gap: 7px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.git-active-badge {
  font-size: 9.5px;
  padding: 1px 5px;
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: 3px;
  text-transform: uppercase;
  font-weight: 700;
}

.git-remote-tag {
  font-size: 9.5px;
  padding: 1px 5px;
  background: var(--bg-deep);
  color: var(--text-dim);
  border-radius: 3px;
}

.git-empty-msg {
  padding: 14px;
  text-align: center;
  font-size: 11px;
  color: var(--text-faint);
}

.git-stash-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 250px;
  overflow-y: auto;
}

.git-stash-card {
  padding: 8px 10px;
  background: var(--bg-deep);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 4px);
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.git-stash-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 10.5px;
}

.git-stash-ref {
  font-weight: 600;
  color: var(--accent);
}

.git-stash-date {
  color: var(--text-faint);
  font-size: 10px;
}

.git-stash-msg {
  font-size: 11.5px;
  color: var(--text);
  word-break: break-word;
}

.git-stash-actions {
  display: flex;
  gap: 6px;
  margin-top: 4px;
  justify-content: flex-end;
}

.git-remotes-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 160px;
  overflow-y: auto;
}

.git-remote-card {
  padding: 7px 9px;
  background: var(--bg-deep);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 4px);
  font-size: 11px;
}

.git-remote-name {
  font-weight: 600;
  color: var(--accent);
  margin-bottom: 3px;
}

.git-remote-urls {
  font-size: 10px;
  color: var(--text-dim);
}

.git-add-remote-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}

.git-subhead {
  font-size: 11px;
  font-weight: 600;
  color: var(--text);
}
</style>
