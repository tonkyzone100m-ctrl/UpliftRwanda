export const BASE_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, { status, cause, extra } = {}) {
    super(message, cause ? { cause } : undefined);
    this.name = "ApiError";
    this.status = status;
    this.extra = extra ?? null;
  }
}

export async function fetchMetrics({ signal } = {}) {
  return fetchRows(`${BASE_URL}/api/metrics`, { signal });
}

/** CFSVA 2024 rows from their own table; returns null on any failure (graceful). */
export async function fetchCfsvaMetrics({ signal } = {}) {
  try {
    return await fetchRows(`${BASE_URL}/api/cfsva/metrics`, { signal });
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    return null;
  }
}

/** Internal: standard row-feed contract { status, count, data[] }. */
async function fetchRows(path, { signal } = {}) {
  let res;
  try {
    res = await fetch(path, { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the analytics API at ${BASE_URL}.`, { cause: err });
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(`API responded with ${res.status}: ${detail}`, { status: res.status });
  }
  const payload = await res.json();
  if (payload.status !== "success" || !Array.isArray(payload.data)) {
    throw new ApiError("The API returned an unexpected response shape.");
  }
  return payload.data;
}

/**
 * Public snapshot of the national policy baseline (defaults + overrides +
 * per-key audit entries). Console tooling uses this to render the editor.
 */
export async function fetchTargets({ signal } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}/api/targets`, { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the analytics API at ${BASE_URL}.`, { cause: err });
  }
  if (!res.ok) throw new ApiError(`API responded with ${res.status}`, { status: res.status });
  const payload = await res.json();
  if (payload.status !== "success" || typeof payload.targets !== "object") {
    throw new ApiError("The API returned an unexpected response shape.");
  }
  return payload;
}

/**
 * Automated policy-engine verdict from the backend for one district
 * (name or id). Responds with { insights, thresholds, benchmarks, ... }.
 */
export async function fetchDistrictInsights(district, { signal } = {}) {
  if (!district) return null;
  return fetchInsights(`/api/districts/${encodeURIComponent(district)}/insights`, { signal });
}

/**
 * Population-weighted national policy view (same shape, no district block).
 */
export async function fetchNationalInsights({ signal } = {}) {
  return fetchInsights("/api/insights/national", { signal });
}

async function fetchInsights(path, { signal } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the policy engine at ${BASE_URL}.`, { cause: err });
  }
  if (!res.ok) {
    let detail = res.statusText;
    let code = null;
    let hint = null;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
      code = body.code ?? null;
      hint = body.hint ?? null;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(detail || `API responded with ${res.status}`, {
      status: res.status,
      cause: code || hint ? { detail, code, hint } : undefined,
    });
  }
  const payload = await res.json();
  if (payload.status !== "success" || !Array.isArray(payload.insights)) {
    throw new ApiError("The policy engine returned an unexpected response shape.");
  }
  return payload;
}

/** District index (ids + province + weights) for lab selectors. */
export async function fetchDistrictList({ signal } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}/api/districts`, { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the analytics API at ${BASE_URL}.`, { cause: err });
  }
  if (!res.ok) throw new ApiError(`API responded with ${res.status}`, { status: res.status });
  const payload = await res.json();
  if (payload.status !== "success" || !Array.isArray(payload.data)) {
    throw new ApiError("The API returned an unexpected response shape.");
  }
  return payload.data;
}

/**
 * Predictive what-if: POST /api/v1/simulate. Returns model card + trajectories.
 */
export async function runSimulation(payload = {}, { signal } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}/api/v1/simulate`, {
      method: "POST",
      signal,
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the simulation engine at ${BASE_URL}.`, { cause: err });
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(detail || `API responded with ${res.status}`, { status: res.status });
  }
  const data = await res.json();
  if (data.status !== "success" || !data.national) {
    throw new ApiError("The simulation engine returned an unexpected response shape.");
  }
  return data;
}
