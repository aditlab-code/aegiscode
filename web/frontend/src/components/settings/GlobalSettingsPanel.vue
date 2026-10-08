<script setup>
// Global Settings Aegis (`data/settings.json`).
//
// Sumber konfigurasi global Aegis = `data/settings.json` (satu-satunya).
// Komponen ini HANYA memanggil HTTP ke Django Gateway (`/api/settings`), yang
// meneruskan ke loader konfigurasi Aegis yang sudah ada
// (`agent_ai.config.settings`). TIDAK ada sumber/skema konfigurasi kedua di
// frontend: nilai yang ditampilkan = nilai AKTUAL dari backend, dan setiap
// simpan dikirim PARSIAL (hanya section terkait) sehingga key/setting lain di
// `data/settings.json` tidak hilang.
//
// Settings dipisah per SECTION (Server / Conversation / Logging / API Retry)
// agar tidak menjadi satu halaman panjang, dengan label + deskripsi jelas.
import { computed, onMounted, reactive, ref } from "vue";
import { getGlobalSettings, updateGlobalSettings } from "../../api";
import { terminateServer, isTerminating, serverTerminated } from "../../services/serverService.js";
import AppButton from "../ui/AppButton.vue";
import AppCard from "../ui/AppCard.vue";

const loading = ref(false);
const busy = ref(false);
const error = ref("");
const notice = ref("");
const showTerminateConfirm = ref(false);

function confirmTerminateServer() {
  showTerminateConfirm.value = true;
}

function cancelTerminateServer() {
  showTerminateConfirm.value = false;
}

async function executeTerminateServer() {
  showTerminateConfirm.value = false;
  busy.value = true;
  error.value = "";
  notice.value = "";
  const res = await terminateServer();
  busy.value = false;
  if (!res.success) {
    error.value = `Gagal menghentikan server: ${res.error}`;
  } else {
    notice.value = "Server AegisCode berhasil dihentikan. Seluruh sub-proses telah dibersihkan.";
  }
}

// Nilai AKTUAL dari backend (sumber kebenaran tampilan; bukan nilai lokal UI).
const actual = ref({
  port: null,
  compression: { enabled: null },
  write_log_response_api: null,
  api_retry: { failed_count: null, failed_sleep: null },
});

// Draft form per section (diisi dari `actual` setiap kali load).
const form = reactive({
  port: 8000,
  compression_enabled: false,
  write_log_response_api: false,
  failed_count: 3,
  failed_sleep: 0,
});

const actualLines = computed(() => [
  { label: "port", value: String(actual.value.port ?? "—") },
  { label: "compression.enabled", value: String(actual.value.compression?.enabled) },
  { label: "write_log_response_api", value: String(actual.value.write_log_response_api) },
  { label: "api_retry.failed_count", value: String(actual.value.api_retry?.failed_count) },
  { label: "api_retry.failed_sleep", value: String(actual.value.api_retry?.failed_sleep) },
]);
// Isi draft dari nilai AKTUAL backend.
function applyActual(settings) {
  actual.value = settings;
  form.port = settings.port;
  form.compression_enabled = !!(settings.compression || {}).enabled;
  form.write_log_response_api = !!settings.write_log_response_api;
  const retry = settings.api_retry || {};
  form.failed_count = retry.failed_count;
  form.failed_sleep = retry.failed_sleep;
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const data = await getGlobalSettings();
    applyActual(data.settings || {});
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    loading.value = false;
  }
}

// Simpan PARSIAL: hanya key milik section yang dikirim. Backend melakukan
// deep-merge ke `data/settings.json` sehingga key lain dipertahankan.
async function save(patch, okMessage) {
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    const data = await updateGlobalSettings(patch);
    applyActual(data.settings || {});
    notice.value = okMessage;
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    busy.value = false;
  }
}

function saveServer() {
  save({ port: Number(form.port) }, "Port disimpan.");
}
function saveConversation() {
  save(
    { compression: { enabled: form.compression_enabled } },
    "Compression disimpan."
  );
}
function saveLogging() {
  save({ write_log_response_api: form.write_log_response_api }, "Logging disimpan.");
}
function saveRetry() {
  save(
    {
      api_retry: {
        failed_count: Number(form.failed_count),
        failed_sleep: Number(form.failed_sleep),
      },
    },
    "API retry disimpan."
  );
}

function reset() {
  applyActual(actual.value);
  notice.value = "";
  error.value = "";
}

onMounted(load);
</script>

<template>
  <AppCard variant="panel" class="settings-panel gs-panel">
    <template #header>
      <div class="panel-head">
        <div class="title">Global Settings</div>
      </div>
    </template>

    <div class="panel-body">
      <div v-if="error" class="gs-alert err">{{ error }}</div>
      <div v-if="notice" class="gs-alert ok">{{ notice }}</div>

      <!-- Scope Badge -->
      <div class="gs-scope">
        <span class="gs-scope-badge">Global AegisCode Settings</span>
        <span class="gs-scope-note">
          Berlaku untuk seluruh AegisCode (semua project).
          <span class="mono">data/settings.json</span>
        </span>
        <span class="gs-scope-hint">
          Untuk konfigurasi &amp; policy per project, buka
          <span class="mono">Sidebar -&gt; Projects -&gt; Project Settings / Policy</span>.
        </span>
      </div>

      <div class="gs-sub-divider"></div>

      <!-- Section: Server -->
      <div class="gs-sub-section">
        <div class="gs-sub-header">
          <div class="gs-sub-title">Server</div>
          <div class="gs-sub-desc">Port lokal yang dipakai AegisCode saat dijalankan.</div>
        </div>

        <div class="gs-row">
          <div class="gs-label">
            <div class="gs-name">Port</div>
            <div class="gs-help">
              Port HTTP gateway AegisCode (1–65535). Perubahan berlaku saat AegisCode dijalankan ulang.
            </div>
          </div>
          <div class="gs-control">
            <input
              v-model.number="form.port"
              class="gs-input"
              type="number"
              min="1"
              max="65535"
              step="1"
              inputmode="numeric"
            />
          </div>
        </div>

        <div class="gs-row">
          <div class="gs-label">
            <div class="gs-name">Terminasi Server</div>
            <div class="gs-help">
              Hentikan server AegisCode beserta seluruh sub-proses anak (PTY slave, background tasks) secara deterministik (Zero-Zombie). Port akan segera dilepaskan.
            </div>
          </div>
          <div class="gs-control">
            <AppButton
              variant="danger"
              size="sm"
              :disabled="isTerminating || serverTerminated"
              @click="confirmTerminateServer"
            >
              {{ isTerminating ? "Menghentikan..." : (serverTerminated ? "Server Berhenti" : "Hentikan Server") }}
            </AppButton>
          </div>
        </div>

        <!-- Konfirmasi Penghentian Server -->
        <div v-if="showTerminateConfirm" class="gs-confirm-box">
          <div class="gs-confirm-title">Konfirmasi Penghentian Server</div>
          <div class="gs-confirm-desc">
            Apakah Anda yakin ingin menghentikan server AegisCode? Seluruh koneksi dan sesi terminal PTY aktif akan ditutup secara aman.
          </div>
          <div class="gs-confirm-actions">
            <AppButton variant="ghost" size="sm" @click="cancelTerminateServer">Batal</AppButton>
            <AppButton variant="danger" size="sm" @click="executeTerminateServer">Ya, Hentikan Server</AppButton>
          </div>
        </div>

        <div class="gs-actions">
          <AppButton variant="ghost" size="sm" :disabled="busy" @click="reset">Reset</AppButton>
          <AppButton variant="primary" size="sm" :disabled="busy" @click="saveServer">Save</AppButton>
        </div>
      </div>

      <div class="gs-sub-divider"></div>

      <!-- Section: Conversation Context -->
      <div class="gs-sub-section">
        <div class="gs-sub-header">
          <div class="gs-sub-title">Conversation</div>
          <div class="gs-sub-desc">Perilaku konteks percakapan sebelum dikirim ke model.</div>
        </div>

        <div class="gs-row">
          <div class="gs-label">
            <div class="gs-name">Conversation compression</div>
            <div class="gs-help">
              Aktifkan peringkasan/pemadatan riwayat percakapan saat konteks mendekati batas — hemat token, tetapi detail lama bisa diringkas.
            </div>
          </div>
          <div class="gs-control">
            <label class="slider-toggle gs-switch">
              <input v-model="form.compression_enabled" type="checkbox" />
              <span class="slider-track gs-track"><span class="slider-thumb gs-thumb"></span></span>
              <span class="slider-state gs-state">{{ form.compression_enabled ? "Enabled" : "Disabled" }}</span>
            </label>
          </div>
        </div>

        <div class="gs-actions">
          <AppButton variant="ghost" size="sm" :disabled="busy" @click="reset">Reset</AppButton>
          <AppButton variant="primary" size="sm" :disabled="busy" @click="saveConversation">Save</AppButton>
        </div>
      </div>

      <div class="gs-sub-divider"></div>

      <!-- Section: Logging -->
      <div class="gs-sub-section">
        <div class="gs-sub-header">
          <div class="gs-sub-title">Logging</div>
          <div class="gs-sub-desc">Pencatatan response mentah API provider per task.</div>
        </div>

        <div class="gs-row">
          <div class="gs-label">
            <div class="gs-name">Log API responses</div>
            <div class="gs-help">
              Simpan setiap response provider ke <span class="mono">.aegis/log/response/&lt;task_id&gt;.json</span> pada project target. Berguna untuk diagnosis, tetapi menambah berkas di disk.
            </div>
          </div>
          <div class="gs-control">
            <label class="slider-toggle gs-switch">
              <input v-model="form.write_log_response_api" type="checkbox" />
              <span class="slider-track gs-track"><span class="slider-thumb gs-thumb"></span></span>
              <span class="slider-state gs-state">{{ form.write_log_response_api ? "Enabled" : "Disabled" }}</span>
            </label>
          </div>
        </div>

        <div class="gs-actions">
          <AppButton variant="ghost" size="sm" :disabled="busy" @click="reset">Reset</AppButton>
          <AppButton variant="primary" size="sm" :disabled="busy" @click="saveLogging">Save</AppButton>
        </div>
      </div>

      <div class="gs-sub-divider"></div>

      <!-- Section: API Retry -->
      <div class="gs-sub-section">
        <div class="gs-sub-header">
          <div class="gs-sub-title">API Retry</div>
          <div class="gs-sub-desc">Perilaku pengulangan request saat panggilan API provider gagal.</div>
        </div>

        <div class="gs-row">
          <div class="gs-label">
            <div class="gs-name">Retry attempts</div>
            <div class="gs-help">
              Jumlah pengulangan SETELAH request gagal (0 = tanpa retry). Total percobaan = 1 percobaan awal + nilai ini.
            </div>
          </div>
          <div class="gs-control">
            <input
              v-model.number="form.failed_count"
              class="gs-input"
              type="number"
              min="0"
              max="1000"
              step="1"
              inputmode="numeric"
            />
          </div>
        </div>

        <div class="gs-row">
          <div class="gs-label">
            <div class="gs-name">Retry delay (seconds)</div>
            <div class="gs-help">
              Jeda tunggu sebelum setiap pengulangan. 0 = langsung mengulang tanpa jeda.
            </div>
          </div>
          <div class="gs-control">
            <input
              v-model.number="form.failed_sleep"
              class="gs-input"
              type="number"
              min="0"
              max="3600"
              step="0.1"
              inputmode="decimal"
            />
          </div>
        </div>

        <div class="gs-actions">
          <AppButton variant="ghost" size="sm" :disabled="busy" @click="reset">Reset</AppButton>
          <AppButton variant="primary" size="sm" :disabled="busy" @click="saveRetry">Save</AppButton>
        </div>
      </div>

      <div class="gs-sub-divider"></div>

      <!-- Section: Actual values -->
      <div class="gs-sub-section">
        <div class="gs-sub-header">
          <div class="gs-sub-title">Actual values</div>
          <div class="gs-sub-desc">
            Nilai yang benar-benar dibaca AegisCode dari <span class="mono">data/settings.json</span>.
          </div>
        </div>
        <div class="gs-actual-grid">
          <div v-for="line in actualLines" :key="line.label" class="kv">
            <span class="k mono">{{ line.label }}</span>
            <span class="v mono">{{ line.value }}</span>
          </div>
        </div>
      </div>
    </div>
  </AppCard>
</template>

<style scoped>
.gs-scope {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.gs-scope-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.3px;
  text-transform: uppercase;
  color: var(--accent-muted);
  background: rgba(45, 125, 78, 0.18);
  border: 1px solid rgba(45, 125, 78, 0.35);
}
.gs-scope-note {
  font-size: 12px;
  color: var(--text-dim);
}
.gs-scope-note .mono,
.gs-scope-hint .mono {
  font-family: var(--mono);
}
.gs-scope-hint {
  width: 100%;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--text-faint);
}

.gs-alert {
  padding: 10px 12px;
  border-radius: 9px;
  font-size: 12.5px;
  border: 1px solid var(--border-soft);
  margin-bottom: 12px;
}
.gs-alert.err {
  color: var(--alert-err-text);
  background: var(--alert-err-bg);
  border-color: var(--alert-err-border);
}
.gs-alert.ok {
  color: var(--alert-ok-text);
  background: var(--alert-ok-bg);
  border-color: var(--alert-ok-border);
}

.gs-sub-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.gs-sub-header {
  margin-bottom: 2px;
}
.gs-sub-title {
  font-size: 13.5px;
  font-weight: 650;
  color: var(--text);
}
.gs-sub-desc {
  font-size: 11.5px;
  color: var(--text-dim);
  margin-top: 2px;
}
.gs-sub-divider {
  height: 1px;
  background: var(--line, var(--border-soft));
  margin: 14px 0;
}
.gs-actual-grid {
  display: grid;
  gap: 8px;
}

.gs-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-soft);
}
.gs-row:last-of-type {
  border-bottom: 0;
}
.gs-label {
  min-width: 0;
}
.gs-name {
  font-size: 13px;
  font-weight: 650;
  color: var(--text);
}
.gs-help {
  margin-top: 3px;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--text-faint);
  max-width: 520px;
}
.gs-help .mono {
  font-family: var(--mono);
}
.gs-control {
  flex: 0 0 auto;
}

.gs-input {
  width: 140px;
  padding: 8px 12px;
  border-radius: 9px;
  border: 1px solid var(--border);
  background: var(--bg-elev);
  color: var(--text);
  font-size: 12.5px;
  font-family: var(--mono);
  text-align: right;
}
.gs-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(45, 125, 78, 0.20);
}

.gs-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

/* Toggle switch (checkbox asli tetap dipakai -> aksesibel). */
.gs-switch,
.slider-toggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
  position: relative;
}
.gs-switch input,
.slider-toggle input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
.gs-track,
.slider-track {
  position: relative;
  width: 40px;
  height: 22px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.09);
  border: 1px solid var(--border);
  transition: background 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
  box-sizing: border-box;
}
:global([data-theme="light"]) .gs-track,
:global([data-theme="light"]) .slider-track {
  background: rgba(0, 0, 0, 0.08);
  border-color: var(--border);
}
.gs-thumb,
.slider-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--text-faint);
  transition: transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), background 0.18s ease;
}
.gs-switch input:checked + .gs-track,
.slider-toggle input:checked + .slider-track {
  background: var(--accent);
  border-color: var(--accent);
}
.gs-switch input:checked + .gs-track .gs-thumb,
.slider-toggle input:checked + .slider-track .slider-thumb {
  transform: translateX(18px);
  background: var(--text);
}
.gs-switch input:focus-visible + .gs-track,
.slider-toggle input:focus-visible + .slider-track {
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.gs-state,
.slider-state {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-dim);
  min-width: 66px;
}

.btn-danger-a {
  background: var(--alert-err-bg);
  color: var(--err);
  border: 1px solid var(--alert-err-border);
  padding: 6px 14px;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 550;
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-danger-a:hover:not(:disabled) {
  background: var(--alert-err-bg);
  border-color: var(--err);
}
.btn-danger-a:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.gs-confirm-box {
  margin: 12px 0;
  padding: 12px 14px;
  border-radius: 9px;
  border: 1px solid var(--alert-err-border);
  background: var(--alert-err-bg);
}
.gs-confirm-title {
  font-size: 13px;
  font-weight: 650;
  color: var(--err);
  margin-bottom: 4px;
}
.gs-confirm-desc {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-dim);
  margin-bottom: 10px;
}
.gs-confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
