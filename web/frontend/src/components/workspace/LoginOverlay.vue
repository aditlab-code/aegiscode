<script setup>
/**
 * LoginOverlay.vue - Mandatory Antigravity Google OAuth Gatekeeper.
 *
 * Displays a modal gateway overlay when no valid session token exists,
 * handles user redirect to Google OAuth, and displays authentication errors.
 */
import { ref } from "vue";
import { fetchGoogleLoginUrl, devLogin } from "../services/authService.js";

const props = defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
  loadingMessage: {
    type: String,
    default: "Authenticating with Antigravity...",
  },
  error: {
    type: String,
    default: "",
  },
});

const emit = defineEmits(["retry", "clear-error"]);

const redirecting = ref(false);
const localError = ref("");

async function handleGoogleLogin() {
  localError.value = "";
  emit("clear-error");
  redirecting.value = true;
  try {
    const data = await fetchGoogleLoginUrl();
    if (data?.auth_url) {
      window.location.href = data.auth_url;
    } else {
      throw new Error("No authorization URL returned by backend gateway.");
    }
  } catch (err) {
    redirecting.value = false;
    localError.value = err.message || "Failed to initialize Google login.";
  }
}

async function handleDevClick() {
  localError.value = "";
  emit("clear-error");
  redirecting.value = true;
  try {
    await devLogin("aditwicaksono34@gmail.com", "Adit Wicaksono");
  } catch (err) {
    localError.value = err.message || "Failed to sign in via Dev Login.";
  } finally {
    redirecting.value = false;
  }
}
</script>

<template>
  <div class="login-overlay-backdrop" role="dialog" aria-modal="true" aria-labelledby="login-title">
    <div class="login-card">
      <!-- Header Badge -->
      <div class="brand-header">
        <div class="brand-badge-large">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="m4.5 8.5-3 3.5 3 3.5" />
            <path d="m19.5 8.5 3 3.5-3 3.5" />
            <path d="M12 3c.4 3.8 2.2 5.6 6 6-3.8.4-5.6 2.2-6 6-.4-3.8-2.2-5.6-6-6 3.8-.4 5.6-2.2 6-6Z" />
            <circle cx="12" cy="12" r="1.5" fill="currentColor" />
          </svg>
        </div>
        <div class="brand-titles">
          <span class="platform-tag">ANTIGRAVITY AI PLATFORM</span>
          <h2 id="login-title" class="product-title">AegisCode Studio</h2>
        </div>
      </div>

      <!-- Description -->
      <p class="login-desc">
        Sign in with your Google account to authorize AI agent runtime tools, access local workspaces, and establish a verified operator session.
      </p>

      <!-- Active Loading State -->
      <div v-if="loading || redirecting" class="login-state-box loading-box">
        <div class="spinner-border text-primary spinner-border-sm" role="status">
          <span class="visually-hidden">Loading...</span>
        </div>
        <span class="loading-label">{{ redirecting ? "Opening Google sign-in..." : loadingMessage }}</span>
      </div>

      <!-- Error State -->
      <div v-if="error || localError" class="login-state-box error-box">
        <svg class="error-ico" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <span class="error-label">{{ error || localError }}</span>
      </div>

      <!-- Action Button -->
      <div class="login-actions">
        <button
          type="button"
          class="btn-google-login"
          :disabled="loading || redirecting"
          @click="handleGoogleLogin"
        >
          <!-- Google 'G' Logo SVG -->
          <svg class="google-logo" width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
            <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"/>
            <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.33 24 12 24z"/>
            <path fill="#FBBC05" d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 10.04 0 12s.45 3.82 1.25 5.42l4.03-3.15z"/>
            <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z"/>
          </svg>
          <span class="btn-text">Continue with Google</span>
        </button>

        <button
          type="button"
          class="btn-dev-login"
          :disabled="loading || redirecting"
          title="Sign in with aditwicaksono34@gmail.com without Google Cloud Console credentials"
          @click="handleDevClick"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
          </svg>
          <span>Dev Quick Sign-In (aditwicaksono34@gmail.com)</span>
        </button>
      </div>

      <!-- Footer Info -->
      <div class="login-footer">
        <span class="footer-badge">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
          </svg>
          Desktop Loopback Stateless Auth (Port 8478)
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
  max-width: 440px;
  background: var(--bg-surface, #1e2430);
  border: 1px solid var(--border-color, #2d3648);
  border-radius: 12px;
  padding: 32px 28px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.45);
  display: flex;
  flex-direction: column;
  gap: 20px;
  color: var(--text-primary, #f0f4f8);
}

.brand-header {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-badge-large {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: linear-gradient(135deg, #3b82f6, #6366f1);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35);
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
  color: #60a5fa;
  text-transform: uppercase;
}

.product-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary, #f8fafc);
}

.login-desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary, #94a3b8);
}

.login-state-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 12.5px;
}

.loading-box {
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.25);
  color: #93c5fd;
}

.error-box {
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.25);
  color: #fca5a5;
}

.btn-google-login {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: #ffffff;
  color: #1f2937;
  font-size: 14px;
  font-weight: 600;
  padding: 12px 18px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  cursor: pointer;
  transition: all 0.15s ease-in-out;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}

.btn-google-login:hover:not(:disabled) {
  background: #f9fafb;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-1px);
}

.btn-google-login:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.login-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.btn-dev-login {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: rgba(59, 130, 246, 0.12);
  border: 1px dashed rgba(59, 130, 246, 0.4);
  color: #60a5fa;
  font-size: 13px;
  font-weight: 600;
  padding: 10px 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease-in-out;
}

.btn-dev-login:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.22);
  border-color: #60a5fa;
  transform: translateY(-1px);
}

.btn-dev-login:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.login-footer {
  display: flex;
  justify-content: center;
  padding-top: 4px;
  border-top: 1px solid var(--border-color, #2d3648);
}

.footer-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-muted, #64748b);
}

@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.98); }
  to { opacity: 1; transform: scale(1); }
}
</style>
