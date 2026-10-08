<script setup>
// Settings page (Configuration).
//
// Mengelola konfigurasi LLM AETHER lewat endpoint backend (`/api/llm/*`) yang
// MEMAKAI LLMConfigService AETHER existing. Frontend HANYA memanggil HTTP:
// tidak ada logic agent, tidak ada model konfigurasi kedua.
//
// Keamanan: backend TIDAK pernah mengirim nilai secret .env — hanya versi
// `masked`. Frontend tidak menyimpan/menampilkan nilai API key.
import { computed, onMounted, reactive, ref, watch } from "vue";
import {
  getLLMConfig,
  createLLMProvider,
  updateLLMProvider,
  deleteLLMProvider,
  createLLMModel,
  updateLLMModel,
  deleteLLMModel,
  createLLMCredential,
  deleteLLMCredential,
  testLLMProvider,
  updateGlobalSettings,
} from "../../api";
import GlobalSettingsPanel from "./GlobalSettingsPanel.vue";
import AgentSettingsPanel from "./AgentSettingsPanel.vue";
import AppearanceSettingsPanel from "./AppearanceSettingsPanel.vue";
import RemoteCompanionSettings from "./RemoteCompanionSettings.vue";
import AppButton from "../ui/AppButton.vue";
import AppCard from "../ui/AppCard.vue";

const props = defineProps({
  // Konfigurasi runtime aktif dari AETHER (provider/model/mode + instance).
  config: { type: Object, default: () => ({}) },
  activeSection: { type: String, default: "" },
  hideTabs: { type: Boolean, default: false },
  providerInstanceId: { type: String, default: "" },
  modelId: { type: String, default: "" },
  mode: { type: String, default: "" },
  initialProviders: { type: Array, default: () => [] },
});

const emit = defineEmits([
  "refresh-config",
  "update:provider-instance-id",
  "update:model-id",
  "update:mode",
]);

// Halaman Settings dipisah menjadi SECTION (tab) agar tidak menjadi satu
// halaman panjang:
//   - "general"   : Global Settings AETHER (`data/settings.json`).
//   - "agent"     : System Prompt / Agent Instructions Agent
//                   (`data/settings.json` -> `agent.system_prompt`).
//   - "providers" : konfigurasi provider/model/credential (LLM Config AETHER).
// Default = General (konfigurasi global aplikasi).
const activeTab = ref(props.activeSection || "general");
watch(
  () => props.activeSection,
  (val) => {
    if (val) activeTab.value = val;
  }
);

const loading = ref(false);
const busy = ref(false);
const error = ref("");
const notice = ref("");

const credentials = ref([]);
const providerTypes = ref([]);
const providers = ref(props.initialProviders?.length ? [...props.initialProviders] : []);
watch(
  () => props.initialProviders,
  (val) => {
    if (Array.isArray(val) && val.length) {
      providers.value = [...val];
    }
  }
);

// Form: provider instance (mode CREATE bila id kosong, mode EDIT bila terisi).
const providerForm = reactive({
  name: "",
  provider_type: "",
  api_key_env: "",
  api_url: "",
  enabled: true,
});
// id instance yang sedang diedit ("" = tambah instance baru).
const editingProviderId = ref("");
// Form: credential (.env) baru.
const credentialForm = reactive({ name: "", value: "" });
// Draft nama model per provider instance (key = provider id).
const modelDrafts = reactive({});

const providerTypeSpec = computed(() => {
  const map = {};
  for (const t of providerTypes.value) map[t.key] = t;
  return map;
});
// Field api_key_env ditampilkan untuk provider cloud ATAU provider generik
// (custom) yang membolehkan nama env BEBAS. Disembunyikan HANYA untuk provider
// lokal murni yang tidak punya API key (mis. Ollama).
const showApiKeyEnv = computed(() => {
  const spec = providerTypeSpec.value[providerForm.provider_type];
  if (!spec) return true;
  return spec.requires_api_key !== false || spec.allow_custom_env === true;
});
// Nama env API key boleh dikosongkan (provider generik/lokal).
const apiKeyEnvOptional = computed(() => {
  const spec = providerTypeSpec.value[providerForm.provider_type];
  return spec ? spec.allow_custom_env === true || spec.requires_api_key === false : false;
});
const providerTypeLabel = computed(() => {
  const map = {};
  for (const t of providerTypes.value) map[t.key] = t.label;
  return map;
});
const credentialByName = computed(() => {
  const map = {};
  for (const c of credentials.value) map[c.name] = c;
  return map;
});

const availableProviders = computed(() => {
  const list = (props.config?.provider_instances && props.config.provider_instances.length)
    ? props.config.provider_instances
    : providers.value;
  if (list && list.length) return list;
  if (props.config?.provider) {
    return [{
      id: props.config.provider_instance_id || props.config.provider,
      name: props.config.provider,
      provider_type: props.config.provider,
      api_key_env: `${props.config.provider.toUpperCase()}_API_KEY`,
      api_key_present: false,
      models: props.config.model ? [{ id: props.config.model_id || props.config.model, model_name: props.config.model, enabled: true }] : [],
    }];
  }
  return [];
});

const activeInstance = computed(() => {
  const id = props.providerInstanceId || props.config?.provider_instance_id;
  const list = availableProviders.value;
  if (id) {
    const found = list.find((p) => p.id === id);
    if (found) return found;
  }
  if (props.config?.provider) {
    const foundByName = list.find((p) => p.id === props.config.provider || p.name.toLowerCase() === props.config.provider.toLowerCase());
    if (foundByName) return foundByName;
  }
  const enabled = list.find((p) => p.enabled !== false);
  return enabled || list[0] || null;
});

const availableModels = computed(() => {
  const inst = activeInstance.value;
  if (!inst) return [];
  if (inst.models && inst.models.length) return inst.models;
  if (props.config?.model) {
    return [{ id: props.config.model_id || props.config.model, model_name: props.config.model, enabled: true }];
  }
  return [];
});

const activeModelId = computed(() => {
  const inst = activeInstance.value;
  if (!inst) return "";
  const models = availableModels.value;
  if (props.modelId && models.some((m) => m.id === props.modelId)) {
    return props.modelId;
  }
  if (props.config?.model_id && models.some((m) => m.id === props.config.model_id)) {
    return props.config.model_id;
  }
  if (props.config?.model) {
    const foundByName = models.find((m) => m.id === props.config.model || m.model_name === props.config.model);
    if (foundByName) return foundByName.id;
  }
  const enabledModel = models.find((m) => m.enabled !== false);
  return enabledModel ? enabledModel.id : (models[0]?.id || "");
});

const activeModelName = computed(() => {
  const inst = activeInstance.value;
  if (!inst) return props.config?.model || "";
  const m = availableModels.value.find((x) => x.id === activeModelId.value);
  return m ? m.model_name : (props.config?.model || "");
});

const availableModes = computed(() => {
  const modes = props.config?.modes || ["autonomous", "architect", "pair-programming"];
  if (props.config?.mode && !modes.includes(props.config.mode)) {
    return [props.config.mode, ...modes];
  }
  return modes;
});

const activeMode = computed(() => {
  return props.mode || props.config?.mode || "autonomous";
});

const activeCred = computed(() => {
  const env = activeInstance.value?.api_key_env;
  return env ? credentialByName.value[env] : null;
});

const activeMaskedKey = computed(() => {
  return activeCred.value?.masked_value || "";
});

const showQuickKeyButton = computed(() => {
  const inst = activeInstance.value;
  if (!inst) return false;
  const spec = providerTypeSpec.value[inst.provider_type];
  if (spec && spec.requires_api_key === false) return false;
  return !!inst.api_key_env;
});

const activeCredBadgeClass = computed(() => {
  const inst = activeInstance.value;
  if (!inst) return "idle";
  const spec = providerTypeSpec.value[inst.provider_type];
  if (spec && spec.requires_api_key === false) return "ok";
  if (inst.api_key_present || activeMaskedKey.value) return "ok";
  return "warn";
});

const activeCredBadgeText = computed(() => {
  const inst = activeInstance.value;
  if (!inst) return "No Provider";
  const spec = providerTypeSpec.value[inst.provider_type];
  if (spec && spec.requires_api_key === false) return "No Key Required";
  if (inst.api_key_present || activeMaskedKey.value) return "Key Set";
  return "Key Missing";
});

function onSelectProvider(e) {
  const newId = e.target.value;
  emit("update:provider-instance-id", newId);
  const inst = (availableProviders.value || []).find((p) => p.id === newId);
  if (inst) {
    const firstModel = (inst.models || []).find((m) => m.enabled !== false) || inst.models?.[0];
    emit("update:model-id", firstModel ? firstModel.id : "");
  }
}

function onSelectModel(e) {
  emit("update:model-id", e.target.value);
}

async function onSelectMode(e) {
  const newMode = e.target.value;
  emit("update:mode", newMode);
  try {
    await updateGlobalSettings({ agent: { default_mode: newMode } });
    notice.value = `Default mode set to '${newMode}'.`;
  } catch (err) {
    error.value = `Failed to persist default mode: ${err.message || err}`;
  }
}

// Quick Key Modal State
const quickKeyModalOpen = ref(false);
const quickKeyEnvName = ref("");
const quickKeyValue = ref("");

function openQuickKeyModal(envName) {
  quickKeyEnvName.value = envName || activeInstance.value?.api_key_env || "";
  quickKeyValue.value = "";
  quickKeyModalOpen.value = true;
}

function closeQuickKeyModal() {
  quickKeyModalOpen.value = false;
  quickKeyEnvName.value = "";
  quickKeyValue.value = "";
}

async function submitQuickKey() {
  const name = quickKeyEnvName.value.trim();
  const val = quickKeyValue.value.trim();
  if (!name || !val) return;
  await run(async () => {
    await createLLMCredential({ name, value: val });
    closeQuickKeyModal();
  }, `API key ${name} saved to .env.`);
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const data = await getLLMConfig();
    credentials.value = data.credentials || [];
    providerTypes.value = data.provider_types || [];
    providers.value = data.providers || [];
    if (!providerForm.provider_type && providerTypes.value.length) {
      providerForm.provider_type = providerTypes.value[0].key;
      onProviderTypeChange();
    }
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    loading.value = false;
  }
}

// Jalankan aksi tulis, lalu muat ulang config (sumber kebenaran = backend).
async function run(action, okMessage) {
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    await action();
    await load();
    notice.value = okMessage;
    emit("refresh-config");
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    busy.value = false;
  }
}

// Isi default api_url / api_key_env dari katalog provider type (statis).
function onProviderTypeChange() {
  const spec = providerTypeSpec.value[providerForm.provider_type];
  if (!spec) return;
  providerForm.api_url = spec.default_api_url || "";
  if (spec.allow_custom_env) {
    // Provider generik "Custom OpenAI Compatible": TIDAK ada prefix tetap.
    // Jangan prefill nama provider tertentu — biarkan user mengisi bebas
    // (mis. GERRY_API_KEY). Bila sudah ada nilai, pertahankan.
    providerForm.api_key_env = providerForm.api_key_env || "";
  } else {
    // Provider lokal (Ollama) tidak butuh API key: kosongkan api_key_env.
    // Provider cloud tetap memakai <PREFIX>_API_KEY seperti sebelumnya.
    providerForm.api_key_env = spec.requires_api_key ? `${spec.env_prefix}_API_KEY` : "";
  }
}

function resetProviderForm() {
  providerForm.name = "";
  providerForm.api_key_env = "";
  providerForm.api_url = "";
  providerForm.enabled = true;
  editingProviderId.value = "";
  onProviderTypeChange();
}

// Muat instance terpilih ke form (mode edit).
function startEditProvider(p) {
  editingProviderId.value = p.id;
  providerForm.name = p.name || "";
  providerForm.provider_type = p.provider_type || "";
  providerForm.api_key_env = p.api_key_env || "";
  providerForm.api_url = p.api_url || "";
  providerForm.enabled = p.enabled !== false;
}

function cancelEditProvider() {
  resetProviderForm();
}

function submitProvider() {
  const payload = {
    name: providerForm.name,
    provider_type: providerForm.provider_type,
    // Provider lokal murni (Ollama) dikirim tanpa api_key_env; provider generik
    // (custom) boleh memakai api_key_env bebas (opsional).
    api_key_env: showApiKeyEnv.value ? providerForm.api_key_env : "",
    api_url: providerForm.api_url,
  };
  const editingId = editingProviderId.value;
  if (editingId) {
    run(async () => {
      await updateLLMProvider(editingId, payload);
      resetProviderForm();
    }, "Provider instance diperbarui.");
  } else {
    run(async () => {
      await createLLMProvider(payload);
      resetProviderForm();
    }, "Provider instance dibuat.");
  }
}

function toggleProvider(p) {
  run(() => updateLLMProvider(p.id, { enabled: !p.enabled }), "Provider diperbarui.");
}

async function removeProvider(p) {
  if (!window.confirm(`Hapus provider instance "${p.name}" beserta model-nya?`)) return;
  run(() => deleteLLMProvider(p.id), "Provider dihapus.");
}

function submitModel(p) {
  const name = (modelDrafts[p.id] || "").trim();
  if (!name) return;
  run(async () => {
    await createLLMModel({ provider_id: p.id, model_name: name });
    modelDrafts[p.id] = "";
  }, "Model ditambahkan.");
}

// Isi cepat nilai model "auto" (routing otomatis di sisi server) untuk provider
// yang mendukungnya — user tidak dipaksa memilih model konkret.
function setAutoModel(p) {
  modelDrafts[p.id] = "auto";
}

function toggleModel(m) {
  run(() => updateLLMModel(m.id, { enabled: !m.enabled }), "Model diperbarui.");
}

function removeModel(m) {
  run(() => deleteLLMModel(m.id), "Model dihapus.");
}

const testResults = reactive({});

async function testProvider(p) {
  const id = p.id;
  testResults[id] = "testing…";
  try {
    const result = await testLLMProvider(id);
    if (result.status === "ok") {
      testResults[id] = "Connection OK";
    } else {
      testResults[id] = `${result.detail || "Failed"}`;
    }
  } catch (e) {
    testResults[id] = `${e.message || e}`;
  }
  // Auto-clear setelah 8 detik
  setTimeout(() => { testResults[id] = ""; }, 8000);
}

function submitCredential() {
  run(async () => {
    await createLLMCredential(credentialForm.name, credentialForm.value);
    credentialForm.name = "";
    credentialForm.value = "";
  }, "Credential disimpan.");
}

function removeCredential(c) {
  const used = (c.used_by || []).length > 0;
  if (used && !window.confirm(`Credential dipakai oleh: ${c.used_by.join(", ")}. Tetap hapus?`)) {
    return;
  }
  run(() => deleteLLMCredential(c.name, used), "Credential dihapus.");
}

onMounted(() => {
  // Muat konfigurasi LLM hanya saat section Providers dibuka (lazy): tab
  // default adalah Global Settings, sehingga jalur read-only tidak terpanggil
  // tanpa perlu (perilaku LLM Config sendiri tidak diubah).
  if (activeTab.value === "providers") load();
});

watch(activeTab, (tab) => {
  if (tab === "providers" && !providers.value.length && !loading.value) load();
});
</script>

<template>
  <!-- Settings dipisah per SECTION (tab) agar tidak menjadi satu halaman
       panjang: "General" (Global Settings `data/settings.json`) dan
       "Providers" (LLM Config AETHER). -->
  <div v-if="!hideTabs" class="sv-tabs" role="tablist" aria-label="Settings sections">
    <button
      class="sv-tab"
      :class="{ active: activeTab === 'general' }"
      type="button"
      role="tab"
      :aria-selected="activeTab === 'general'"
      @click="activeTab = 'general'"
    >
      General
    </button>
    <button
      class="sv-tab"
      :class="{ active: activeTab === 'appearance' }"
      type="button"
      role="tab"
      :aria-selected="activeTab === 'appearance'"
      @click="activeTab = 'appearance'"
    >
      Appearance
    </button>
    <button
      class="sv-tab"
      :class="{ active: activeTab === 'agent' }"
      type="button"
      role="tab"
      :aria-selected="activeTab === 'agent'"
      @click="activeTab = 'agent'"
    >
      Agent
    </button>
    <button
      class="sv-tab"
      :class="{ active: activeTab === 'providers' }"
      type="button"
      role="tab"
      :aria-selected="activeTab === 'providers'"
      @click="activeTab = 'providers'"
    >
      Providers
    </button>
    <button
      class="sv-tab"
      :class="{ active: activeTab === 'companion' }"
      type="button"
      role="tab"
      :aria-selected="activeTab === 'companion'"
      @click="activeTab = 'companion'"
    >
      Companion
    </button>
  </div>

  <!-- ================= GENERAL: Global Settings AETHER ================= -->
  <GlobalSettingsPanel v-if="activeTab === 'general'" />

  <!-- ================= APPEARANCE: Theme & Appearance ================= -->
  <AppearanceSettingsPanel v-else-if="activeTab === 'appearance'" />

  <!-- ================= AGENT: System Prompt Agent ================= -->
  <AgentSettingsPanel v-else-if="activeTab === 'agent'" />

  <!-- ================= COMPANION: Remote Telegram Companion ================= -->
  <RemoteCompanionSettings v-else-if="activeTab === 'companion'" />

  <!-- ================= PROVIDERS: LLM Config AETHER ================= -->
  <template v-else>
  <!-- Runtime aktif (read-only summary dari AETHER). -->
  <!-- Runtime aktif (Configuration: Provider, model, credential, mode). -->
  <AppCard variant="panel" class="settings-panel">
    <template #header>
      <span class="title">Configuration</span>
      <div class="panel-actions sv-config-head-actions">
        <AppButton
          variant="ghost"
          size="sm"
          :disabled="loading || busy || !activeInstance"
          :busy="testResults[activeInstance?.id] === 'testing…'"
          title="Test connectivity to active provider"
          @click="testProvider(activeInstance)"
        >
          <span v-if="testResults[activeInstance?.id] === 'testing…'">Testing…</span>
          <span v-else>Test Connection</span>
        </AppButton>
      </div>
    </template>
    <div class="panel-body">
      <div v-if="error" class="sv-alert err">{{ error }}</div>
      <div v-if="notice" class="sv-alert ok">{{ notice }}</div>
      <div v-if="testResults[activeInstance?.id]" class="sv-test-result" style="margin-bottom: 12px;">
        {{ testResults[activeInstance.id] }}
      </div>
      <div v-if="loading" class="wb-empty">Memuat konfigurasi…</div>
      <div v-else class="sv-config-grid">
        <!-- Row 1: Active Provider -->
        <div class="sv-config-row">
          <label class="sv-config-label" for="active-provider-select">
            <span class="sv-config-title">Active Provider</span>
            <span class="sv-config-subtitle">Active instance for agent completions</span>
          </label>
          <div class="sv-config-control">
            <select
              id="active-provider-select"
              class="sv-select"
              :value="activeInstance?.id || ''"
              @change="onSelectProvider"
            >
              <option v-if="!availableProviders.length" value="" disabled>No providers available</option>
              <option
                v-for="p in availableProviders"
                :key="p.id"
                :value="p.id"
              >
                {{ p.name }} ({{ providerTypeLabel[p.provider_type] || p.provider_type }})
              </option>
            </select>
          </div>
        </div>

        <!-- Row 2: Active Model -->
        <div class="sv-config-row">
          <label class="sv-config-label" for="active-model-select">
            <span class="sv-config-title">Active Model</span>
            <span class="sv-config-subtitle">Model associated with selected provider</span>
          </label>
          <div class="sv-config-control">
            <select
              id="active-model-select"
              class="sv-select"
              :value="activeModelId"
              :disabled="!activeInstance || !availableModels.length"
              @change="onSelectModel"
            >
              <option v-if="!availableModels.length" value="" disabled>
                {{ activeInstance ? "No models configured (auto/custom)" : "Select provider first" }}
              </option>
              <option
                v-for="m in availableModels"
                :key="m.id"
                :value="m.id"
              >
                {{ m.model_name }} {{ m.enabled === false ? "(disabled)" : "" }}
              </option>
            </select>
          </div>
        </div>

        <!-- Row 3: Mode Selector -->
        <div class="sv-config-row">
          <label class="sv-config-label" for="active-mode-select">
            <span class="sv-config-title">Mode</span>
            <span class="sv-config-subtitle">Default runtime autonomy policy</span>
          </label>
          <div class="sv-config-control">
            <select
              id="active-mode-select"
              class="sv-select"
              :value="activeMode"
              @change="onSelectMode"
            >
              <option v-for="m in availableModes" :key="m" :value="m">
                {{ m }}
              </option>
            </select>
          </div>
        </div>

        <!-- Row 4: Credential & API Key Status -->
        <div class="sv-config-row">
          <div class="sv-config-label">
            <span class="sv-config-title">Credential &amp; Key</span>
            <span class="sv-config-subtitle">Authentication environment variable</span>
          </div>
          <div class="sv-config-control sv-cred-status-wrap">
            <div class="sv-cred-summary">
              <span class="mono sv-cred-env">{{ activeInstance?.api_key_env || "No API key" }}</span>
              <span v-if="activeMaskedKey" class="mono sv-cred-val">{{ activeMaskedKey }}</span>
              <span class="chip chip-sm" :class="activeCredBadgeClass">
                {{ activeCredBadgeText }}
              </span>
            </div>
            <button
              v-if="showQuickKeyButton"
              type="button"
              class="sv-mini"
              :disabled="busy"
              @click="openQuickKeyModal(activeInstance?.api_key_env)"
            >
              {{ (activeInstance?.api_key_present || activeMaskedKey) ? "Update Key" : "Set Key" }}
            </button>
          </div>
        </div>

        <!-- Row 5: Endpoint URL -->
        <div class="sv-config-row">
          <div class="sv-config-label">
            <span class="sv-config-title">Endpoint URL</span>
            <span class="sv-config-subtitle">Base URL target for API requests</span>
          </div>
          <div class="sv-config-control">
            <span class="mono sv-url-val">{{ activeInstance?.api_url || "Standard Gateway / Default" }}</span>
          </div>
        </div>


      </div>
    </div>
  </AppCard>

  <!-- Provider instance + model (relasi Provider -> Model). -->
  <AppCard variant="panel" class="settings-panel">
    <template #header>
      <span class="title">Providers &amp; Models</span>
    </template>
    <div class="panel-body">
      <div v-if="!providers.length" class="wb-empty">Belum ada provider instance.</div>

      <div v-for="p in providers" :key="p.id" class="sv-prov">
        <div class="sv-prov-head">
          <div class="sv-prov-id">
            <span class="avatar">{{ (p.name || "P").slice(0, 1).toUpperCase() }}</span>
            <div>
              <div class="sv-prov-name">
                {{ p.name }}
                <span class="chip chip-sm">{{ providerTypeLabel[p.provider_type] || p.provider_type }}</span>
              </div>
              <div class="sv-prov-meta">
                <span class="mono">{{ p.api_url || "—" }}</span>
                <span class="mono">· {{ p.api_key_env || "no api key" }}</span>
                <span class="mono" :class="p.api_key_present ? 'ok' : 'warn'">
                  · {{ p.api_key_present ? "key set" : "key missing" }}
                </span>
              </div>
            </div>
          </div>
          <div class="sv-actions">
            <AppButton
              variant="ghost"
              :disabled="busy"
              @click="toggleProvider(p)"
            >
              {{ p.enabled ? "Disable" : "Enable" }}
            </AppButton>
            <AppButton variant="ghost" :disabled="busy" @click="testProvider(p)">
              Test
            </AppButton>
            <AppButton variant="ghost" :disabled="busy" @click="startEditProvider(p)">
              Edit
            </AppButton>
            <AppButton variant="danger" :disabled="busy" @click="removeProvider(p)">
              Delete
            </AppButton>
          </div>
        </div>
        <div v-if="p.provider_type === 'antigravity'" class="sv-tip-box" title="Jalankan agy di terminal luar -> pilih akun Google -> copy token OAuth -> paste ke terminal">
          <span class="sv-tip-icon">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 2a7 7 0 0 0-7 7c0 2.38 1.19 4.47 3 5.74V17a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-2.26c1.81-1.27 3-3.36 3-5.74a7 7 0 0 0-7-7z"/>
              <line x1="9" y1="21" x2="15" y2="21"/>
            </svg>
          </span>
          <span><strong>Cara Login:</strong> Jalankan <code>agy</code> di terminal luar &rarr; verifikasi akun Google &rarr; salin token &rarr; tempel ke CLI. Kredensial tersimpan di <code>~/.gemini/oauth_creds.json</code>.</span>
        </div>
        <div class="sv-test-result" v-if="testResults[p.id]">{{ testResults[p.id] }}</div>

        <!-- Model milik provider instance ini. -->
        <div class="sv-models">
          <div v-if="!(p.models || []).length" class="sv-models-empty">Belum ada model.</div>
          <div v-for="m in p.models" :key="m.id" class="sv-model-row">
            <span class="mono">{{ m.model_name }}</span>
            <span class="sv-model-actions">
              <span class="status-tag" :class="m.enabled ? 'ok' : 'idle'">
                {{ m.enabled ? "enabled" : "disabled" }}
              </span>
              <button class="sv-mini" :disabled="busy" @click="toggleModel(m)">
                {{ m.enabled ? "Disable" : "Enable" }}
              </button>
              <button class="sv-mini danger" :disabled="busy" @click="removeModel(m)">Delete</button>
            </span>
          </div>

          <div class="sv-add-row">
            <input
              v-model="modelDrafts[p.id]"
              class="sv-input"
              placeholder="Model (mis. claude-sonnet-4-5, openai/gpt-4o-mini, deepseek-v4.1-flash, auto)"
              @keyup.enter="submitModel(p)"
            />
            <button
              v-if="p.requires_model === false || p.allow_custom_env"
              class="sv-mini"
              :disabled="busy"
              title="Set model ke 'auto' (routing otomatis)"
              @click="setAutoModel(p)"
            >
              Auto
            </button>
            <button class="btn-aegis btn-primary-a" :disabled="busy" @click="submitModel(p)">
              Add model
            </button>
          </div>
          <div v-if="p.requires_model === false" class="sv-models-empty">
            Model opsional untuk tipe ini — boleh diisi nilai routing seperti
            “auto”, atau dikosongkan bila server menentukan model sendiri.
          </div>
        </div>
      </div>

      <!-- Form: provider instance (create / edit). -->
      <div class="sv-form" :class="{ 'sv-form-editing': !!editingProviderId }">
        <div class="sv-form-title">
          {{ editingProviderId ? "Edit provider instance" : "Add provider instance" }}
        </div>
        <div class="sv-form-grid">
          <input
            v-model="providerForm.name"
            class="sv-input"
            placeholder="Nama instance (bebas, mis. Gerry)"
          />
          <select v-model="providerForm.provider_type" class="sv-input" @change="onProviderTypeChange">
            <option v-for="t in providerTypes" :key="t.key" :value="t.key">{{ t.label }}</option>
          </select>
          <input
            v-model="providerForm.api_url"
            class="sv-input"
            placeholder="Base URL (mis. http://gerry.com/v1)"
          />
          <input
            v-if="showApiKeyEnv"
            v-model="providerForm.api_key_env"
            class="sv-input"
            :placeholder="
              apiKeyEnvOptional
                ? 'API key env (opsional, mis. GERRY_API_KEY)'
                : 'Nama variabel .env API key (mis. OPENROUTER_API_KEY)'
            "
          />
        </div>
        <div class="sv-form-actions">
          <AppButton
            v-if="editingProviderId"
            variant="ghost"
            :disabled="busy"
            @click="cancelEditProvider"
          >
            Cancel
          </AppButton>
          <AppButton variant="primary" :disabled="busy" @click="submitProvider">
            {{ editingProviderId ? "Save changes" : "Create provider" }}
          </AppButton>
        </div>
      </div>
    </div>
  </AppCard>

  <!-- Credential (.env API key) — hanya versi masked yang ditampilkan. -->
  <AppCard variant="panel" class="settings-panel">
    <template #header>
      <div>
        <div class="title">API Credentials</div>
        <div class="desc">Disimpan di .env AegisCode. Nilai secret tidak pernah ditampilkan.</div>
      </div>
    </template>
    <div class="panel-body">
      <div v-if="!credentials.length" class="wb-empty">Belum ada credential.</div>

      <div v-for="c in credentials" :key="c.name" class="sv-cred">
        <div>
          <div class="sv-cred-name">
            <span class="mono">{{ c.name }}</span>
            <span class="chip chip-sm">{{ c.provider_label }}</span>
            <span class="status-tag" :class="c.is_set ? 'ok' : 'idle'">
              {{ c.is_set ? "set" : "missing" }}
            </span>
          </div>
          <div class="sv-cred-meta">
            <span class="mono">{{ c.masked || "—" }}</span>
            <span v-if="(c.used_by || []).length" class="mono">· used by: {{ c.used_by.join(", ") }}</span>
          </div>
        </div>
        <AppButton variant="danger" :disabled="busy" @click="removeCredential(c)">
          Delete
        </AppButton>
      </div>

      <!-- Form: set/simpan API key (.env). -->
      <div class="sv-form">
        <div class="sv-form-title">Set API key</div>
        <div class="sv-form-grid">
          <input
            v-model="credentialForm.name"
            class="sv-input"
            placeholder="Nama variabel .env (mis. OPENROUTER_API_KEY)"
          />
          <input
            v-model="credentialForm.value"
            class="sv-input"
            type="password"
            placeholder="Nilai API key"
            @keyup.enter="submitCredential"
          />
        </div>
        <div class="sv-form-actions">
          <AppButton variant="primary" :disabled="busy" @click="submitCredential">
            Save credential
          </AppButton>
        </div>
      </div>
    </div>
  </AppCard>
  </template>

  <!-- Quick Set Key Modal -->
  <div v-if="quickKeyModalOpen" class="unified-popup-backdrop sv-quick-key-overlay" @click.self="closeQuickKeyModal">
    <div class="unified-popup-card sv-quick-key-dialog" role="dialog" aria-modal="true" aria-labelledby="quick-key-title">
      <div class="unified-popup-head sv-quick-key-head">
        <div id="quick-key-title" class="unified-popup-title sv-quick-key-title">Set API Key for {{ quickKeyEnvName }}</div>
        <AppButton variant="ghost" size="sm" class="unified-popup-close-btn" @click="closeQuickKeyModal">&times;</AppButton>
      </div>
      <div class="unified-popup-body sv-quick-key-body">
        <p class="sv-quick-key-desc">
          Save secret securely to <code>.env</code>. Keys are never displayed in plain text after saving.
        </p>
        <input
          v-model="quickKeyValue"
          type="password"
          class="sv-input"
          placeholder="Enter API key (e.g. sk-...)"
          @keyup.enter="submitQuickKey"
        />
      </div>
      <div class="unified-popup-foot sv-quick-key-actions">
        <AppButton variant="ghost" @click="closeQuickKeyModal">Cancel</AppButton>
        <AppButton
          variant="primary"
          :disabled="busy || !quickKeyValue.trim()"
          :busy="busy"
          @click="submitQuickKey"
        >
          {{ busy ? "Saving…" : "Save Key" }}
        </AppButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Settings sections (tab): General | Providers. Reuse seg-tabs AETHER. */
.sv-tabs {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.22);
  margin-bottom: 14px;
}
.sv-tab {
  display: inline-flex;
  align-items: center;
  padding: 6px 14px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--text-dim);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}
.sv-tab:hover {
  color: var(--text);
  background: rgba(255, 255, 255, 0.045);
}
.sv-tab.active {
  color: var(--text);
  background: rgba(45, 125, 78, 0.20);
  box-shadow: inset 0 0 0 1px rgba(45, 125, 78, 0.35);
}

.sv-alert {
  padding: 10px 12px;
  border-radius: 9px;
  font-size: 12.5px;
  border: 1px solid var(--border-soft);
}
.sv-alert.err {
  color: var(--alert-err-text);
  background: var(--alert-err-bg);
  border-color: var(--alert-err-border);
}
.sv-alert.ok {
  color: var(--alert-ok-text);
  background: var(--alert-ok-bg);
  border-color: var(--alert-ok-border);
}

.sv-prov {
  border: 1px solid var(--line, var(--border-soft));
  border-radius: 6px;
  background: var(--inset, rgba(0, 0, 0, 0.25));
  padding: 14px;
  display: grid;
  gap: 12px;
}
.sv-prov-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}
.sv-prov-id {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.sv-prov-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 650;
}
.sv-prov-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 3px;
  font-size: 11.5px;
  color: var(--text-faint);
}
.sv-prov-meta .mono.ok {
  color: var(--ok);
}
.sv-prov-meta .mono.warn {
  color: var(--warn);
}
.sv-actions {
  display: flex;
  gap: 8px;
}

.avatar {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: rgba(45, 125, 78, 0.18);
  color: var(--accent-muted);
  font-weight: 700;
  flex: 0 0 auto;
}

.sv-models {
  display: grid;
  gap: 8px;
  border-top: 1px solid var(--border-soft);
  padding-top: 12px;
}
.sv-models-empty {
  color: var(--text-faint);
  font-style: italic;
  font-size: 12.5px;
}
.sv-model-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.015);
}
.sv-model-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sv-mini {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 7px;
  padding: 4px 9px;
  font-size: 11.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.14s ease;
}
.sv-mini:hover {
  color: var(--text);
  border-color: var(--accent);
  background: var(--bg-hover);
}
.sv-mini.danger {
  border-color: var(--err);
  color: var(--err);
}
.sv-mini.danger:hover {
  background: var(--err);
  color: var(--text);
  border-color: var(--err);
}

.sv-add-row {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
.sv-add-row .sv-input {
  flex: 1 1 auto;
}

.sv-form {
  border: 1px dashed var(--line, var(--border-soft));
  border-radius: 6px;
  background: var(--inset, rgba(0, 0, 0, 0.25));
  padding: 14px;
  display: grid;
  gap: 10px;
}
.sv-form-editing {
  border-style: solid;
  border-color: var(--accent);
}
.sv-form-title {
  font-size: 12.5px;
  font-weight: 650;
  color: var(--text-dim);
}
.sv-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}
.sv-form-actions {
  display: flex;
  justify-content: flex-end;
}

.sv-input {
  width: 100%;
  padding: 9px 12px;
  border-radius: 9px;
  border: 1px solid var(--border);
  background: var(--bg-elev);
  color: var(--text);
  font-size: 12.5px;
  font-family: var(--mono);
}
.sv-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(45, 125, 78, 0.20);
}

.sv-cred {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 14px;
  border: 1px solid var(--line, var(--border-soft));
  border-radius: 6px;
  background: var(--inset, rgba(0, 0, 0, 0.25));
}
.sv-cred-name {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sv-cred-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
  font-size: 11.5px;
  color: var(--text-faint);
}

.sv-test-result {
  padding: 6px 12px;
  font-size: 12px;
  border-radius: 8px;
  background: rgba(45, 125, 78, 0.08);
  color: var(--text-dim);
}

.status-tag.ok {
  color: var(--ok);
}
.status-tag.idle {
  opacity: 0.7;
}

/* Configuration Card & Interactive Selectors */
.sv-config-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sv-config-grid {
  display: flex;
  flex-direction: column;
  gap: 0;
  border-radius: 8px;
  border: 1px solid var(--line);
  overflow: hidden;
  background: var(--inset, rgba(0, 0, 0, 0.25));
}

[data-theme="light"] .sv-config-grid {
  background: rgba(0, 0, 0, 0.02);
  border-color: var(--line, rgba(73, 64, 97, 0.1));
}

.sv-config-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  border-radius: 0;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--line);
}

[data-theme="light"] .sv-config-row {
  border-bottom-color: var(--line, rgba(73, 64, 97, 0.1));
}

.sv-config-row:last-child {
  border-bottom: none;
}

.sv-config-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 140px;
  flex: 0 0 170px;
}

.sv-config-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text);
}

.sv-config-subtitle {
  font-size: 10.5px;
  color: var(--text-faint);
  line-height: 1.3;
}

.sv-config-control {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  min-width: 0;
}

.sv-select {
  width: 100%;
  max-width: 320px;
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg-elev);
  color: var(--text);
  font-size: 12px;
  font-family: inherit;
  outline: none;
  cursor: pointer;
  transition: border-color 0.15s ease;
}

.sv-select:focus {
  border-color: var(--accent);
}

.sv-cred-status-wrap {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.sv-cred-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.sv-cred-env {
  font-size: 11.5px;
  color: var(--text);
  font-weight: 600;
}

.sv-cred-val {
  font-size: 11px;
  color: var(--text-dim);
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 6px;
  border-radius: 4px;
}

.sv-url-val {
  font-size: 11.5px;
  color: var(--text-dim);
  text-align: right;
  word-break: break-all;
}

/* Quick Key Modal */
.sv-quick-key-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 16px;
}

.sv-quick-key-dialog {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
  width: 100%;
  max-width: 440px;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.45);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sv-quick-key-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sv-quick-key-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text);
}

.sv-quick-key-desc {
  font-size: 11.5px;
  color: var(--text-dim);
  margin: 0 0 10px;
  line-height: 1.4;
}

.sv-quick-key-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.sv-tip-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--accent-soft);
  border: 1px solid var(--accent-dim);
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 11.5px;
  color: var(--text-dim);
  line-height: 1.4;
  margin-top: 8px;
}

.sv-tip-box code {
  color: var(--accent);
  background: var(--accent-soft);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 11px;
}
</style>
