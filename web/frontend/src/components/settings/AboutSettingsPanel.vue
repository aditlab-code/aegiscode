<script setup>
import { ref } from "vue";
import { AEGIS_VERSION } from "../version.js";
import AppCard from "../ui/AppCard.vue";

const props = defineProps({
  section: {
    type: String,
    default: "overview",
    validator: (v) => ["overview", "architecture", "license"].includes(v),
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
      <div class="panel settings-panel">
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
            AegisCode is a dual-stack autonomous coding agent engine combining an agentic Python runtime with a high-performance modern web workbench. It provides end-to-end task execution, intelligent codebase exploration, test-driven validation, and resilient error recovery.
          </p>

          <div class="about-grid">
            <AppCard variant="card" class="about-card">
              <div class="card-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M12 2a4 4 0 0 0-4 4v1H6a2 2 0 0 0-2 2v2a2 2 0 0 0 2 2v2a2 2 0 0 0-2 2v2a2 2 0 0 0 2 2h2v1a4 4 0 0 0 8 0v-1h2a2 2 0 0 0 2-2v-2a2 2 0 0 0-2-2v-2a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2V6a4 4 0 0 0-4-4z"/>
                </svg>
              </div>
              <div class="about-card-title">Hybrid 5-Stage CoT Protocol</div>
              <div class="card-text">
                Enforces systematic reasoning: Intent Assessment &rarr; Architectural Analysis (YAGNI Check) &rarr; Step Action Planning &rarr; Execution Reflection Loop &rarr; Independent Verification.
              </div>
            </AppCard>

            <AppCard variant="card" class="about-card">
              <div class="card-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                  <line x1="8" y1="21" x2="16" y2="21"/>
                  <line x1="12" y1="17" x2="12" y2="21"/>
                </svg>
              </div>
              <div class="about-card-title">Hybrid Asymmetric Split-Brain</div>
              <div class="card-text">
                Decouples cloud LLM reasoning with a strict context budget (&lt; 4,000 tokens) from deterministic local execution (AST parsing, PTY terminal, and FileWriteLock).
              </div>
            </AppCard>

            <AppCard variant="card" class="about-card">
              <div class="card-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                </svg>
              </div>
              <div class="about-card-title">Dual-Stack Verification</div>
              <div class="card-text">
                Guarantees zero regressions across both Python backend (Pytest / Django REST API) and modern frontend (Vite / Vue 3 / Monaco Editor / Vitest).
              </div>
            </AppCard>

            <AppCard variant="card" class="about-card">
              <div class="card-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
              </div>
              <div class="about-card-title">Strict Security &amp; Policy</div>
              <div class="card-text">
                Read-before-write invariant, workspace sandbox boundaries, environment variable secret masking, and real-time state synchronization via RTK Protocol.
              </div>
            </AppCard>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. ARCHITECTURE SECTION -->
    <div v-else-if="section === 'architecture'" class="about-pane">
      <div class="panel settings-panel">
        <div class="panel-head">
          <div>
            <div class="title">System Architecture &amp; Execution Model</div>
            <div class="desc">Detailed architectural pipeline of the AegisCode autonomous platform based on docs/architecture.md.</div>
          </div>
        </div>

        <div class="panel-body">
          <div class="arch-section">
            <div class="arch-title">1. Hybrid Asymmetric Split-Brain Model</div>
            <div class="arch-box mono">LLM (Brain) — Cloud Orchestrator:
  • Autonomous Reasoning &amp; Diff Synthesis
  • Tool Selection &amp; Argument Construction
  • Budgeted Context Window (&lt; 4,000 tokens)
                  ▲
                  │ JSON-RPC / API
                  ▼
Aegis Agent (Hands) — Local Worker:
  • AST Parsing, Semantic Vector Discovery &amp; FastEmbed
  • Interactive PTY Terminal (@xterm/xterm, zero-zombie)
  • FileWriteLock &amp; HITL Diff Approval (Supervised)
  • Context Budget Compaction, RRF Ranking &amp; Rollback Stash</div>
          </div>

          <div class="arch-section">
            <div class="arch-title">2. Aegis Agent Core Subsystems (src/agent_ai/)</div>
            <div class="arch-subsystems-grid">
              <div class="arch-subsystem-card">
                <span class="subsys-name">runtime/</span>
                <span class="subsys-desc">Core execution loop, turn controller, working state</span>
              </div>
              <div class="arch-subsystem-card">
                <span class="subsys-name">planning/</span>
                <span class="subsys-desc">Task decomposition, milestone tracking, replanning</span>
              </div>
              <div class="arch-subsystem-card">
                <span class="subsys-name">contextbuilder/</span>
                <span class="subsys-desc">Repo context compilation, system prompts, @file mentions</span>
              </div>
              <div class="arch-subsystem-card">
                <span class="subsys-name">contextbudget/</span>
                <span class="subsys-desc">Sliding window compaction, tool pruning (&lt; 4,000 tokens)</span>
              </div>
              <div class="arch-subsystem-card">
                <span class="subsys-name">tools/</span>
                <span class="subsys-desc">Filesystem, interactive terminal, source symbols, MCP</span>
              </div>
              <div class="arch-subsystem-card">
                <span class="subsys-name">providers/</span>
                <span class="subsys-desc">Unified LLM abstraction (Antigravity, Anthropic, OpenAI, Ollama)</span>
              </div>
              <div class="arch-subsystem-card">
                <span class="subsys-name">repointel/</span>
                <span class="subsys-desc">AST parsing, symbol indexing, repository graph</span>
              </div>
              <div class="arch-subsystem-card">
                <span class="subsys-name">permission/</span>
                <span class="subsys-desc">Policy gateway, path whitelists, command safety sandbox</span>
              </div>
              <div class="arch-subsystem-card">
                <span class="subsys-name">validation/</span>
                <span class="subsys-desc">Verification guards, syntax check, checkpoint recovery</span>
              </div>
              <div class="arch-subsystem-card">
                <span class="subsys-name">recovery/</span>
                <span class="subsys-desc">Loop breaker detection, backoff, and runtime self-healing</span>
              </div>
            </div>
          </div>

          <div class="arch-section">
            <div class="arch-title">3. 4-Phase Execution Lifecycle</div>
            <div class="arch-steps">
              <div class="arch-step">
                <span class="step-num">1</span>
                <div>
                  <div class="step-name">Task Preparation</div>
                  <div class="step-desc">Sanitization, repointel symbol map discovery, sandbox initialization.</div>
                </div>
              </div>
              <div class="arch-step">
                <span class="step-num">2</span>
                <div>
                  <div class="step-name">Context &amp; Budget</div>
                  <div class="step-desc">Assembly of prompts, contextbudget sliding compaction (&lt; 4,000 tokens).</div>
                </div>
              </div>
              <div class="arch-step">
                <span class="step-num">3</span>
                <div>
                  <div class="step-name">Continuous Execution Loop</div>
                  <div class="step-desc">Streaming CoT reasoning, structured tool execution, observation feedback, replanner.</div>
                </div>
              </div>
              <div class="arch-step">
                <span class="step-num">4</span>
                <div>
                  <div class="step-name">Termination &amp; Validation</div>
                  <div class="step-desc">Deterministic completion, syntax/test sanity validation, final report streaming.</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 3. LICENSE SECTION -->
    <div v-else-if="section === 'license'" class="about-pane">
      <div class="panel settings-panel">
        <div class="panel-head">
          <div>
            <div class="title">Open Source License</div>
            <div class="desc">AegisCode is open source software released under the terms of the MIT License.</div>
          </div>
          <button type="button" class="btn-aegis btn-ghost-a" @click="copyLicense">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
            <span>{{ copied ? "Copied!" : "Copy License" }}</span>
          </button>
        </div>

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
      </div>
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
  border: 1px solid var(--line, #1e1e2c) !important;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: none !important;
  transition: border-color 0.15s ease, background 0.15s ease;
}

[data-theme="light"] .about-card {
  background: rgba(0, 0, 0, 0.02) !important;
  border-color: var(--line, rgba(73, 64, 97, 0.1)) !important;
}

.about-card:hover {
  border-color: var(--accent, #a78bfa) !important;
  box-shadow: none !important;
  transform: none !important;
}

.card-icon {
  color: var(--accent, #a78bfa);
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

.arch-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.arch-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text);
}

.arch-box {
  padding: 12px 14px;
  background: var(--inset, rgba(0, 0, 0, 0.25));
  border: 1px solid var(--line);
  border-radius: 8px;
  font-size: 11.5px;
  color: var(--text-dim);
  white-space: pre-wrap;
  line-height: 1.5;
}

[data-theme="light"] .arch-box {
  background: rgba(0, 0, 0, 0.02);
  border-color: var(--line, rgba(73, 64, 97, 0.1));
}

.arch-subsystems-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 8px;
}

.arch-subsystem-card {
  padding: 8px 12px;
  background: var(--inset, rgba(0, 0, 0, 0.25));
  border: 1px solid var(--line);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

[data-theme="light"] .arch-subsystem-card {
  background: rgba(0, 0, 0, 0.02);
  border-color: var(--line, rgba(73, 64, 97, 0.1));
}

.subsys-name {
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
}

.subsys-desc {
  font-size: 10.5px;
  color: var(--text-faint);
  line-height: 1.35;
}

.arch-steps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
}

.arch-step {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-soft);
  border-radius: 8px;
}

.step-num {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--accent);
  color: var(--text);
  font-size: 11px;
  font-weight: 700;
  flex: 0 0 auto;
}

.step-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
}

.step-desc {
  font-size: 10.5px;
  color: var(--text-faint);
  line-height: 1.35;
  margin-top: 2px;
}

.license-card {
  padding: 14px 16px;
  background: var(--inset, rgba(0, 0, 0, 0.25));
  border: 1px solid var(--line);
  border-radius: 8px;
  margin-bottom: 16px;
}

[data-theme="light"] .license-card {
  background: rgba(0, 0, 0, 0.02);
  border-color: var(--line, rgba(73, 64, 97, 0.1));
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

[data-theme="light"] .credit-item {
  background: rgba(0, 0, 0, 0.02);
  border-color: var(--line, rgba(73, 64, 97, 0.1));
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
