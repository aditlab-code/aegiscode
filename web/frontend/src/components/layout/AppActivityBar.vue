<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import AppBadge from "../ui/AppBadge.vue";

const props = defineProps({
  activeNav: {
    type: String,
    default: "explorer",
    validator: (v) => ["explorer", "git", "queue", "settings"].includes(v),
  },
  sidebarOpen: {
    type: Boolean,
    default: true,
  },
  isDark: {
    type: Boolean,
    default: true,
  },
  queueCount: {
    type: Number,
    default: 0,
  },
  changesCount: {
    type: Number,
    default: 0,
  },
});

const emit = defineEmits([
  "update:activeNav",
  "toggle-theme",
  "open-settings",
  "open-sidebar",
  "toggle-sidebar",
]);

function selectNav(navId) {
  if (props.activeNav === navId && props.sidebarOpen) {
    emit("toggle-sidebar", false);
  } else {
    emit("update:activeNav", navId);
    emit("toggle-sidebar", true);
  }
}

const gearMenuOpen = ref(false);
const gearAnchorRef = ref(null);

function toggleGearMenu() {
  gearMenuOpen.value = !gearMenuOpen.value;
}

function selectSettingItem(tab) {
  gearMenuOpen.value = false;
  emit("open-settings", tab);
}

function handleDocumentClick(e) {
  if (gearMenuOpen.value && gearAnchorRef.value && !gearAnchorRef.value.contains(e.target)) {
    gearMenuOpen.value = false;
  }
}

onMounted(() => {
  if (typeof window !== "undefined") {
    window.addEventListener("click", handleDocumentClick);
  }
});

onBeforeUnmount(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("click", handleDocumentClick);
  }
});
</script>

<template>
  <aside class="app-activity-bar" aria-label="Activity Bar">
    <div class="act-bar-top">
      <!-- Explorer / File Tree -->
      <button
        type="button"
        class="act-btn"
        :class="{ active: sidebarOpen && activeNav === 'explorer' }"
        title="Explorer (Files)"
        aria-label="Explorer"
        @click="selectNav('explorer')"
      >
        <svg
          class="act-ico"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <path d="M14 2v6h6M9 13h6M9 17h4" />
        </svg>
      </button>

      <!-- Source Control / Git -->
      <button
        type="button"
        class="act-btn"
        :class="{ active: sidebarOpen && activeNav === 'git' }"
        title="Source Control & Changes"
        aria-label="Source Control"
        @click="selectNav('git')"
      >
        <svg
          class="act-ico"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <line x1="6" y1="3" x2="6" y2="15" />
          <circle cx="18" cy="6" r="3" />
          <circle cx="6" cy="18" r="3" />
          <path d="M18 9a9 9 0 0 1-9 9" />
        </svg>
        <AppBadge v-if="changesCount > 0" variant="count" class="act-badge">
          {{ changesCount }}
        </AppBadge>
      </button>

      <!-- Global Task Queue -->
      <button
        type="button"
        class="act-btn"
        :class="{ active: sidebarOpen && activeNav === 'queue' }"
        title="Task Queue"
        aria-label="Task Queue"
        @click="selectNav('queue')"
      >
        <svg
          class="act-ico"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        <AppBadge v-if="queueCount > 0" variant="count" class="act-badge">
          {{ queueCount }}
        </AppBadge>
      </button>
    </div>

    <div class="act-bar-bottom">
      <!-- Settings Gear + Popup Toolbar Menu -->
      <div ref="gearAnchorRef" class="act-gear-anchor">
        <button
          type="button"
          class="act-btn"
          :class="{ active: activeNav === 'settings' || gearMenuOpen }"
          title="Settings"
          aria-label="Settings"
          aria-haspopup="menu"
          :aria-expanded="gearMenuOpen"
          @click="toggleGearMenu"
        >
          <svg
            class="act-ico"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="3" />
            <path
              d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
            />
          </svg>
        </button>

        <!-- VS Code-style Settings Toolbar Popup Menu -->
        <div v-if="gearMenuOpen" class="act-gear-menu" role="menu" aria-label="Settings and Information">
          <button type="button" class="act-menu-item" role="menuitem" @click="selectSettingItem('providers')">
            <svg class="act-menu-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
            <span>Settings</span>
            <span class="act-menu-shortcut mono">⌘,</span>
          </button>

          <div class="act-menu-divider"></div>

          <button type="button" class="act-menu-item" role="menuitem" @click="selectSettingItem('overview')">
            <svg class="act-menu-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="16" x2="12" y2="12"/>
              <line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
            <span>Overview</span>
          </button>

          <button type="button" class="act-menu-item" role="menuitem" @click="selectSettingItem('architecture')">
            <svg class="act-menu-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="12 2 2 7 12 12 22 7 12 2"/>
              <polyline points="2 17 12 22 22 17"/>
              <polyline points="2 12 12 17 22 12"/>
            </svg>
            <span>Architecture</span>
          </button>

          <button type="button" class="act-menu-item" role="menuitem" @click="selectSettingItem('license')">
            <svg class="act-menu-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
            <span>License</span>
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>
