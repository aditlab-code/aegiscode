<script setup>
// Project Launcher (#52 rework) — halaman awal sebelum Workbench.
//
// Single-user local app: memilih / membuat / membuka project (TIDAK ada login
// atau account). Data dari gateway (#50) yang sudah ada:
//   GET    /api/projects              -> daftar project
//   POST   /api/projects              -> buat project
//   DELETE /api/projects/<id>         -> hapus record project
//   GET    /api/active-project        -> project/session terakhir (pulihkan)
//
// Visual (dark AETHER): topbar, New Project,
// "lanjutkan project terakhir", dan daftar project (tabel).
import { computed, ref } from "vue";
// Versi AETHER dari SINGLE SOURCE OF TRUTH `data/version.json` (sama dengan
// footer Workbench). TIDAK ada version hardcoded di launcher ini.
import { AEGIS_VERSION } from "../version.js";
import { pickFolder } from "../api.js";

const props = defineProps({
  projects: { type: Array, default: () => [] },
  // Project/session terakhir (persisted active project) untuk "buka kembali".
  lastProject: { type: Object, default: null },
  busy: { type: Boolean, default: false },
  isDark: { type: Boolean, default: true },
});
const emit = defineEmits(["open", "create", "delete", "setTheme"]);

const name = ref("");
const path = ref("");
const confirmDelete = ref(null);

// --- Folder picker (dialog native OS lewat backend) -------------------------
// Browser TIDAK bisa memilih folder dengan path absolut (File API hanya
// memberi path relatif), jadi dialog Finder dibuka oleh backend.
const pickBusy = ref(false);
const pickError = ref("");
// Nilai `name` terakhir hasil autofill — dipakai aturan sticky:
// nama kosong -> isi; sama dengan autofill sebelumnya -> ikuti folder baru;
// nama diketik user sendiri -> JANGAN ditimpa (anti data-loss).
const autoName = ref("");

function folderName(p) {
  const parts = String(p).split(/[\\/]+/).filter(Boolean);
  return parts.length ? parts[parts.length - 1] : "";
}

async function browseFolder() {
  if (pickBusy.value) return;
  pickBusy.value = true;
  pickError.value = "";
  try {
    const res = await pickFolder();
    if (res && res.ok && res.path) {
      path.value = res.path;
      const base = folderName(res.path);
      if (base && (!name.value.trim() || name.value === autoName.value)) {
        name.value = base;
        autoName.value = base;
      }
    } else if (res && res.reason && res.reason !== "cancelled") {
      pickError.value = res.message || "Folder picker gagal.";
    }
    // "cancelled" = hasil normal (user menutup dialog) -> diam.
  } catch (e) {
    pickError.value = e?.message || "Folder picker gagal.";
  } finally {
    pickBusy.value = false;
  }
}

const canCreate = computed(() => Boolean(name.value.trim() && path.value.trim()));
function openProject(projectId) {
  if (props.busy || !projectId) return;
  emit("open", projectId);
}

function submitForm() {
  const n = name.value.trim();
  const p = path.value.trim();
  if (!n || !p) return;
  emit("create", { name: n, path: p });
  name.value = "";
  path.value = "";
  autoName.value = "";
  pickError.value = "";
}

// Tandai project yang sama dengan "project terakhir" (status aktif).
function isLast(project) {
  return Boolean(props.lastProject && props.lastProject.id === project.id);
}

function relTime(iso) {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  const sec = Math.floor((Date.now() - t) / 1000);
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} hour${hr > 1 ? "s" : ""} ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day} day${day > 1 ? "s" : ""} ago`;
  return new Date(t).toLocaleDateString();
}

function lastUsed(project) {
  return relTime(project.last_opened_at || project.updated_at);
}

function askDelete(project) {
  confirmDelete.value = project;
}

function cancelDelete() {
  confirmDelete.value = null;
}

function doDelete() {
  if (confirmDelete.value) emit("delete", confirmDelete.value.id);
  confirmDelete.value = null;
}
</script>

<template>
  <div class="pl-root">
    <!-- ===================== TOP BAR ===================== -->
    <header class="pl-topbar">
      <div class="pl-brand">
        <span class="pl-logo">AE</span>
        <span class="pl-brand-name">AegisCode</span>
        <span class="pl-brand-sub">PROJECTS</span>
      </div>
      <div class="pl-topbar-right">
        <div class="theme-toggle-group" role="group" aria-label="Theme selector">
          <button
            class="theme-toggle-btn"
            :class="{ active: isDark }"
            type="button"
            @click="emit('setTheme', 'dark')"
            title="Dark theme"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
            </svg>
            <span>Dark</span>
          </button>
          <button
            class="theme-toggle-btn"
            :class="{ active: !isDark }"
            type="button"
            @click="emit('setTheme', 'light')"
            title="Light theme"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
            <span>Light</span>
          </button>
        </div>
        <span class="pl-pill"><span class="pl-dot"></span> Local</span>
        <span class="pl-pill">v{{ AEGIS_VERSION }}</span>
      </div>
    </header>

    <main class="pl-shell">
      <div class="pl-page-head">
        <h1>Projects</h1>
        <p>Create and open AegisCode workspaces.</p>
      </div>

      <!-- ============== LAST SESSION (bila ada) ============== -->
      <section v-if="lastProject" class="pl-panel pl-resume">
        <div class="pl-panel-head">
          <div>
            <div class="pl-title">Continue where you left off</div>
            <div class="pl-desc">Last opened project.</div>
          </div>
          <span class="pl-pill"><span class="pl-dot"></span> Last used</span>
        </div>
        <div class="pl-resume-body">
          <div class="pl-cell-name">
            <span class="pl-ico">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
            </span>
            <div>
              <div class="pl-name">{{ lastProject.name }}</div>
              <div class="pl-meta">{{ lastProject.path }}</div>
            </div>
          </div>
          <button
            type="button"
            class="pl-btn pl-btn-primary"
            :disabled="busy"
            @click="openProject(lastProject.id)"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
            Open Project
          </button>
        </div>
      </section>

      <!-- ===================== NEW PROJECT ===================== -->
      <section class="pl-panel">
        <div class="pl-panel-head">
          <div>
            <div class="pl-title">New Project</div>
            <div class="pl-desc">Create a new AegisCode workspace.</div>
          </div>
        </div>
        <form class="pl-form" @submit.prevent="submitForm">
          <div class="pl-field">
            <label for="np-name">Project Name</label>
            <input
              id="np-name"
              v-model="name"
              class="pl-input"
              type="text"
              placeholder="e.g. Kuis Bahasa Arab"
            />
          </div>
          <div class="pl-field">
            <label for="np-path">Workspace / Project Path</label>
            <div class="pl-path">
              <span class="pl-path-ico">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
              </span>
              <input
                id="np-path"
                v-model="path"
                type="text"
                placeholder="/Users/you/projects/my-app"
                @input="pickError = ''"
              />
              <button
                type="button"
                class="pl-btn pl-btn-browse"
                :disabled="pickBusy || busy"
                title="Pilih folder dengan dialog Finder / file manager"
                @click="browseFolder"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
                {{ pickBusy ? "Membuka…" : "Browse…" }}
              </button>
            </div>
            <div v-if="pickError" class="pl-field-error">{{ pickError }}</div>
          </div>
          <div class="pl-form-actions">
            <button
              class="pl-btn pl-btn-primary"
              type="submit"
              :disabled="busy || !canCreate"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
              Create Project
            </button>
          </div>
        </form>
      </section>

      <!-- ===================== PROJECT LIST ===================== -->
      <section class="pl-panel pl-panel-list">
        <div class="pl-panel-head">
          <div>
            <div class="pl-title">Projects</div>
            <div class="pl-desc">{{ projects.length }} workspace{{ projects.length === 1 ? "" : "s" }}</div>
          </div>
        </div>

        <div v-if="!projects.length" class="pl-empty">
          No projects yet. Create your first project.
        </div>

        <table v-else class="pl-table">
          <thead>
            <tr>
              <th style="width: 30%">Project</th>
              <th style="width: 32%">Path</th>
              <th style="width: 14%">Status</th>
              <th style="width: 14%">Last Used</th>
              <th style="width: 12%; text-align: right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="p in projects"
              :key="p.id"
              class="pl-row"
              :class="{ selected: isLast(p) }"
              @click="openProject(p.id)"
            >
              <td>
                <div class="pl-cell-name">
                  <span class="pl-ico">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
                  </span>
                  <div>
                    <div class="pl-name">{{ p.name }}</div>
                    <div class="pl-meta">{{ (p.id || "").slice(0, 8) }}</div>
                  </div>
                </div>
              </td>
              <td><span class="pl-mono" :title="p.path">{{ p.path }}</span></td>
              <td>
                <span class="pl-status" :class="isLast(p) ? 'on' : 'off'">
                  <span class="pl-status-dot"></span>{{ isLast(p) ? "Active" : "Ready" }}
                </span>
              </td>
              <td><span class="pl-mono">{{ lastUsed(p) }}</span></td>
              <td>
                <div class="pl-row-actions">
                  <button
                    type="button"
                    class="pl-icon-btn"
                    title="Open"
                    @click.stop="openProject(p.id)"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
                  </button>
                  <button
                    type="button"
                    class="pl-icon-btn danger project-delete"
                    title="Delete project record"
                    @click.stop="askDelete(p)"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></svg>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </main>

    <!-- Delete confirmation -->
    <div v-if="confirmDelete" class="modal-backdrop" @click.self="cancelDelete">
      <div class="modal">
        <div class="modal-title">Delete "{{ confirmDelete.name }}"?</div>
        <div class="modal-body">The project record will be removed. The project files will not be deleted.</div>
        <div class="modal-actions">
          <button type="button" class="btn-ghost" @click="cancelDelete">Cancel</button>
          <button type="button" class="btn-danger" @click="doDelete">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>

