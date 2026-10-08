<script setup>
import AppBreadcrumbs from "../ui/AppBreadcrumbs.vue";

const props = defineProps({
  activeTabPath: {
    type: String,
    default: "",
  },
  activeTab: {
    type: Object,
    default: null,
  },
  projectRootName: {
    type: String,
    default: "",
  },
  isSplit: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["navigate", "select-file"]);
</script>

<template>
  <div
    v-if="activeTabPath"
    class="wb-breadcrumbs-bar"
    :class="{ 'split-breadcrumbs': isSplit }"
  >
    <div
      v-if="activeTabPath === 'aegis://settings'"
      class="breadcrumbs-list"
      aria-label="Settings Breadcrumbs"
    >
      <span class="crumb-item crumb-root">Preferences</span>
      <span class="crumb-separator" aria-hidden="true">›</span>
      <span class="crumb-item crumb-file current">Settings</span>
    </div>
    <div
      v-else-if="activeTabPath === 'aegis://welcome'"
      class="breadcrumbs-list"
      aria-label="Welcome Breadcrumbs"
    >
      <span class="crumb-item crumb-root">AEGIS</span>
      <span class="crumb-separator" aria-hidden="true">›</span>
      <span class="crumb-item crumb-file current">Welcome</span>
    </div>
    <div
      v-else-if="activeTab?.isDiff || activeTabPath.startsWith('diff://')"
      class="breadcrumbs-list"
      aria-label="Diff Breadcrumbs"
    >
      <span class="crumb-item crumb-root">{{ projectRootName }}</span>
      <span class="crumb-separator" aria-hidden="true">›</span>
      <span class="crumb-item crumb-file current">{{ activeTab?.name || 'Diff' }}</span>
    </div>
    <AppBreadcrumbs
      v-else
      :path="activeTabPath"
      :root="projectRootName"
      @navigate="(p) => emit('navigate', p)"
      @select-file="(p) => emit('select-file', p)"
    />
  </div>
</template>
