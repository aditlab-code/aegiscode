/**
 * authService.js - Antigravity / Google OAuth Authentication Service.
 *
 * Manages stateless session tokens, user identity retention in localStorage,
 * server-to-server OAuth callback exchange, and authentication state events.
 */

import { ref, computed } from "vue";
import { request } from "../api.js";

const TOKEN_STORAGE_KEY = "aegis_auth_token";
const USER_STORAGE_KEY = "aegis_auth_user";

export function getAuthToken() {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function setAuthToken(token) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch (err) {
    console.warn("Failed to persist auth token:", err);
  }
  dispatchAuthChange();
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user) {
  try {
    if (user) {
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(USER_STORAGE_KEY);
    }
  } catch (err) {
    console.warn("Failed to persist user profile:", err);
  }
  dispatchAuthChange();
}

export function clearAuthSession() {
  try {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(USER_STORAGE_KEY);
  } catch {
    // Ignore storage errors during cleanup
  }
  dispatchAuthChange();
}

export function isAuthenticated() {
  return Boolean(getAuthToken());
}

export function getRedirectUri() {
  if (typeof window !== "undefined" && window.location) {
    return `${window.location.origin}/auth/callback`;
  }
  return "http://localhost:8478/auth/callback";
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
 * Fetch Google OAuth authorization URL from Django backend.
 */
export async function fetchGoogleLoginUrl(redirectUri = null) {
  const uri = encodeURIComponent(redirectUri || getRedirectUri());
  return request(`/auth/google/url?redirect_uri=${uri}`);
}

/**
 * Exchange authorization code and anti-CSRF state token for Aegis session.
 */
export async function exchangeOAuthCallback(code, state, redirectUri = null) {
  const payload = {
    code,
    state,
    redirect_uri: redirectUri || getRedirectUri(),
  };

  const data = await request("/auth/google/callback", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  if (data?.token) {
    setAuthToken(data.token);
    if (data.user) {
      setStoredUser(data.user);
    }
  }

  return data;
}

/**
 * Verify current session token with the backend.
 */
export async function verifyCurrentSession() {
  const token = getAuthToken();
  if (!token) return null;

  try {
    const data = await request("/auth/me");
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
    // If backend is temporarily unreachable, preserve cached user in dev
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
      await request("/auth/logout", {
        method: "POST",
      });
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
  const authLoading = ref(false);
  const authLoadingMessage = ref("Authenticating with Antigravity...");
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
    const code = urlParams.get("code");
    const state = urlParams.get("state");
    const oauthError = urlParams.get("error");

    if (oauthError) {
      authError.value = `Google authorization error: ${oauthError}`;
      cleanUrlQuery();
    } else if (code && state) {
      authLoading.value = true;
      authLoadingMessage.value = "Verifying Google credentials & initializing Antigravity session...";
      try {
        const result = await exchangeOAuthCallback(code, state);
        currentUser.value = result.user;
        cleanUrlQuery();
      } catch (err) {
        authError.value = err.message || "OAuth exchange failed";
        clearAuthSession();
        currentUser.value = null;
        cleanUrlQuery();
      } finally {
        authLoading.value = false;
      }
    } else if (getAuthToken()) {
      try {
        const user = await verifyCurrentSession();
        currentUser.value = user;
      } catch {
        currentUser.value = null;
      }
    }
    authChecking.value = false;
  }

  async function handleDevLogin(email, name) {
    authLoading.value = true;
    authLoadingMessage.value = "Authenticating with local dev credentials...";
    try {
      const res = await devLogin(email, name);
      currentUser.value = res.user;
      authError.value = "";
    } catch (err) {
      authError.value = err.message || "Dev login failed.";
    } finally {
      authLoading.value = false;
    }
  }

  return {
    currentUser,
    authLoading,
    authLoadingMessage,
    authError,
    authChecking,
    isAuthenticated,
    cleanUrlQuery,
    handleLogout,
    handleDevLogin,
    initAuth,
  };
}

/**
 * Dev-only login bypass for local manual testing.
 */
export async function devLogin(email = "aditwicaksono34@gmail.com", name = "Adit Wicaksono") {
  const data = await request("/auth/dev-login", {
    method: "POST",
    body: JSON.stringify({ email, name }),
  });
  if (data?.token) {
    setAuthToken(data.token);
    if (data.user) {
      setStoredUser(data.user);
    }
  }
  return data;
}


