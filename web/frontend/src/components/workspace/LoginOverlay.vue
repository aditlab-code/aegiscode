<script setup>
/**
 * LoginOverlay.vue - Sovereign Local Password Authentication Gatekeeper.
 *
 * Menampilkan antarmuka otentikasi kata sandi operator lokal (minimal 6 karakter)
 * untuk mengamankan gateway studio tanpa dependensi pihak ketiga eksternal.
 */
import { ref, computed, watch, nextTick, onMounted } from "vue";
import AppButton from "../ui/AppButton.vue";

const props = defineProps({
  hasPassword: {
    type: Boolean,
    default: true,
  },
  hasPin: {
    type: Boolean,
    default: undefined,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  loadingMessage: {
    type: String,
    default: "Memeriksa kata sandi...",
  },
  error: {
    type: String,
    default: "",
  },
});

const emit = defineEmits([
  "submit-password",
  "setup-password",
  "submit-pin",
  "setup-pin",
  "clear-error",
]);

const isConfigured = computed(() => {
  if (props.hasPin !== undefined) return props.hasPin;
  return props.hasPassword;
});

const mode = ref(isConfigured.value ? "entry" : "setup");
const passwordInput = ref("");
const newPassword = ref("");
const confirmPassword = ref("");
const localError = ref("");
const showPassword = ref(false);
const showNewPassword = ref(false);

const passwordInputRef = ref(null);
const newPasswordInputRef = ref(null);

watch(isConfigured, (val) => {
  mode.value = val ? "entry" : "setup";
  localError.value = "";
  passwordInput.value = "";
  focusInput();
});

const displayError = computed(() => props.error || localError.value);

function focusInput() {
  nextTick(() => {
    if (mode.value === "entry" && passwordInputRef.value) {
      passwordInputRef.value.focus();
    } else if (mode.value === "setup" && newPasswordInputRef.value) {
      newPasswordInputRef.value.focus();
    }
  });
}

function clearErrors() {
  localError.value = "";
  emit("clear-error");
}

function submitLogin() {
  if (passwordInput.value.length < 6) {
    localError.value = "Kata sandi minimal 6 karakter.";
    return;
  }
  clearErrors();
  emit("submit-password", passwordInput.value);
  emit("submit-pin", passwordInput.value);
}

function submitSetup() {
  clearErrors();
  if (!newPassword.value || !confirmPassword.value) {
    localError.value = "Kata sandi dan konfirmasi harus diisi.";
    return;
  }
  if (newPassword.value.length < 6) {
    localError.value = "Kata sandi minimal 6 karakter.";
    return;
  }
  if (newPassword.value.length > 128) {
    localError.value = "Kata sandi maksimal 128 karakter.";
    return;
  }
  if (newPassword.value !== confirmPassword.value) {
    localError.value = "Konfirmasi kata sandi tidak cocok.";
    return;
  }
  emit("setup-password", {
    password: newPassword.value,
    confirmPassword: confirmPassword.value,
  });
  emit("setup-pin", {
    pin: newPassword.value,
    confirmPin: confirmPassword.value,
  });
}

onMounted(() => {
  focusInput();
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
            ? "Tentukan kata sandi operator lokal (minimal 6 karakter) untuk mengamankan gateway studio dan runtime tools Antigravity."
            : "Masukkan kata sandi operator lokal untuk membuka sesi studio dan workspace."
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

      <!-- MODE 1: SETUP KATA SANDI BARU -->
      <form v-if="mode === 'setup'" class="auth-form" @submit.prevent="submitSetup">
        <div class="form-group">
          <label class="form-label" for="setup-password-input">Kata Sandi Baru (minimal 6 karakter)</label>
          <div class="password-field-wrapper">
            <input
              id="setup-password-input"
              ref="newPasswordInputRef"
              v-model="newPassword"
              :type="showNewPassword ? 'text' : 'password'"
              class="auth-text-input"
              maxlength="128"
              autocomplete="new-password"
              placeholder="Masukkan kata sandi baru"
              autofocus
              @input="clearErrors"
            />
            <button
              type="button"
              class="eye-toggle-btn"
              tabindex="-1"
              :title="showNewPassword ? 'Sembunyikan' : 'Perlihatkan'"
              @click="showNewPassword = !showNewPassword"
            >
              <svg v-if="!showNewPassword" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                <line x1="1" y1="1" x2="23" y2="23" />
              </svg>
            </button>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label" for="setup-confirm-input">Ulangi Kata Sandi</label>
          <div class="password-field-wrapper">
            <input
              id="setup-confirm-input"
              v-model="confirmPassword"
              :type="showNewPassword ? 'text' : 'password'"
              class="auth-text-input"
              maxlength="128"
              autocomplete="new-password"
              placeholder="Konfirmasi kata sandi baru"
              @input="clearErrors"
            />
          </div>
        </div>

        <AppButton
          variant="primary"
          size="md"
          class="action-btn-full"
          :disabled="loading || newPassword.length < 6 || confirmPassword.length < 6"
          :busy="loading"
          type="submit"
        >
          Simpan Sandi & Buka Studio
        </AppButton>
      </form>

      <!-- MODE 2: ENTRY KATA SANDI -->
      <form v-else class="auth-form" @submit.prevent="submitLogin">
        <div class="form-group">
          <label class="form-label" for="entry-password-input">Kata Sandi Operator</label>
          <div class="password-field-wrapper">
            <input
              id="entry-password-input"
              ref="passwordInputRef"
              v-model="passwordInput"
              :type="showPassword ? 'text' : 'password'"
              class="auth-text-input"
              maxlength="128"
              autocomplete="current-password"
              placeholder="Masukkan kata sandi..."
              autofocus
              @input="clearErrors"
            />
            <button
              type="button"
              class="eye-toggle-btn"
              tabindex="-1"
              :title="showPassword ? 'Sembunyikan' : 'Perlihatkan'"
              @click="showPassword = !showPassword"
            >
              <svg v-if="!showPassword" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                <line x1="1" y1="1" x2="23" y2="23" />
              </svg>
            </button>
          </div>
        </div>

        <AppButton
          variant="primary"
          size="md"
          class="action-btn-full"
          :disabled="loading || passwordInput.length < 6"
          :busy="loading"
          type="submit"
        >
          Masuk ke Studio
        </AppButton>

        <!-- Petunjuk Reset Sandi -->
        <div class="reset-hint-box">
          <span class="hint-text">
            Lupa kata sandi? Hapus berkas <code>.aegis/auth.json</code> atau set <code>AEGIS_PASSWORD=sandiAnda</code> di berkas <code>.env</code>.
          </span>
        </div>
      </form>

      <!-- Footer Info -->
      <div class="login-footer">
        <span class="footer-badge">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          Sovereign Local Authentication (.aegis/auth.json / PBKDF2)
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

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: 100%;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.form-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--secondary);
}

.password-field-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
}

.auth-text-input {
  width: 100%;
  padding: 11px 38px 11px 14px;
  background: var(--input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s ease;
  box-sizing: border-box;
}

.auth-text-input:focus {
  border-color: var(--border-hover);
}

.eye-toggle-btn {
  position: absolute;
  right: 10px;
  background: transparent;
  border: none;
  color: var(--muted);
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: color 0.12s ease;
}

.eye-toggle-btn:hover {
  color: var(--text);
}

.action-btn-full {
  width: 100%;
  margin-top: 4px;
  height: 42px;
}

.reset-hint-box {
  width: 100%;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  border: 1px solid var(--border);
  font-size: 11px;
  line-height: 1.4;
  color: var(--muted);
  text-align: center;
  box-sizing: border-box;
}

.reset-hint-box code {
  color: var(--accent);
  font-family: var(--mono);
  font-size: 10.5px;
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
