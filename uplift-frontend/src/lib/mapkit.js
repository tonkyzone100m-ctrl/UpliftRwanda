import { useEffect, useRef, useState } from "react";

export const RW_CENTER = [-1.9441, 29.8739];
export const RW_ZOOM = 9;
export const RW_BOUNDS = [[-2.85, 28.85], [-1.02, 30.95]];
export const RW_PAN_BOUNDS = [[-3.1, 28.6], [-0.8, 31.2]];
export const FOCUS_MAX_ZOOM = 11;

const GEO_URL = "/geo/rw-districts.geojson";

// 5-step ramp, worst-first: band 0 paints the darkest red, so callers holding
// "higher is better" metrics flip the index instead of reversing the array.
const RAMP = ["#b91c1c", "#f87171", "#fbbf24", "#93c5fd", "#22c55e"];

export function quintileBuckets(values) {
  const clean = values.filter((v) => v != null && !Number.isNaN(v)).sort((a, b) => a - b);
  if (clean.length < 5) return null;
  const edges = [0, 0.2, 0.4, 0.6, 0.8, 1].map(
    (q) => clean[Math.min(clean.length - 1, Math.floor(q * clean.length))],
  );
  return (v) => {
    if (v == null || Number.isNaN(v)) return null;
    for (let i = 1; i < edges.length; i += 1) {
      if (v <= edges[i] + 1e-9) return i - 1;
    }
    return edges.length - 2;
  };
}

export function bandColor(band, direction) {
  if (band == null) return "#e5e7eb";
  return RAMP[direction === "higher" ? 4 - band : band];
}

export function useDistrictGeo() {
  const [geo, setGeo] = useState(null);
  useEffect(() => {
    let live = true;
    fetch(GEO_URL)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`geo ${res.status}`))))
      .then((data) => live && setGeo(data))
      .catch(() => live && setGeo(null));
    return () => {
      live = false;
    };
  }, []);
  return geo;
}

// Leaflet inside hidden SPA tabs still believes its size is 0, so re-measure
// whenever the map shell mounts, resizes or re-shows.
export function useLeafletResizer() {
  const shellRef = useRef(null);
  const mapRef = useRef(null);
  useEffect(() => {
    const el = shellRef.current;
    if (!el) return undefined;
    const observer = new ResizeObserver(() => mapRef.current?.invalidateSize());
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return { shellRef, mapRef };
}

// Bounds of a mounted district layer, matched case-insensitively.
export function getLayerBounds(layerRef, name) {
  const target = String(name).toLowerCase();
  const match = (layerRef.current?.getLayers() ?? []).find(
    (layer) => String(layer.feature?.properties?.district ?? "").toLowerCase() === target,
  );
  if (typeof match?.getBounds !== "function") return null;
  try {
    const bounds = match.getBounds();
    if (typeof bounds?.isValid === "function" && !bounds.isValid()) return null;
    return bounds;
  } catch {
    return null; // degenerate / NaN geometry
  }
}
