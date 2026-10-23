import { ApiError, BASE_URL } from "./api";

const TOKEN_KEY = "uplift_admin_token";
const EXPIRY_KEY = "uplift_admin_expires_at";

export function getToken() {
  try {
    const token = sessionStorage.getItem(TOKEN_KEY);
    if (!token) return null;
    const expiresAt = Number(sessionStorage.getItem(EXPIRY_KEY)) || Infinity;
    if (Date.now() / 1000 >= expiresAt) {
      clearSession();
      return null;
    }
    return token;
  } catch {
    return null;
  }
}

export function getSession() {
  try {
    const expiresAt = Number(sessionStorage.getItem(EXPIRY_KEY));
    const username = sessionStorage.getItem("uplift_admin_username");
    if (!expiresAt || Date.now() / 1000 >= expiresAt) {
      clearSession();
      return null;
    }
    return { username, expiresAt };
  } catch {
    return null;
  }
}

export function storeSession({ username, access_token, expires_at }) {
  try {
    sessionStorage.setItem(TOKEN_KEY, access_token);
    sessionStorage.setItem(EXPIRY_KEY, String(expires_at));
    sessionStorage.setItem("uplift_admin_username", username);
  } catch {
    /* storage unavailable (private mode) - session simply won't persist */
  }
}

export function clearSession() {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(EXPIRY_KEY);
    sessionStorage.removeItem("uplift_admin_username");
  } catch {
    /* noop */
  }
}

function redactedHeaders(headers = {}) {
  const safe = Object.fromEntries(
    Object.entries(headers).filter(([name]) => name.toLowerCase() !== "authorization")
  );
  const hasAuth = Object.keys(headers).some((name) => name.toLowerCase() === "authorization");
  return { ...safe, Authorization: hasAuth ? "Bearer <redacted>" : "absent" };
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers: { Accept: "application/json", ...options.headers },
    });
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the analytics API at ${BASE_URL}.`, { cause: err });
  }
  let body;
  let text = "";
  try {
    text = await res.text();
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text ? { raw: text } : null;
  }
  if (!res.ok) {
    console.error(
      `[uplift-api] ${options.method ?? "GET"} ${path} -> ${res.status}`,
      {
        requestHeaders: redactedHeaders(options.headers),
        responseText: text.slice(0, 480),
      },
    );
    const detail = body?.detail;
    const code = typeof detail === "object" ? detail?.code : null;
    const message =
      (typeof detail === "object" ? detail?.detail : detail) ?? `API responded with ${res.status}`;
    throw new ApiError(message, { status: res.status, cause: code, extra: typeof detail === "object" ? detail : null });
  }
  return body;
}

export function loginAdmin(username, password) {
  return request("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}

export function fetchAdminSession(token) {
  return request("/api/auth/me", {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
}

/** POST a ministerial action; body is raw JSON (undefined keeps the legacy plain POST). */
export function postAdminAction(path, body) {
  const token = getToken();
  if (!token) {
    throw new ApiError("Your ministerial session is not active. Sign in again before this action.", {
      status: 401,
      cause: "not_authenticated",
    });
  }
  return request(path, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body !== undefined ? { "Content-Type": "application/json" } : undefined),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : undefined),
  });
}
