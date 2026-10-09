<script setup>
import { ref } from "vue";
import ChangesPanel from "../git/ChangesPanel.vue";
import GithubBackupPanel from "../git/GithubBackupPanel.vue";

const props = defineProps({
  activeProject: {
    type: Object,
    default: null,
  },
  explorerRefresh: {
    type: Number,
    default: 0,
  },
  changes: {
    type: Array,
    default: () => [],
  },
  validation: {
    type: Object,
    default: () => ({}),
  },
});

const emit = defineEmits([
  "open-file",
  "open-diff",
  "discard-change",
  "stage-change",
  "unstage-change",
  "checkpoint-created",
  "branch-info-updated",
  "changes-updated",
]);

const changesPanelRef = ref(null);

async function onCheckpointCreated(result) {
  if (changesPanelRef.value?.loadGitChanges) {
    await changesPanelRef.value.loadGitChanges();
  }
  emit("checkpoint-created", result);
}

function handleOpenFile(file) {
  emit("open-file", file);
}

function handleOpenDiff(file) {
  emit("open-diff", file);
}
</script>

<template>
  <section class="sidebar-panel git-panel">
    <div class="backup-subpanel">
      <GithubBackupPanel
        :project="activeProject"
        :refresh-key="explorerRefresh"
        @branch-info-updated="emit('branch-info-updated', $event)"
        @checkpoint-created="onCheckpointCreated"
      >
        <ChangesPanel
          ref="changesPanelRef"
          :changes="changes"
          :validation="validation || {}"
          :project="activeProject"
          :refresh-key="explorerRefresh"
          @open-file="handleOpenFile"
          @open-diff="handleOpenDiff"
          @discard-change="emit('discard-change', $event)"
          @stage-change="emit('stage-change', $event)"
          @unstage-change="emit('unstage-change', $event)"
          @changes-updated="emit('changes-updated', $event)"
        />
      </GithubBackupPanel>
    </div>
  </section>
</template>
