import test from "node:test";
import assert from "node:assert/strict";

// Mock global localStorage
const storage = new Map();
globalThis.localStorage = {
  getItem: (k) => storage.get(k) || null,
  setItem: (k, v) => storage.set(k, String(v)),
  removeItem: (k) => storage.delete(k),
  clear: () => storage.clear(),
};

// Mock global window and CustomEvent
class MockCustomEvent {
  constructor(type, options = {}) {
    this.type = type;
    this.detail = options.detail || null;
  }
}
globalThis.CustomEvent = MockCustomEvent;

const eventListeners = new Map();
globalThis.window = {
  location: {
    origin: "http://localhost:5173",
    pathname: "/",
    search: "",
  },
  history: {
    replaceState: () => {},
  },
  addEventListener: (event, handler) => {
    if (!eventListeners.has(event)) eventListeners.set(event, []);
    eventListeners.get(event).push(handler);
  },
  removeEventListener: (event, handler) => {
    if (eventListeners.has(event)) {
      const arr = eventListeners.get(event).filter((h) => h !== handler);
      eventListeners.set(event, arr);
    }
  },
  dispatchEvent: (event) => {
    const list = eventListeners.get(event.type) || [];
    list.forEach((fn) => fn(event));
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
  fetchAuthStatus,
  loginWithPassword,
  setupInitialPassword,
  loginWithPin,
  setupInitialPin,
  verifyCurrentSession,
  logoutUser,
  resolveBootstrapToken,
} = await import("./services/authService.js");

test("authService: stores and retrieves token and user profile in storage", () => {
  clearAuthSession();
  assert.equal(getAuthToken(), "");
  assert.equal(getStoredUser(), null);
  assert.equal(isAuthenticated(), false);

  setAuthToken("test_token_123");
  assert.equal(getAuthToken(), "test_token_123");
  assert.equal(isAuthenticated(), true);

  const mockUser = { sub: "sub_1", email: "user@example.com", name: "User 1" };
  setStoredUser(mockUser);
  assert.deepEqual(getStoredUser(), mockUser);

  clearAuthSession();
  assert.equal(getAuthToken(), "");
  assert.equal(getStoredUser(), null);
  assert.equal(isAuthenticated(), false);
});

test("authService: fetchAuthStatus calls /api/auth/status", async () => {
  globalThis.fetch = async (url) => {
    assert.equal(url, "/api/auth/status");
    const payload = {
      configured: true,
      has_password: true,
      has_pin: true,
      authenticated: false,
      user: null,
    };
    return {
      ok: true,
      text: async () => JSON.stringify(payload),
      json: async () => payload,
    };
  };

  const status = await fetchAuthStatus();
  assert.equal(status.configured, true);
  assert.equal(status.has_password, true);
  assert.equal(status.authenticated, false);
});

test("authService: loginWithPassword saves token and user on success", async () => {
  clearAuthSession();

  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/auth/login");
    assert.equal(options.method, "POST");
    const body = JSON.parse(options.body);
    assert.equal(body.password, "securepassword123");

    const payload = {
      token: "minted.password.session.jwt",
      user: { sub: "local-operator", email: "operator@aegis.local", name: "Local Operator" },
    };
    return {
      ok: true,
      text: async () => JSON.stringify(payload),
      json: async () => payload,
    };
  };

  const result = await loginWithPassword("securepassword123");
  assert.equal(result.token, "minted.password.session.jwt");
  assert.equal(getAuthToken(), "minted.password.session.jwt");
  assert.equal(isAuthenticated(), true);
  assert.equal(getStoredUser().sub, "local-operator");
  assert.equal(getStoredUser().email, "operator@aegis.local");
});

test("authService: setupInitialPassword saves token and user on success", async () => {
  clearAuthSession();

  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/auth/setup");
    assert.equal(options.method, "POST");
    const body = JSON.parse(options.body);
    assert.equal(body.password, "initialpass123");
    assert.equal(body.confirm_password, "initialpass123");

    const payload = {
      token: "minted.setup.session.jwt",
      user: { sub: "local-operator", email: "operator@aegis.local", name: "Local Operator" },
      success: true,
    };
    return {
      ok: true,
      text: async () => JSON.stringify(payload),
      json: async () => payload,
    };
  };

  const result = await setupInitialPassword("initialpass123", "initialpass123");
  assert.equal(result.token, "minted.setup.session.jwt");
  assert.equal(result.success, true);
  assert.equal(getAuthToken(), "minted.setup.session.jwt");
  assert.equal(isAuthenticated(), true);
  assert.equal(getStoredUser().sub, "local-operator");
});

test("authService: verifyCurrentSession validates existing token", async () => {
  setAuthToken("active_token");

  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/auth/me");
    assert.equal(options.headers.Authorization, "Bearer active_token");

    const payload = {
      authenticated: true,
      user: { sub: "local-operator", email: "operator@aegis.local", name: "Local Operator" },
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
  setStoredUser({ email: "operator@aegis.local" });
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

test("authService: resolveBootstrapToken extracts token from URL, meta tag, or dev define", () => {
  // 1. URL search param
  globalThis.window.location.search = "?token=handshake_from_url_123";
  assert.equal(resolveBootstrapToken(), "handshake_from_url_123");

  // 2. Meta tag
  globalThis.window.location.search = "";
  globalThis.document = {
    querySelector: (selector) => {
      if (selector === 'meta[name="aegis-ephemeral-token"]') {
        return { getAttribute: () => "meta_token_abc" };
      }
      return null;
    },
  };
  assert.equal(resolveBootstrapToken(), "meta_token_abc");

  // 3. Dev define global
  delete globalThis.document;
  globalThis.__AEGIS_DEV_TOKEN__ = "dev_token_xyz";
  assert.equal(resolveBootstrapToken(), "dev_token_xyz");
  delete globalThis.__AEGIS_DEV_TOKEN__;

  // 4. Fallback empty
  assert.equal(resolveBootstrapToken(), "");
});
