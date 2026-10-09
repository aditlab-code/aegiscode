/**
 * authService.js - Sovereign Local PIN Authentication Service.
 *
 * Manages local PIN authentication, session tokens (localStorage: aegis_auth_token),
 * cached user profile, and reactive auth composables for AegisCode Web UI.
 */

import { ref, computed } from "vue";
import {
  getAuthStatus,
  postLogin,
  postSetup,
  postPinLogin,
  postPinSetup,
  getAuthMe,
  postAuthLogout,
} from "../api.js";

const TOKEN_STORAGE_KEY = "aegis_auth_token";
const USER_STORAGE_KEY = "aegis_auth_user";

export function getAuthToken() {
  if (typeof localStorage === "undefined") return "";
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function setAuthToken(token) {
  if (typeof localStorage === "undefined") return;
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
    dispatchAuthChange();
  } catch (err) {
    console.warn("Gagal menyimpan auth token di localStorage:", err);
  }
}

export function getStoredUser() {
  if (typeof localStorage === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user) {
  if (typeof localStorage === "undefined") return;
  try {
    if (user) {
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(USER_STORAGE_KEY);
    }
    dispatchAuthChange();
  } catch (err) {
    console.warn("Gagal menyimpan user di localStorage:", err);
  }
}

export function clearAuthSession() {
  setAuthToken("");
  setStoredUser(null);
}

export function isAuthenticated() {
  return Boolean(getAuthToken());
}

function dispatchAuthChange() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("aegis:auth-changed", {
        detail: {
          authenticated: isAuthenticated(),
          user: getStoredUser(),
        },
      })
    );
  }
}

/**
 * Resolve bootstrap handshake token from URL query, meta tag, or dev define.
 */
export function resolveBootstrapToken() {
  if (typeof window === "undefined") return "";
  try {
    const urlParams = new URLSearchParams(window.location.search || "");
    const tokenFromUrl = urlParams.get("token");
    if (tokenFromUrl) return tokenFromUrl.trim();
  } catch (_) {}

  if (typeof document !== "undefined") {
    try {
      const meta = document.querySelector('meta[name="aegis-ephemeral-token"]');
      const content = meta?.getAttribute("content");
      if (content) return content.trim();
    } catch (_) {}
  }

  if (typeof __AEGIS_DEV_TOKEN__ !== "undefined" && __AEGIS_DEV_TOKEN__) {
    return String(__AEGIS_DEV_TOKEN__).trim();
  }
  return "";
}

/**
 * Fetch local PIN authentication status from backend.
 */
export async function fetchAuthStatus() {
  return getAuthStatus();
}

/**
 * Submit password to log in and store session JWT.
 */
export async function loginWithPassword(password) {
  const data = await postLogin(password);
  if (data?.token) {
    setAuthToken(data.token);
    if (data.user) {
      setStoredUser(data.user);
    }
  }
  return data;
}

/**
 * Setup initial password and store session JWT.
 */
export async function setupInitialPassword(password, confirmPassword) {
  const data = await postSetup(password, confirmPassword);
  if (data?.token) {
    setAuthToken(data.token);
    if (data.user) {
      setStoredUser(data.user);
    }
  }
  return data;
}

export const loginWithPin = loginWithPassword;
export const setupInitialPin = setupInitialPassword;
/**
 * Verify current session token with the backend.
 */
export async function verifyCurrentSession() {
  const token = getAuthToken();
  if (!token) return null;

  try {
    const data = await getAuthMe();
    if (data?.authenticated && data?.user) {
      setStoredUser(data.user);
      return data.user;
    }
    clearAuthSession();
    return null;
  } catch (err) {
    if (err?.status === 401) {
      clearAuthSession();
      return null;
    }
    console.warn("Session verification network failure:", err);
    return getStoredUser();
  }
}

/**
 * Logout user locally and inform backend.
 */
export async function logoutUser() {
  const token = getAuthToken();
  clearAuthSession();

  try {
    if (token) {
      await postAuthLogout();
    }
  } catch {
    // Ignore network error during logout
  }
}

/**
 * Vue 3 Composable managing reactive auth state for App.vue.
 */
export function useAuth() {
  const currentUser = ref(getStoredUser());
  const authStatus = ref(null);
  const authLoading = ref(false);
  const authLoadingMessage = ref("Memeriksa autentikasi...");
  const authError = ref("");
  const authChecking = ref(true);
  const isAuthenticated = computed(() => Boolean(currentUser.value && getAuthToken()));

  function cleanUrlQuery() {
    if (typeof window !== "undefined" && window.history && window.location) {
      const cleanUrl = window.location.origin + window.location.pathname;
      window.history.replaceState({}, document.title, cleanUrl);
    }
  }

  async function handleLogout() {
    await logoutUser();
    currentUser.value = null;
    await refreshAuthStatus();
  }

  async function refreshAuthStatus() {
    try {
      const status = await fetchAuthStatus();
      authStatus.value = status;
      return status;
    } catch (err) {
      console.warn("Gagal mengambil status autentikasi:", err);
      return null;
    }
  }

  async function handlePasswordLogin(password) {
    authLoading.value = true;
    authLoadingMessage.value = "Memverifikasi kata sandi...";
    authError.value = "";
    try {
      const res = await loginWithPassword(password);
      currentUser.value = res.user;
      await refreshAuthStatus();
      return res;
    } catch (err) {
      authError.value = err.message || "Kata sandi yang dimasukkan salah.";
      throw err;
    } finally {
      authLoading.value = false;
    }
  }

  async function handlePasswordSetup(password, confirmPassword) {
    authLoading.value = true;
    authLoadingMessage.value = "Menyimpan kata sandi baru...";
    authError.value = "";
    try {
      const res = await setupInitialPassword(password, confirmPassword);
      currentUser.value = res.user;
      await refreshAuthStatus();
      return res;
    } catch (err) {
      authError.value = err.message || "Gagal mengatur kata sandi.";
      throw err;
    } finally {
      authLoading.value = false;
    }
  }

  async function initAuth() {
    if (typeof window === "undefined") return;

    window.addEventListener("aegis:auth-unauthorized", () => {
      currentUser.value = null;
      clearAuthSession();
    });
    window.addEventListener("aegis:auth-changed", (e) => {
      currentUser.value = e.detail?.user || null;
    });

    const urlParams = new URLSearchParams(window.location.search);
    const tokenFromUrl = urlParams.get("token");
    if (tokenFromUrl) {
      setAuthToken(tokenFromUrl);
      cleanUrlQuery();
    } else if (!getAuthToken()) {
      const bootstrapToken = resolveBootstrapToken();
      if (bootstrapToken) {
        setAuthToken(bootstrapToken);
      }
    }

    if (getAuthToken()) {
      try {
        const user = await verifyCurrentSession();
        currentUser.value = user;
      } catch {
        currentUser.value = null;
      }
    }

    await refreshAuthStatus();
    authChecking.value = false;
  }

  return {
    currentUser,
    authStatus,
    authLoading,
    authLoadingMessage,
    authError,
    authChecking,
    isAuthenticated,
    cleanUrlQuery,
    handleLogout,
    loginWithPassword: handlePasswordLogin,
    setupInitialPassword: handlePasswordSetup,
    loginWithPin: handlePasswordLogin,
    setupInitialPin: handlePasswordSetup,
    initAuth,
  };
}
