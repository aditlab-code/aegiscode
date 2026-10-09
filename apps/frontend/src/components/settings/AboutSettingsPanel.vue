<script setup>
import { ref } from "vue";
import { AEGIS_VERSION } from "../../version.js";
import AppButton from "../ui/AppButton.vue";
import AppCard from "../ui/AppCard.vue";

const props = defineProps({
  section: {
    type: String,
    default: "overview",
    validator: (v) => ["overview", "license"].includes(v),
  },
});

const copied = ref(false);

const MIT_LICENSE_TEXT = `MIT License

Copyright (c) 2026 adigayung
Copyright (c) 2026 aditlab-code
Copyright (c) 2026 AegisCode Authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.`;

async function copyLicense() {
  try {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      await navigator.clipboard.writeText(MIT_LICENSE_TEXT);
      copied.value = true;
      setTimeout(() => {
        copied.value = false;
      }, 2000);
    }
  } catch (_) {
    // fallback
  }
}
</script>

<template>
  <div class="about-settings-root">
    <!-- 1. OVERVIEW SECTION -->
    <div v-if="section === 'overview'" class="about-pane">
      <AppCard variant="panel" class="settings-panel">
        <div class="about-hero">
          <div class="hero-brand">
            <div class="hero-logo">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
              </svg>
            </div>
            <div>
              <div class="hero-title">
                AegisCode Studio Workbench
                <span class="chip chip-sm ok">v{{ AEGIS_VERSION }}</span>
              </div>
              <div class="hero-sub">Autonomous AI Coding Agent &amp; Dual-Stack Development Environment</div>
            </div>
          </div>
        </div>

        <div class="panel-body">
          <p class="about-summary">
            AegisCode is a local-first autonomous AI coding workbench combining an agentic runtime with a high-performance studio workbench. It enforces deterministic guardrails, asymmetric token efficiency (&lt; 4,000 tokens), non-blocking interactive terminal workflows, and zero-loss code integrity.
          </p>

          <div class="about-grid">
            <AppCard variant="card" class="about-card">
              <div class="card-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                  <line x1="8" y1="21" x2="16" y2="21"/>
                  <line x1="12" y1="17" x2="12" y2="21"/>
                </svg>
              </div>
              <div class="about-card-title">Hybrid Asymmetric Split-Brain (&lt; 4k Tokens)</div>
              <div class="card-text">
                Decouples cloud LLM reasoning with a strict context budget (&lt; 4,000 tokens) from deterministic local execution (AST parsing, CodeGraph, and FileWriteLock).
              </div>
            </AppCard>

            <AppCard variant="card" class="about-card">
              <div class="card-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
              </div>
              <div class="about-card-title">Deterministic Guardrails &amp; HITL (Zero Code Destruction)</div>
              <div class="card-text">
                Human-in-the-Loop visual Monaco diff approval, FileWriteLock race prevention, read-before-write invariant, and instant 1-click snapshot rollback.
              </div>
            </AppCard>

            <AppCard variant="card" class="about-card">
              <div class="card-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polyline points="4 17 10 11 4 5"/>
                  <line x1="12" y1="19" x2="20" y2="19"/>
                </svg>
              </div>
              <div class="about-card-title">Interactive Pseudo-Terminal (PTY Zero-Zombie)</div>
              <div class="card-text">
                Interactive shell sessions powered by non-blocking PTY kernel (@xterm/xterm), responsive Ctrl+C interrupts, and clean tree-kill with 0% orphan process lifecycle.
              </div>
            </AppCard>

            <AppCard variant="card" class="about-card">
              <div class="card-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polygon points="12 2 2 7 12 12 22 7 12 2"/>
                  <polyline points="2 17 12 22 22 17"/>
                  <polyline points="2 12 12 17 22 12"/>
                </svg>
              </div>
              <div class="about-card-title">Local-First Code Intelligence &amp; RTK Protocol</div>
              <div class="card-text">
                Canonical <span class="mono">.aegis/</span> workspace memory, deterministic SQLite CodeGraph AST traversal, and real-time state synchronization via RTK Protocol.
              </div>
            </AppCard>
          </div>
        </div>
      </AppCard>
    </div>

    <!-- 3. LICENSE SECTION -->
    <div v-else-if="section === 'license'" class="about-pane">
      <AppCard variant="panel" class="settings-panel">
        <template #header>
          <div>
            <div class="title">Open Source License</div>
            <div class="desc">AegisCode is open source software released under the terms of the MIT License.</div>
          </div>
          <div class="panel-actions">
            <AppButton variant="ghost" size="sm" @click="copyLicense">
              <template #icon>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
              </template>
              <span>{{ copied ? "Copied!" : "Copy License" }}</span>
            </AppButton>
          </div>
        </template>

        <div class="panel-body">
          <div class="license-card">
            <pre class="license-text mono"><code>{{ MIT_LICENSE_TEXT }}</code></pre>
          </div>

          <div class="credits-section">
            <div class="credits-title">Third-Party Open Source Components</div>
            <div class="credits-grid">
              <div class="credit-item">
                <span class="credit-name">Monaco Editor</span>
                <span class="credit-desc">VS Code editor engine &amp; language services</span>
              </div>
              <div class="credit-item">
                <span class="credit-name">Vue.js 3</span>
                <span class="credit-desc">Progressive reactive frontend framework</span>
              </div>
              <div class="credit-item">
                <span class="credit-name">Django &amp; Django REST Framework</span>
                <span class="credit-desc">Robust backend gateway and persistence API</span>
              </div>
              <div class="credit-item">
                <span class="credit-name">Pytest &amp; Vitest</span>
                <span class="credit-desc">Dual-stack automated test runners</span>
              </div>
            </div>
          </div>
        </div>
      </AppCard>
    </div>
  </div>
</template>

<style scoped>
.about-settings-root {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.about-hero {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-soft);
  background: rgba(45, 125, 78, 0.05);
}

.hero-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hero-logo {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(45, 125, 78, 0.2);
  color: var(--accent);
}

.hero-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 650;
  color: var(--text);
}

.hero-sub {
  font-size: 11.5px;
  color: var(--text-faint);
  margin-top: 2px;
}

.about-summary {
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-dim);
  margin: 0 0 16px;
}

.about-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.about-card {
  padding: 14px 16px !important;
  border-radius: 8px !important;
  background: var(--inset, rgba(0, 0, 0, 0.25)) !important;
  border: 1px solid var(--line, var(--border-soft)) !important;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: none !important;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.about-card:hover {
  border-color: var(--accent, var(--edge)) !important;
  box-shadow: none !important;
  transform: none !important;
}

.card-icon {
  color: var(--accent);
  margin-bottom: 2px;
  display: flex;
  align-items: center;
}

.about-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.3;
}

.card-text {
  font-size: 11.5px;
  color: var(--text-faint);
  line-height: 1.45;
}

.license-card {
  padding: 14px 16px;
  background: var(--inset, rgba(0, 0, 0, 0.25));
  border: 1px solid var(--line);
  border-radius: 8px;
  margin-bottom: 16px;
}

.license-text {
  margin: 0;
  font-size: 11px;
  line-height: 1.55;
  color: var(--text-dim);
  white-space: pre-wrap;
  word-break: break-word;
}

.credits-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.credits-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text);
}

.credits-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px;
}

.credit-item {
  padding: 8px 12px;
  background: var(--inset, rgba(0, 0, 0, 0.25));
  border: 1px solid var(--line);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.credit-name {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text);
}

.credit-desc {
  font-size: 10.5px;
  color: var(--text-faint);
}
</style>
