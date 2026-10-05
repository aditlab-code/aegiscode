<script setup>
import { ref } from "vue";
import { AETHER_VERSION } from "../version.js";

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
                <span class="chip chip-sm ok">v{{ AETHER_VERSION }}</span>
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
            <div class="about-card">
              <div class="card-icon">🧠</div>
              <div class="card-head">Hybrid 5-Stage CoT Protocol</div>
              <div class="card-text">
                Enforces systematic reasoning: Intent Assessment &rarr; Architectural Analysis (YAGNI Check) &rarr; Step Action Planning &rarr; Execution Reflection Loop &rarr; Independent Verification.
              </div>
            </div>

            <div class="about-card">
              <div class="card-icon">🏢</div>
              <div class="card-head">Oh My Company (OMC) Hierarchy</div>
              <div class="card-text">
                Organizes 13 specialized autonomous agents across Executive, Production, Operations, and QA/Security departments structured in a resilient star topology.
              </div>
            </div>

            <div class="about-card">
              <div class="card-icon">⚡</div>
              <div class="card-head">Dual-Stack Verification</div>
              <div class="card-text">
                Guarantees zero regressions across both Python backend (Pytest / Django REST API) and modern frontend (Vite / Vue 3 / Monaco Editor / Vitest).
              </div>
            </div>

            <div class="about-card">
              <div class="card-icon">🔒</div>
              <div class="card-head">Strict Security &amp; Policy</div>
              <div class="card-text">
                Read-before-write invariant, workspace sandbox boundaries, environment variable secret masking, and real-time state synchronization via RTK Protocol.
              </div>
            </div>
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
            <div class="desc">Detailed architectural pipeline of the AETHER autonomous platform.</div>
          </div>
        </div>

        <div class="panel-body">
          <div class="arch-section">
            <div class="arch-title">1. OMC Corporate Hierarchy (Star Topology)</div>
            <div class="arch-box mono">
              Executive Department:
                CEO [adit-ceo] &lt;---&gt; CTO [nisa-cto]
                                          |
                      +-------------------+-------------------+
                      |                   |                   |
               Production Dept     Operations Dept     QA &amp; Security Dept
               - citra-lead        - rini-lead         - owi-lead
               - dani-architect    - putri-architect   - pentester
               - gita-coder        - taufik-coder      - budi-devops
               - hadi-tester       - umar-tester
            </div>
          </div>

          <div class="arch-section">
            <div class="arch-title">2. 4-Role Core Delivery Pipeline</div>
            <div class="arch-steps">
              <div class="arch-step">
                <span class="step-num">1</span>
                <div>
                  <div class="step-name">Lead Orchestration</div>
                  <div class="step-desc">Decomposition, scope curation, task boundary assignment.</div>
                </div>
              </div>
              <div class="arch-step">
                <span class="step-num">2</span>
                <div>
                  <div class="step-name">Architect Design</div>
                  <div class="step-desc">Interface definitions, dependency tree mapping, YAGNI check.</div>
                </div>
              </div>
              <div class="arch-step">
                <span class="step-num">3</span>
                <div>
                  <div class="step-name">Coder Implementation</div>
                  <div class="step-desc">Lean, production-grade code adhering strictly to contracts.</div>
                </div>
              </div>
              <div class="arch-step">
                <span class="step-num">4</span>
                <div>
                  <div class="step-name">QA Tester Verification</div>
                  <div class="step-desc">Independent validation, automated test suites, clean exit check.</div>
                </div>
              </div>
            </div>
          </div>

          <div class="arch-section">
            <div class="arch-title">3. Continuous Runtime Loop</div>
            <div class="arch-box mono">
              LLM Call &rarr; Tool Invocation &rarr; Observation &rarr; Reflection &rarr; Dynamic Replanning
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
            <div class="desc">AETHER is open source software released under the terms of the MIT License.</div>
          </div>
          <button type="button" class="btn-aether btn-ghost-a" @click="copyLicense">
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
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-soft);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-icon {
  font-size: 18px;
  margin-bottom: 2px;
}

.card-head {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text);
}

.card-text {
  font-size: 11px;
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
  background: var(--bg-deep, #100e18);
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  font-size: 11.5px;
  color: var(--text-dim);
  white-space: pre-wrap;
  line-height: 1.5;
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
  color: #ffffff;
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
  background: var(--bg-deep, #100e18);
  border: 1px solid var(--border-soft);
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
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-soft);
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
