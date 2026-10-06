import test from "node:test";
import assert from "node:assert/strict";

// Mock global localStorage
const storage = new Map();
globalThis.localStorage = {
  getItem: (k) => (storage.has(k) ? storage.get(k) : null),
  setItem: (k, v) => storage.set(k, String(v)),
  removeItem: (k) => storage.delete(k),
  clear: () => storage.clear(),
};

// Mock global window and CustomEvent
class MockCustomEvent {
  constructor(type, eventInitDict) {
    this.type = type;
    this.detail = eventInitDict?.detail;
  }
}
globalThis.CustomEvent = MockCustomEvent;

const eventListeners = new Map();
globalThis.window = {
  location: {
    origin: "http://localhost:5173",
    pathname: "/workbench",
  },
  addEventListener: (event, handler) => {
    if (!eventListeners.has(event)) eventListeners.set(event, []);
    eventListeners.get(event).push(handler);
  },
  removeEventListener: (event, handler) => {
    if (eventListeners.has(event)) {
      eventListeners.set(
        event,
        eventListeners.get(event).filter((h) => h !== handler)
      );
    }
  },
  dispatchEvent: (evt) => {
    const list = eventListeners.get(evt.type) || [];
    for (const handler of list) handler(evt);
    return true;
  },
};

const {
  getAuthToken,
  setAuthToken,
  getStoredUser,
  setStoredUser,
  clearAuthSession,
  isAuthenticated,
  getRedirectUri,
  fetchGoogleLoginUrl,
  exchangeOAuthCallback,
  verifyCurrentSession,
  logoutUser,
} = await import("./services/authService.js");

test("authService: stores and retrieves token and user profile in storage", () => {
  clearAuthSession();
  assert.equal(getAuthToken(), "");
  assert.equal(isAuthenticated(), false);
  assert.equal(getStoredUser(), null);

  setAuthToken("sample.jwt.token");
  assert.equal(getAuthToken(), "sample.jwt.token");
  assert.equal(isAuthenticated(), true);

  const sampleUser = { sub: "123", email: "adit@example.com", name: "Adit" };
  setStoredUser(sampleUser);
  assert.deepEqual(getStoredUser(), sampleUser);

  clearAuthSession();
  assert.equal(getAuthToken(), "");
  assert.equal(getStoredUser(), null);
  assert.equal(isAuthenticated(), false);
});

test("authService: computes redirect URI based on window.location", () => {
  const uri = getRedirectUri();
  assert.equal(uri, "http://localhost:5173/auth/callback");
});

test("authService: fetchGoogleLoginUrl calls /api/auth/google/url", async () => {
  globalThis.fetch = async (url) => {
    assert.match(url, /\/api\/auth\/google\/url\?redirect_uri=/);
    const payload = {
      auth_url: "https://accounts.google.com/o/oauth2/v2/auth?state=xyz",
      state: "xyz",
    };
    return {
      ok: true,
      text: async () => JSON.stringify(payload),
      json: async () => payload,
    };
  };

  const data = await fetchGoogleLoginUrl();
  assert.equal(data.state, "xyz");
  assert.match(data.auth_url, /accounts\.google\.com/);
});

test("authService: exchangeOAuthCallback saves token and user on success", async () => {
  clearAuthSession();

  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/auth/google/callback");
    assert.equal(options.method, "POST");
    const body = JSON.parse(options.body);
    assert.equal(body.code, "google_auth_code_123");
    assert.equal(body.state, "signed_state_token");

    const payload = {
      token: "minted.aegis.jwt",
      user: { sub: "sub_1", email: "operator@aegis.local", name: "Operator" },
    };
    return {
      ok: true,
      text: async () => JSON.stringify(payload),
      json: async () => payload,
    };
  };

  const result = await exchangeOAuthCallback("google_auth_code_123", "signed_state_token");
  assert.equal(result.token, "minted.aegis.jwt");
  assert.equal(getAuthToken(), "minted.aegis.jwt");
  assert.equal(isAuthenticated(), true);
  assert.equal(getStoredUser().email, "operator@aegis.local");
});

test("authService: verifyCurrentSession validates existing token", async () => {
  setAuthToken("active_token");

  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/auth/me");
    assert.equal(options.headers.Authorization, "Bearer active_token");

    const payload = {
      authenticated: true,
      user: { sub: "sub_1", email: "operator@aegis.local", name: "Operator" },
    };
    return {
      ok: true,
      text: async () => JSON.stringify(payload),
      json: async () => payload,
    };
  };

  const user = await verifyCurrentSession();
  assert.equal(user.email, "operator@aegis.local");
});

test("authService: logoutUser clears local storage and notifies server", async () => {
  setAuthToken("token_to_logout");
  setStoredUser({ email: "test@example.com" });
  assert.equal(isAuthenticated(), true);

  let serverLogoutCalled = false;
  globalThis.fetch = async (url) => {
    if (url === "/api/auth/logout") {
      serverLogoutCalled = true;
      return { ok: true, text: async () => JSON.stringify({ success: true }), json: async () => ({ success: true }) };
    }
    return { ok: false };
  };

  await logoutUser();
  assert.equal(isAuthenticated(), false);
  assert.equal(getAuthToken(), "");
  assert.equal(getStoredUser(), null);
  assert.equal(serverLogoutCalled, true);
});
