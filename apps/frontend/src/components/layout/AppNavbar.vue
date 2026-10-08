<script setup>

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
  sidebarVisible: {
    type: Boolean,
    default: true,
  },
  bottomDockVisible: {
    type: Boolean,
    default: false,
  },
  isDark: {
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
  "toggle-sidebar",
  "toggle-terminal",
  "toggle-theme",
  "logout",
]);

</script>

<template>
  <header class="app-navbar" aria-label="Top Navigation">
    <!-- macOS / UI Kit Traffic lights -->
    <div class="nav-traffic-lights" aria-hidden="true">
      <span class="traffic-light light-close" title="Close"></span>
      <span class="traffic-light light-minimize" title="Minimize"></span>
      <span class="traffic-light light-maximize" title="Maximize"></span>
    </div>

    <!-- Left: Aegis Brand -->
    <div class="nav-left">
      <button
        type="button"
        class="nav-project-btn"
        title="Open explorer"
        @click="emit('open-explorer')"
      >
        <div class="brand-badge-icon" aria-hidden="true">
          <img src="/favicon.svg" alt="Aegis" width="16" height="16" class="brand-badge-img" />
        </div>
        <span class="brand-title">AEGIS</span>
      </button>
    </div>

    <!-- Center: Command Search ⌘K -->
    <div class="nav-center">
      <button
        type="button"
        class="nav-cmd-btn"
        title="Search files, commands, and more (Cmd+K / Ctrl+K)"
        aria-label="Open Command Palette"
        @click="emit('open-command-palette')"
      >
        <svg
          class="cmd-ico"
          width="12"
          height="12"
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
        <span class="cmd-text">Search files, commands, and more</span>
        <kbd class="cmd-shortcut">⌘ K</kbd>
      </button>
    </div>

    <!-- Right: Status, Profile, Theme & Panel Toggles -->
    <div class="nav-right">
      <!-- Changes Count Chip -->
      <div
        v-if="changesCount > 0"
        class="chip changes-chip"
        title="Pending changes count"
      >
        <span class="chip-label">Changes:</span>
        <span class="chip-val mono">{{ changesCount }}</span>
      </div>

      <!-- Background AI Running Indicator -->
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

      <!-- User Profile Chip -->
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
        <span v-if="tier === 'desktop'" class="user-name-text">
          {{ user.name || user.email }}
        </span>
        <button
          type="button"
          class="nav-logout-btn"
          title="Sign out of Antigravity session"
          aria-label="Sign out"
          @click="emit('logout')"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
            <polyline points="16 17 21 12 16 7"></polyline>
            <line x1="21" y1="12" x2="9" y2="12"></line>
          </svg>
        </button>
      </div>

      <!-- Theme Toggle Button -->
      <button
        type="button"
        class="icon-action-btn"
        :title="isDark ? 'Switch to Light Theme' : 'Switch to Dark Theme'"
        aria-label="Toggle theme"
        @click="emit('toggle-theme')"
      >
        <svg v-if="isDark" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5"></circle>
          <line x1="12" y1="1" x2="12" y2="3"></line>
          <line x1="12" y1="21" x2="12" y2="23"></line>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
          <line x1="1" y1="12" x2="3" y2="12"></line>
          <line x1="21" y1="12" x2="23" y2="12"></line>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
        </svg>
        <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
      </button>

      <span class="nav-v-sep" aria-hidden="true"></span>

      <!-- Panel Left Toggle (Sidebar) -->
      <button
        type="button"
        class="icon-action-btn"
        :class="{ 'is-active': sidebarVisible }"
        title="Toggle Explorer Sidebar (Cmd+B)"
        aria-label="Toggle explorer"
        @click="emit('toggle-sidebar')"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="9" y1="3" x2="9" y2="21"></line>
        </svg>
      </button>

      <!-- Panel Bottom Toggle (Terminal Dock) -->
      <button
        type="button"
        class="icon-action-btn"
        :class="{ 'is-active': bottomDockVisible }"
        title="Toggle Terminal Dock (Ctrl+`)"
        aria-label="Toggle terminal"
        @click="emit('toggle-terminal')"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="3" y1="15" x2="21" y2="15"></line>
        </svg>
      </button>

      <!-- Panel Right Toggle (Assistant Drawer) -->
      <button
        type="button"
        class="icon-action-btn"
        :class="{ 'is-active': assistantVisible, 'is-running': isRunning }"
        title="Toggle Aegis Assistant (Cmd+J)"
        aria-label="Toggle assistant"
        @click="emit('toggle-assistant')"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="15" y1="3" x2="15" y2="21"></line>
        </svg>
      </button>
    </div>
  </header>
</template>
