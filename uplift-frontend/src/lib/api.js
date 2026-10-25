export const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ??
  import.meta.env.VITE_API_URL ?? // legacy name for existing deploys
  "https://uplift-backend-77a1.onrender.com"
).replace(/\/+$/, "");

if (import.meta.env.PROD && /\/\/(localhost|127\.0\.0\.1)/.test(BASE_URL)) {
  console.warn(
    "[uplift-api] PROD build is pointing at a localhost API — set VITE_API_BASE_URL in your hosting dashboard.",
  );
}

export class ApiError extends Error {
  constructor(message, { status, cause, extra } = {}) {
    super(message, cause ? { cause } : undefined);
    this.name = "ApiError";
    this.status = status;
    this.extra = extra ?? null;
  }
}

async function errorDetail(res) {
  try {
    const body = await res.json();
    return body.detail ?? `API responded with ${res.status}`;
  } catch {
    return `API responded with ${res.status}`;
  }
}

async function request(path, { method = "GET", signal, body, accept = "application/json" } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      signal,
      body,
      headers: { Accept: accept, ...(body != null && { "Content-Type": "application/json" }) },
    });
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the analytics API at ${BASE_URL}.`, { cause: err });
  }
  if (!res.ok) throw new ApiError(await errorDetail(res), { status: res.status });
  return res.json();
}

const rowsOf = (payload) => (payload?.status === "success" && Array.isArray(payload.data) ? payload.data : null);

const isRowFeed = (p) => p?.status === "success" && Array.isArray(p.data);

function expect(payload, check, engine) {
  if (!check(payload)) throw new ApiError(`The ${engine} returned an unexpected response shape.`);
  return payload;
}

/** Optional data layers resolve to null on any failure (except a deliberate abort). */
async function optionalJson(path, { signal } = {}) {
  try {
    return await request(path, { signal });
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    return null;
  }
}

const optionalRows = (path, { signal } = {}) =>
  optionalJson(path, { signal }).then(rowsOf);

function requireRows(path, { signal } = {}) {
  return expect(request(path, { signal }), isRowFeed, "API").then((p) => p.data);
}

export function fetchMetrics({ signal } = {}) {
  return requireRows("/api/metrics", { signal });
}

export const fetchCfsvaMetrics = ({ signal } = {}) => optionalRows("/api/cfsva/metrics", { signal });
export const fetchRdhsDistricts = ({ signal } = {}) => optionalRows("/api/rdhs/districts", { signal });

export function fetchTargets({ signal } = {}) {
  return expect(
    request("/api/targets", { signal }),
    (p) => p?.status === "success" && typeof p.targets === "object",
    "API",
  );
}

export const fetchDistrictInsights = (district, { signal } = {}) => {
  if (!district) return Promise.resolve(null);
  return expect(
    request(`/api/districts/${encodeURIComponent(district)}/insights`, { signal }),
    (p) => p?.status === "success" && Array.isArray(p.insights),
    "policy engine",
  );
};

export function fetchNationalInsights({ signal } = {}) {
  return expect(
    request("/api/insights/national", { signal }),
    (p) => p?.status === "success" && Array.isArray(p.insights),
    "policy engine",
  );
}

export function fetchDistrictList({ signal } = {}) {
  return requireRows("/api/districts", { signal });
}

export function runSimulation(payload = {}, { signal } = {}) {
  return expect(
    request("/api/v1/simulate", { method: "POST", signal, body: JSON.stringify(payload) }),
    (p) => p?.status === "success" && p.national,
    "simulation engine",
  );
}

// LFS 2025 labour-market layer
export const fetchLabourDistricts = ({ signal } = {}) => optionalRows("/api/labour/districts", { signal });

export const fetchLabourDisaggregation = (dimension, { signal } = {}) =>
  optionalJson(`/api/labour/disaggregation?dimension=${encodeURIComponent(dimension)}`, { signal });

// VUP social-protection layer
export const fetchVupDistricts = ({ signal } = {}) => optionalRows("/api/vup/districts", { signal });

export const fetchVupSummary = ({ signal } = {}) => optionalJson("/api/vup/summary", { signal });

// Financial inclusion + opportunity matchmaker
export const fetchInclusionDistricts = ({ signal } = {}) => optionalRows("/api/inclusion/districts", { signal });

export const fetchMatchmakerCatalog = ({ signal } = {}) => optionalJson("/api/matchmaker/catalog", { signal });

export function postMatchmakerRecommendations(profile, { signal } = {}) {
  return expect(
    request("/api/matchmaker/recommendations", { method: "POST", signal, body: JSON.stringify(profile) }),
    (p) => p?.status === "success" && Array.isArray(p.results),
    "matchmaker",
  );
}

// Executive brief — direct downloads
export function briefDownloadUrl(districtRef, format = "pdf") {
  const ref = districtRef ? encodeURIComponent(districtRef) : "national";
  return `${BASE_URL}/api/brief/${ref}.${format}`;
}

// Plain <a href> navigation silently swallows 400/404/503, so fetch the file
// ourselves and surface backend error details through ApiError.
export async function downloadBrief(districtRef, format = "pdf", { signal } = {}) {
  let res;
  try {
    res = await fetch(briefDownloadUrl(districtRef, format), {
      signal,
      headers: { Accept: format === "csv" ? "text/csv" : "application/pdf" },
    });
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    throw new ApiError(`Cannot reach the analytics API at ${BASE_URL}.`, { cause: err });
  }
  if (!res.ok) throw new ApiError(await errorDetail(res), { status: res.status });

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `upliftrwanda-brief-${districtRef || "national"}.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
