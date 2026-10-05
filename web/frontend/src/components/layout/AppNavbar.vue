<script setup>
import { computed } from "vue";
import {
  getProjectDisplayName,
} from "../../services/projectService.js";

const props = defineProps({
  project: {
    type: Object,
    default: null,
  },
  tier: {
    type: String,
    default: "desktop",
    validator: (v) => ["desktop", "compact", "mobile"].includes(v),
  },
  agentStatus: {
    type: Object,
    default: () => ({ label: "idle", cls: "status-off" }),
  },
  changesCount: {
    type: Number,
    default: 0,
  },
  connected: {
    type: Boolean,
    default: false,
  },
  isRunning: {
    type: Boolean,
    default: false,
  },
  assistantVisible: {
    type: Boolean,
    default: true,
  },
  user: {
    type: Object,
    default: null,
  },
});

const emit = defineEmits([
  "open-explorer",
  "open-command-palette",
  "toggle-assistant",
  "logout",
]);

const projectName = computed(() => (props.project ? getProjectDisplayName(props.project) : "AegisCode Studio"));
</script>

<template>
  <header class="app-navbar" aria-label="Top Navigation">
    <!-- Left: Brand -->
    <div class="nav-left">
      <div class="nav-brand">
        <span class="brand-badge" aria-label="AegisCode Studio">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="m4.5 8.5-3 3.5 3 3.5" />
            <path d="m19.5 8.5 3 3.5-3 3.5" />
            <path d="M12 3c.4 3.8 2.2 5.6 6 6-3.8.4-5.6 2.2-6 6-.4-3.8-2.2-5.6-6-6 3.8-.4 5.6-2.2 6-6Z" />
            <circle cx="12" cy="12" r="1.5" fill="currentColor" />
          </svg>
        </span>
        <span v-if="tier !== 'mobile'" class="brand-text">AegisCode</span>
      </div>
    </div>

    <!-- Center: Command Palette Quick Open Trigger -->
    <div class="nav-center">
      <button
        type="button"
        class="nav-cmd-btn"
        title="Command Palette (Cmd+K / Ctrl+K)"
        aria-label="Open Command Palette"
        @click="emit('open-command-palette')"
      >
        <div class="nav-cmd-left">
          <svg
            class="cmd-ico"
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <span v-if="tier !== 'mobile'" class="cmd-text">Quick Open</span>
        </div>
        <kbd v-if="tier === 'desktop'" class="cmd-shortcut">⌘K</kbd>
      </button>
    </div>

    <!-- Right: Status Chips & Actions -->
    <div class="nav-right">
      <!-- Changes Count Chip (Desktop and Compact only when > 0; hidden on Mobile) -->
      <div
        v-if="tier !== 'mobile' && changesCount > 0"
        class="chip changes-chip"
        title="Pending changes count"
      >
        <span class="chip-label">Changes:</span>
        <span class="chip-val mono">{{ changesCount }}</span>
      </div>


      <!-- Background AI Running Indicator (Pulsing badge when drawer closed) -->
      <button
        v-if="isRunning && !assistantVisible"
        type="button"
        class="nav-assistant-pill"
        title="AI process running in background. Click to open Assistant."
        aria-label="AI running in background"
        @click="emit('toggle-assistant')"
      >
        <span class="pulse-dot" aria-hidden="true"></span>
        <span class="pill-label">AI Working…</span>
      </button>

      <!-- User Profile / Antigravity Identity Chip -->
      <div
        v-if="user"
        class="nav-user-chip"
        :title="`Signed in as ${user.name || user.email} (${user.email})`"
      >
        <img
          v-if="user.picture"
          :src="user.picture"
          :alt="user.name || 'User'"
          class="user-avatar-img"
          referrerpolicy="no-referrer"
        />
        <div v-else class="user-avatar-fallback">
          {{ (user.name || user.email || "U").charAt(0).toUpperCase() }}
        </div>
        <span v-if="tier !== 'mobile'" class="user-name-text">
          {{ user.name || user.email }}
        </span>
        <button
          type="button"
          class="nav-logout-btn"
          title="Sign out of Antigravity session"
          aria-label="Sign out"
          @click="emit('logout')"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
            <polyline points="16 17 21 12 16 7"></polyline>
            <line x1="21" y1="12" x2="9" y2="12"></line>
          </svg>
        </button>
      </div>

      <!-- Assistant Toggle Button -->
      <button
        type="button"
        class="nav-assistant-btn"
        :class="{ 'is-running': isRunning, 'drawer-closed': !assistantVisible }"
        :title="isRunning && !assistantVisible ? 'AI Assistant (Running in background)' : 'Toggle AI Assistant (Cmd+J)'"
        aria-label="Toggle Assistant"
        @click="emit('toggle-assistant')"
      >
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
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
      </button>
    </div>
  </header>
</template>
