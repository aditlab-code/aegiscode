<script setup>
/**
 * LoginOverlay.vue - Sovereign Local PIN Authentication Gatekeeper.
 *
 * Menampilkan numpad lokal minimalis atau antarmuka setup PIN pertama kali
 * untuk mengamankan sesi operator studio tanpa koneksi ke domain eksternal.
 */
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import AppButton from "../ui/AppButton.vue";

const props = defineProps({
  hasPin: {
    type: Boolean,
    default: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  loadingMessage: {
    type: String,
    default: "Memeriksa PIN...",
  },
  error: {
    type: String,
    default: "",
  },
});

const emit = defineEmits(["submit-pin", "setup-pin", "clear-error"]);

const mode = ref(props.hasPin ? "entry" : "setup");
const pinInput = ref("");
const newPin = ref("");
const confirmPin = ref("");
const localError = ref("");

watch(
  () => props.hasPin,
  (val) => {
    mode.value = val ? "entry" : "setup";
    localError.value = "";
    pinInput.value = "";
  }
);

const displayError = computed(() => props.error || localError.value);

function handleDigit(d) {
  if (pinInput.value.length < 12) {
    pinInput.value += String(d);
    clearErrors();
  }
}

function handleBackspace() {
  if (pinInput.value.length > 0) {
    pinInput.value = pinInput.value.slice(0, -1);
    clearErrors();
  }
}

function handleClear() {
  pinInput.value = "";
  clearErrors();
}

function clearErrors() {
  localError.value = "";
  emit("clear-error");
}

function submitPin() {
  if (pinInput.value.length < 4) {
    localError.value = "PIN minimal 4 digit.";
    return;
  }
  clearErrors();
  emit("submit-pin", pinInput.value);
}

function submitSetup() {
  clearErrors();
  if (!newPin.value || !confirmPin.value) {
    localError.value = "PIN dan konfirmasi PIN harus diisi.";
    return;
  }
  if (newPin.value.length < 4 || newPin.value.length > 12) {
    localError.value = "Panjang PIN harus antara 4 hingga 12 karakter.";
    return;
  }
  if (newPin.value !== confirmPin.value) {
    localError.value = "Konfirmasi PIN tidak cocok.";
    return;
  }
  emit("setup-pin", { pin: newPin.value, confirmPin: confirmPin.value });
}

function onKeyDown(e) {
  if (mode.value !== "entry") return;
  if (props.loading) return;

  if (e.key >= "0" && e.key <= "9") {
    handleDigit(e.key);
  } else if (e.key === "Backspace") {
    handleBackspace();
  } else if (e.key === "Enter") {
    if (pinInput.value.length >= 4) {
      submitPin();
    }
  } else if (e.key === "Escape") {
    handleClear();
  }
}

onMounted(() => {
  if (typeof window !== "undefined") {
    window.addEventListener("keydown", onKeyDown);
  }
});

onUnmounted(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("keydown", onKeyDown);
  }
});
</script>

<template>
  <div class="login-overlay-backdrop" role="dialog" aria-modal="true" aria-labelledby="login-title">
    <div class="login-card">
      <!-- Header Badge -->
      <div class="brand-header">
        <div class="brand-badge-large">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
        </div>
        <div class="brand-titles">
          <span class="platform-tag">SOVEREIGN RUNTIME GATEWAY</span>
          <h2 id="login-title" class="product-title">AegisCode Studio</h2>
        </div>
      </div>

      <!-- Description -->
      <p class="login-desc">
        {{
          mode === "setup"
            ? "Tentukan PIN operator lokal untuk mengamankan gateway studio dan runtime tools Antigravity."
            : "Masukkan PIN keamanan untuk membuka akses gateway dan workspace lokal."
        }}
      </p>

      <!-- Active Loading State -->
      <div v-if="loading" class="login-state-box loading-box">
        <svg class="spinner-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="2" stroke-dasharray="28" stroke-dashoffset="10" />
        </svg>
        <span class="loading-label">{{ loadingMessage }}</span>
      </div>

      <!-- Error State -->
      <div v-if="displayError" class="login-state-box error-box">
        <svg class="error-ico" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <span class="error-label">{{ displayError }}</span>
      </div>

      <!-- MODE 1: SETUP PIN -->
      <div v-if="mode === 'setup'" class="setup-form">
        <div class="form-group">
          <label class="form-label" for="setup-pin-input">PIN Baru (4–12 digit/karakter)</label>
          <input
            id="setup-pin-input"
            v-model="newPin"
            type="password"
            class="pin-text-input"
            maxlength="12"
            autocomplete="new-password"
            placeholder="Ketik PIN baru"
            @input="clearErrors"
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="setup-confirm-input">Konfirmasi PIN</label>
          <input
            id="setup-confirm-input"
            v-model="confirmPin"
            type="password"
            class="pin-text-input"
            maxlength="12"
            autocomplete="new-password"
            placeholder="Ulangi PIN baru"
            @input="clearErrors"
            @keydown.enter="submitSetup"
          />
        </div>

        <AppButton
          variant="primary"
          size="md"
          class="action-btn-full"
          :disabled="loading || newPin.length < 4 || confirmPin.length < 4"
          :busy="loading"
          @click="submitSetup"
        >
          Buat PIN & Buka Studio
        </AppButton>
      </div>

      <!-- MODE 2: ENTRY PIN (NUMPAD) -->
      <div v-else class="entry-pad">
        <!-- Dot Indicators -->
        <div class="pin-indicator-container">
          <div class="pin-dots">
            <span
              v-for="idx in 6"
              :key="idx"
              class="pin-dot"
              :class="{ filled: idx <= pinInput.length }"
            />
          </div>
          <span v-if="pinInput.length > 6" class="pin-overflow-counter">
            {{ pinInput.length }} digit
          </span>
        </div>

        <!-- 3x4 Numpad -->
        <div class="numpad-grid">
          <AppButton
            v-for="digit in [1, 2, 3, 4, 5, 6, 7, 8, 9]"
            :key="digit"
            variant="ghost"
            size="md"
            class="numpad-btn"
            :disabled="loading"
            @click="handleDigit(digit)"
          >
            {{ digit }}
          </AppButton>

          <AppButton
            variant="ghost"
            size="md"
            class="numpad-btn numpad-action-btn"
            :disabled="loading || pinInput.length === 0"
            title="Hapus Semua"
            @click="handleClear"
          >
            C
          </AppButton>

          <AppButton
            variant="ghost"
            size="md"
            class="numpad-btn"
            :disabled="loading"
            @click="handleDigit(0)"
          >
            0
          </AppButton>

          <AppButton
            variant="ghost"
            size="md"
            class="numpad-btn numpad-action-btn"
            :disabled="loading || pinInput.length === 0"
            title="Hapus Terakhir"
            @click="handleBackspace"
          >
            <template #icon>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 4H8l-7 8 7 8h13a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z" />
                <line x1="18" y1="9" x2="12" y2="15" />
                <line x1="12" y1="9" x2="18" y2="15" />
              </svg>
            </template>
          </AppButton>
        </div>

        <AppButton
          variant="primary"
          size="md"
          class="action-btn-full"
          :disabled="loading || pinInput.length < 4"
          :busy="loading"
          @click="submitPin"
        >
          Buka Studio
        </AppButton>
      </div>

      <!-- Footer Info -->
      <div class="login-footer">
        <span class="footer-badge">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          Sovereign Local PIN Authentication (.aegis/auth.json)
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-overlay-backdrop {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(10, 14, 20, 0.88);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  animation: fadeIn 0.2s ease-out;
}

.login-card {
  width: 100%;
  max-width: 420px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 28px 24px;
  box-shadow: var(--shadow-pop);
  display: flex;
  flex-direction: column;
  gap: 18px;
  color: var(--text);
}

.brand-header {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-badge-large {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: var(--accent);
  border: 1px solid var(--border-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.brand-titles {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.platform-tag {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--accent-dim);
  text-transform: uppercase;
}

.product-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}

.login-desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--secondary);
}

.login-state-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 12.5px;
}

.loading-box {
  background: var(--accent-soft);
  border: 1px solid var(--border-hover);
  color: var(--accent);
}

.spinner-icon {
  width: 16px;
  height: 16px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.error-box {
  background: var(--alert-err-bg);
  border: 1px solid var(--alert-err-border);
  color: var(--alert-err-text);
}

.setup-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--secondary);
}

.pin-text-input {
  width: 100%;
  padding: 10px 14px;
  background: var(--input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-size: 14px;
  font-family: var(--mono);
  outline: none;
  transition: border-color 0.15s ease;
  box-sizing: border-box;
}

.pin-text-input:focus {
  border-color: var(--border-hover);
}

.entry-pad {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
}

.pin-indicator-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}

.pin-dots {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pin-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1.5px solid var(--border);
  background: transparent;
  transition: all 0.15s ease-in-out;
}

.pin-dot.filled {
  background: var(--accent);
  border-color: var(--accent);
  transform: scale(1.15);
}

.pin-overflow-counter {
  font-size: 11px;
  color: var(--muted);
  font-family: var(--mono);
}

.numpad-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  width: 100%;
  max-width: 280px;
}

.numpad-btn {
  height: 52px;
  font-size: 18px;
  font-weight: 600;
  font-family: var(--mono);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text);
  cursor: pointer;
  transition: all 0.12s ease;
}

.numpad-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  background: var(--bg-hover);
  color: var(--accent);
}

.numpad-action-btn {
  font-size: 14px;
  color: var(--secondary);
}

.action-btn-full {
  width: 100%;
  margin-top: 4px;
  height: 42px;
}

.login-footer {
  display: flex;
  justify-content: center;
  padding-top: 6px;
  border-top: 1px solid var(--border);
}

.footer-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--muted);
}

@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.98); }
  to { opacity: 1; transform: scale(1); }
}
</style>
