<script setup>
/**
 * WelcomeView.vue - Modern AETHER Welcome & Getting Started Studio Canvas.
 * Follows the "Your IDE. Your Own." philosophy: pure web-native, zero bloatware,
 * local-first, engineered to work seamlessly side-by-side with browser AI panels.
 * Strictly uses native inline Vue SVG icons (zero emoticons).
 */
import { computed } from "vue";
import { AEGIS_VERSION } from "../version.js";

const props = defineProps({
  projects: {
    type: Array,
    default: () => [],
  },
  lastProject: {
    type: Object,
    default: null,
  },
  activeProject: {
    type: Object,
    default: null,
  },
  busy: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits([
  "open-folder",
  "clone-git",
  "new-task",
  "open-project",
  "delete-project",
  "open-settings",
]);

function relTime(iso) {
  if (!iso) return "recently";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "recently";
  const sec = Math.floor((Date.now() - t) / 1000);
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  return `${day}d ago`;
}

const recentProjects = computed(() => {
  return [...props.projects]
    .sort((a, b) => {
      const ta = Date.parse(a.updated_at || a.created_at || 0) || 0;
      const tb = Date.parse(b.updated_at || b.created_at || 0) || 0;
      return tb - ta;
    })
    .slice(0, 8);
});

function handleOpenProject(p) {
  if (!p || props.busy) return;
  emit("open-project", p.id || p);
}
</script>

<template>
  <div class="welcome-view-root" role="region" aria-label="Welcome and Getting Started">
    <div class="welcome-container">
      <!-- 2-Column Studio Grid -->
      <div class="welcome-grid">
        <!-- Left Column: Branding, Quick Actions, Recent Workspaces -->
        <div class="welcome-col welcome-col-main">
          <!-- Hero Header Card -->
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
                  <span class="version-tag">v{{ AEGIS_VERSION }}</span>
                </div>
              </div>
              <p class="brand-tagline welcome-project">
                {{ activeProject ? activeProject.path : "No Project Selected" }}
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
                :disabled="busy"
                @click="emit('open-folder')"
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
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                </svg>
                <div class="action-btn-text">
                  <span class="btn-label">Open Folder…</span>
                  <span class="btn-sub">Open local project from disk</span>
                </div>
              </button>

              <button
                type="button"
                class="action-btn"
                :disabled="busy"
                @click="emit('clone-git')"
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
                  <line x1="6" y1="3" x2="6" y2="15" />
                  <circle cx="18" cy="6" r="3" />
                  <circle cx="6" cy="18" r="3" />
                  <path d="M18 9a9 9 0 0 1-9 9" />
                </svg>
                <div class="action-btn-text">
                  <span class="btn-label">Clone Git Repository…</span>
                  <span class="btn-sub">Clone from GitHub or remote URL</span>
                </div>
              </button>
            </div>
          </section>

          <!-- Recent Workspaces Card -->
          <section class="welcome-card recent-workspaces-card" aria-labelledby="recent-heading">
            <div class="recent-header-row">
              <h2 id="recent-heading" class="card-heading">
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
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                <span><span class="sr-only">Workspace: </span>Recent Workspaces</span>
              </h2>
              <span v-if="recentProjects.length" class="recent-count">
                {{ recentProjects.length }} workspaces
              </span>
            </div>

            <div v-if="!recentProjects.length" class="empty-recent-card">
              <svg
                class="empty-icon"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
              <p>No recent workspaces yet. Click <strong>Open Folder…</strong> to open your project.</p>
            </div>

            <ul v-else class="recent-list" role="list">
              <li
                v-for="p in recentProjects"
                :key="p.id"
                class="recent-item"
                :class="{ active: activeProject && activeProject.id === p.id }"
              >
                <button
                  type="button"
                  class="recent-open-btn"
                  :title="`Open ${p.name}`"
                  @click="handleOpenProject(p)"
                >
                  <svg
                    class="recent-item-icon"
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                  </svg>
                  <div class="recent-item-info">
                    <span class="recent-name">{{ p.name }}</span>
                    <span class="recent-path mono" :title="p.path || p.root">{{ p.path || p.root }}</span>
                  </div>
                  <span class="recent-time">{{ relTime(p.updated_at || p.created_at) }}</span>
                </button>
                <button
                  type="button"
                  class="recent-del-btn"
                  title="Remove from recent"
                  aria-label="Remove workspace from recent"
                  @click.stop="emit('delete-project', p.id)"
                >
                  <svg
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
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </li>
            </ul>
          </section>
        </div>

        <!-- Right Column: Philosophy, Side-by-Side Browser Synergy, Shortcuts -->
        <div class="welcome-col welcome-col-side">
          <!-- Philosophy & Superpower Card -->
          <section class="welcome-card philosophy-card" aria-labelledby="philosophy-heading">
            <h2 id="philosophy-heading" class="card-heading">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <circle cx="12" cy="12" r="10" />
                <path d="M12 16v-4" />
                <path d="M12 8h.01" />
              </svg>
              <span>Built for Modern Developers</span>
            </h2>

            <div class="philosophy-features">
              <div class="feature-item">
                <div class="feature-icon-wrap" aria-hidden="true">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                  </svg>
                </div>
                <div class="feature-text">
                  <span class="feature-title">Pure Web-Native, Zero Bloat</span>
                  <p class="feature-desc">
                    No heavy Electron processes or embedded background baggage. Instant startup and minimal memory footprint.
                  </p>
                </div>
              </div>

              <div class="feature-item">
                <div class="feature-icon-wrap" aria-hidden="true">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                    <line x1="9" y1="3" x2="9" y2="21" />
                  </svg>
                </div>
                <div class="feature-text">
                  <span class="feature-title">Side-by-Side Browser AI Synergy</span>
                  <p class="feature-desc">
                    Designed to work alongside browser AI sidebars (Chrome Gemini side panel, Edge Copilot, Arc). Your IDE and browser AI in unified flow.
                  </p>
                </div>
              </div>

              <div class="feature-item">
                <div class="feature-icon-wrap" aria-hidden="true">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                </div>
                <div class="feature-text">
                  <span class="feature-title">Local-First & Autonomous</span>
                  <p class="feature-desc">
                    Your code stays on your filesystem. Autonomous execution loop with real-time inspection, editing, and tests.
                  </p>
                </div>
              </div>
            </div>
          </section>

          <!-- Essential Keyboard Shortcuts -->
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
</template>

<style>
.welcome-view-root {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  background: transparent !important;
  color: var(--text, #cccccc);
  padding: 40px 32px;
  box-sizing: border-box;
  position: relative;
  z-index: 1;
}

[data-theme="light"] .welcome-view-root {
  background: transparent !important;
  color: var(--text, #2c2738);
}

.welcome-container {
  max-width: 1100px;
  margin: 0 auto;
}

.welcome-grid {
  display: grid;
  grid-template-columns: minmax(340px, 1.4fr) minmax(300px, 1fr);
  gap: 48px;
}

@media (max-width: 860px) {
  .welcome-grid {
    grid-template-columns: 1fr;
    gap: 32px;
  }
}

/* Hero Header */
.welcome-hero {
  margin-bottom: 0;
  width: 100%;
}

.hero-brand-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 8px;
}

.brand-logo-wrap {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(16, 240, 154, 0.20), rgba(52, 211, 153, 0.14));
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.1));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent, #10f09a);
}

.brand-text-block {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.brand-title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.5px;
  color: var(--text-bright, #ffffff);
}

.brand-highlight {
  font-weight: 400;
  color: var(--accent, #10f09a);
}

.version-tag {
  font-size: 11px;
  font-family: var(--font-mono, monospace);
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--bg-surface, #252526);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.08));
  color: var(--text-dim, #888888);
}

.brand-tagline {
  margin: 0;
  font-size: 14px;
  color: var(--text-dim, #999999);
}

/* Sections */
.welcome-section {
  margin-bottom: 32px;
}

.section-title {
  margin: 0 0 14px 0;
  font-size: 12px;
  text-transform: uppercase;
  font-weight: 600;
  letter-spacing: 0.8px;
  color: var(--text-dim, #777777);
}

/* Action Buttons */
.action-buttons-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 16px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.07);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.12));
  color: var(--text, #cccccc);
  text-align: left;
  cursor: pointer;
  transition: all 0.18s ease;
  width: 100%;
  box-sizing: border-box;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

[data-theme="light"] .action-btn {
  background: rgba(255, 255, 255, 0.45);
  border-color: rgba(0, 0, 0, 0.08);
  box-shadow: 0 4px 16px rgba(69, 43, 34, 0.06);
}

.action-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.14);
  border-color: var(--accent, #10f09a);
  color: var(--text-bright, #ffffff);
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(16, 240, 154, 0.25);
}

[data-theme="light"] .action-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.72);
  border-color: var(--accent, #10f09a);
  box-shadow: 0 6px 20px rgba(16, 240, 154, 0.20);
}

.action-icon {
  color: var(--accent, #10f09a);
  flex-shrink: 0;
}

.action-btn-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.btn-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-bright, #ffffff);
}

.btn-sub {
  font-size: 12px;
  color: var(--text-dim, #888888);
}

/* Recent Workspaces */
.recent-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  margin-bottom: 14px;
}

.recent-header-row .card-heading {
  margin: 0 !important;
}

.recent-count {
  font-size: 11px;
  color: var(--text-dim, #777777);
}

.empty-recent-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px dashed var(--border-soft, rgba(255, 255, 255, 0.08));
  color: var(--text-dim, #888888);
  font-size: 13px;
  width: 100%;
  box-sizing: border-box;
}

[data-theme="light"] .empty-recent-card {
  background: rgba(0, 0, 0, 0.015);
  border-color: rgba(0, 0, 0, 0.08);
}

.empty-icon {
  color: var(--text-dim, #666666);
  flex-shrink: 0;
}

.recent-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.recent-item {
  display: flex;
  align-items: center;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.06));
  transition: all 0.15s ease;
  width: 100%;
  box-sizing: border-box;
}

[data-theme="light"] .recent-item {
  background: rgba(0, 0, 0, 0.02);
  border-color: rgba(0, 0, 0, 0.06);
}

.recent-item:hover {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.14);
}

[data-theme="light"] .recent-item:hover {
  background: rgba(0, 0, 0, 0.05);
  border-color: var(--accent, #10f09a);
}

.recent-item.active {
  border-color: var(--accent, #10f09a);
}

.recent-open-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  padding: 9px 12px;
  background: transparent;
  border: none;
  color: inherit;
  text-align: left;
  cursor: pointer;
  min-width: 0;
}

.recent-item-icon {
  color: var(--text-dim, #888888);
  flex-shrink: 0;
}

.recent-item-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.recent-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-bright, #ffffff);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recent-path {
  font-size: 11px;
  color: var(--text-dim, #777777);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recent-time {
  font-size: 11px;
  color: var(--text-dim, #666666);
  flex-shrink: 0;
  margin-left: 8px;
}

.recent-del-btn {
  background: transparent;
  border: none;
  padding: 8px 10px;
  color: var(--text-dim, #666666);
  cursor: pointer;
  border-radius: 4px;
  margin-right: 4px;
}

.recent-del-btn:hover {
  color: var(--danger, #e06c75);
}

/* Cards - Frosted Glass */
.welcome-card {
  background: rgba(14, 13, 20, 0.45);
  backdrop-filter: blur(20px) saturate(190%);
  -webkit-backdrop-filter: blur(20px) saturate(190%);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 24px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
}

[data-theme="light"] .welcome-card {
  background: rgba(253, 249, 243, 0.55);
  border: 1px solid rgba(69, 43, 34, 0.14);
  box-shadow: 0 16px 40px rgba(69, 43, 34, 0.10);
}

/* Cards - Left aligned */
.hero-card,
.start-card,
.recent-workspaces-card,
.philosophy-card {
  align-items: flex-start !important;
  text-align: left !important;
  justify-content: flex-start !important;
  max-width: none !important;
  width: 100%;
  box-sizing: border-box;
}

.hero-card .hero-brand-row {
  justify-content: flex-start;
  width: 100%;
}

.hero-card .brand-text-block {
  text-align: left;
}

.hero-card .welcome-project {
  text-align: left;
  margin: 0;
  width: 100%;
}

.philosophy-card .card-heading {
  align-items: center !important;
  justify-content: flex-start !important;
  text-align: left !important;
  width: 100%;
}

.philosophy-card .philosophy-features {
  display: flex;
  flex-direction: column;
  align-items: flex-start !important;
  text-align: left !important;
  width: 100%;
}

.philosophy-card .feature-item {
  display: flex;
  align-items: flex-start !important;
  text-align: left !important;
  justify-content: flex-start !important;
  width: 100%;
}

.philosophy-card .feature-text {
  align-items: flex-start !important;
  text-align: left !important;
}

.philosophy-card .feature-title,
.philosophy-card .feature-desc {
  text-align: left !important;
}

.philosophy-card .card-action-bar {
  text-align: left !important;
  display: flex;
  justify-content: flex-start !important;
  width: 100%;
}

/* Key Bindings Card - Left aligned */
.shortcuts-card {
  align-items: stretch !important;
  text-align: left !important;
  max-width: none !important;
  width: 100%;
  box-sizing: border-box;
}

.shortcuts-card .card-heading {
  align-items: center !important;
  justify-content: flex-start !important;
  text-align: left !important;
  width: 100%;
}

.shortcuts-card .shortcuts-grid {
  width: 100%;
}

.card-heading {
  margin: 0 0 16px 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-bright, #ffffff);
  display: flex;
  align-items: center;
  gap: 8px;
}

.philosophy-features {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 18px;
}

.feature-item {
  display: flex;
  gap: 12px;
}

.feature-icon-wrap {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: rgba(16, 240, 154, 0.08);
  border: 1px solid rgba(16, 240, 154, 0.18);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent, #10f09a);
  flex-shrink: 0;
}

.feature-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.feature-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-bright, #ffffff);
}

.feature-desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.4;
  color: var(--text-dim, #888888);
}

/* Shortcuts */
.shortcuts-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.shortcut-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
}

.sc-label {
  color: var(--text-dim, #999999);
}

.sc-kbd-group {
  display: flex;
  align-items: center;
  gap: 4px;
}

kbd {
  display: inline-block;
  padding: 2px 6px;
  font-size: 11px;
  font-family: var(--font-mono, monospace);
  line-height: 1.2;
  color: var(--text, #cccccc);
  background: var(--bg-base, #1e1e1e);
  border: 1px solid var(--border-soft, rgba(255, 255, 255, 0.15));
  border-radius: 4px;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.2);
}

/* Light Theme Card Typography & Contrast Overrides */
[data-theme="light"] .brand-title,
[data-theme="light"] .btn-label,
[data-theme="light"] .card-heading,
[data-theme="light"] .feature-title,
[data-theme="light"] .recent-name {
  color: var(--text, #180c06) !important;
}

[data-theme="light"] .action-btn {
  color: var(--text, #180c06);
}

[data-theme="light"] .action-btn:hover:not(:disabled) {
  color: var(--text, #180c06) !important;
}

[data-theme="light"] .sc-label {
  color: var(--text-dim, #4a3628);
}

/* Button tombol shortcut key bindings di light theme berwarna hitam, label text putih */
[data-theme="light"] kbd,
[data-theme="light"] .sc-kbd-group kbd {
  background: #181524 !important;
  color: #ffffff !important;
  border-color: rgba(24, 21, 36, 0.6) !important;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.35) !important;
}
</style>
