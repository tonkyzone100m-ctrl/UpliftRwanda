import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, GeoJSON } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { Satellite, Map as MapIcon } from "lucide-react";
import SectionCard from "./Card";
import MapFocus from "./MapFocus";

const RW_CENTER = [-1.9403, 29.8739];
const RW_ZOOM = 8;
const RW_BOUNDS = [[-2.85, 28.85], [-1.02, 30.95]];
const RW_PAN_BOUNDS = [[-3.1, 28.6], [-0.8, 31.2]];
const FOCUS_MAX_ZOOM = 11;

const GEO_URL = "/geo/rw-districts.geojson";

// Discrete 5-step ramp (light → dark), worst-first semantics: for "lower is
// better" metrics band 0 paints the darkest red; for "higher is better" it flips.
const RAMP = ["#b91c1c", "#f87171", "#fbbf24", "#93c5fd", "#22c55e"];

function quintileBuckets(values) {
  const clean = values.filter((v) => v != null && !Number.isNaN(v)).sort((a, b) => a - b);
  if (clean.length < 5) return null;
  const qs = [0, 0.2, 0.4, 0.6, 0.8, 1].map((q) => {
    const idx = Math.min(clean.length - 1, Math.floor(q * clean.length));
    return clean[idx];
  });
  return (v) => {
    if (v == null || Number.isNaN(v)) return null;
    for (let i = 1; i < qs.length; i += 1) {
      if (v <= qs[i] + 1e-9) return i - 1;
    }
    return qs.length - 2;
  };
}

function bandColor(bandIndex, direction) {
  if (bandIndex == null) return "#e5e7eb";
  const idx = direction === "higher" ? 4 - bandIndex : bandIndex;
  return RAMP[idx];
}

/**
 * Generic district choropleth used by the LFS / VUP / inclusion modules.
 * props:
 *   rows       [{ district, ...metricKey: number }]
 *   metricDefs [{ key, label, direction: "lower"|"higher", format }]
 *   selectedDistrict / onSelectDistrict — synced with the app-wide focus
 * Self-contained geo fetch so it can live inside any panel without props.
 */
export default function ChoroplethMap({
  rows = [],
  metricDefs = [],
  selectedDistrict = "",
  onSelectDistrict = () => {},
  title = "District Choropleth",
  subtitle,
  tone = "sky",
  heightClass = "h-[380px] sm:h-[460px]",
  footerNote,
}) {
  const [geo, setGeo] = useState(null);
  const [metricKey, setMetricKey] = useState(metricDefs[0]?.key ?? "");
  const [hovered, setHovered] = useState(null);
  const layerRef = useRef(null);
  const mapRef = useRef(null);
  const shellRef = useRef(null);

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

  // Leaflet inside a tabbed SPA: re-measure whenever the container resizes.
  useEffect(() => {
    const el = shellRef.current;
    if (!el) return undefined;
    const observer = new ResizeObserver(() => mapRef.current?.invalidateSize());
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const getDistrictBounds = useCallback((name) => {
    const target = String(name).toLowerCase();
    const match = (layerRef.current?.getLayers() ?? []).find(
      (layer) => String(layer.feature?.properties?.district ?? "").toLowerCase() === target,
    );
    if (typeof match?.getBounds !== "function") return null;
    try {
      const bounds = match.getBounds();
      if (typeof bounds?.isValid === "function" && bounds.isValid()) return bounds;
    } catch {
      return null; // layer has degenerate/NaN geometry
    }
    return null;
  }, []);

  const def = useMemo(
    () => metricDefs.find((d) => d.key === metricKey) ?? metricDefs[0] ?? null,
    [metricDefs, metricKey],
  );

  const regional = useMemo(() => {
    const map = new Map();
    for (const row of rows) {
      const v = def ? row[def.key] : null;
      if (v != null) map.set(String(row.district).toLowerCase(), v);
    }
    return map;
  }, [rows, def]);

  const bucketFor = useMemo(() => quintileBuckets([...regional.values()]), [regional]);

  const styleFeature = (feature) => {
    const name = String(feature.properties.district ?? "").toLowerCase();
    const value = regional.get(name);
    const band = bucketFor ? bucketFor(value) : null;
    const active = selectedDistrict && name === selectedDistrict.toLowerCase();
    return {
      fillColor: bandColor(band, def?.direction ?? "lower"),
      fillOpacity: 0.82,
      color: active ? "#0b2534" : "#475569",
      weight: active ? 3 : 1,
    };
  };

  const legendBands = useMemo(() => {
    if (!bucketFor) return [];
    const values = [...regional.values()].filter((v) => v != null).sort((a, b) =>
      def?.direction === "higher" ? b - a : a - b
    );
    return [0]
      .concat(Array.from({ length: 5 }, (_, i) => Math.round(((i + 1) / 5) * (values.length - 1))))
      .slice(0, 5)
      .map((idx, i) => ({ color: bandColor(i, def?.direction ?? "lower"), label: values[idx] }));
  }, [bucketFor, regional, def?.direction]);

  const fmt = (v) => (v == null ? "—" : `${Number(v).toFixed(1)}%`);

  useEffect(() => {
    if (!layerRef.current) return;
    for (const layer of layerRef.current.getLayers()) {
      const name = layer.feature?.properties?.district ?? "";
      const value = regional.get(String(name).toLowerCase());
      const valueLine = value == null
        ? "No match in dataset"
        : `${def?.label ?? "Value"}: <b>${fmt(value)}</b>`;
      layer.bindTooltip(`<b>${name}</b><br>${valueLine}`, { sticky: true, className: "uplift-map-tip" });
    }
  }, [geo, regional, def]);

  return (
    <SectionCard
      ariaLabel={`Map: ${title}`}
      icon={MapIcon}
      tone={tone}
      title={title}
      subtitle={subtitle}
      actions={
        <div
          className="flex flex-wrap items-center justify-end gap-1.5"
          role="group"
          aria-label="Indicator selector for the map"
        >
          {metricDefs.map((d) => {
            const loaded = rows.some((r) => r[d.key] != null);
            const active = def?.key === d.key;
            return (
              <button
                key={d.key}
                type="button"
                onClick={() => loaded && setMetricKey(d.key)}
                disabled={!loaded}
                title={loaded ? d.label : `${d.label} — no rows loaded yet`}
                aria-pressed={active}
                className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold transition sm:text-[11px] ${
                  active
                    ? "border-slate-900 bg-slate-900 text-white"
                    : loaded
                      ? "border-slate-300 bg-white text-slate-600 hover:border-slate-500"
                      : "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                }`}
              >
                {d.label}
              </button>
            );
          })}
        </div>
      }
      bodyClass="p-4 sm:px-5 sm:pb-4 sm:pt-3"
      footer={
        <footer className="flex flex-wrap items-center justify-between gap-3 px-4 pb-4 sm:px-5">
          <div className="flex items-center gap-1.5" aria-label="Quantile legend">
            <span className="text-[11px] font-semibold text-slate-500">
              {def?.direction === "higher" ? "High ↓" : "Low ↓"} value → color:
            </span>
            {legendBands.map((band, i) => (
              <span key={i} className="flex items-center gap-1 text-[11px] text-slate-600">
                <span className="h-3 w-5 rounded-sm border border-slate-300" style={{ background: band.color }} />
                {band.label != null ? Number(band.label).toFixed(1) : "—"}
              </span>
            ))}
          </div>
          {footerNote && <p className="text-[11px] text-slate-500">{footerNote}</p>}
        </footer>
      }
    >
      <div ref={shellRef} className={`overflow-hidden rounded-xl border border-slate-200 ${heightClass}`}>
        {geo ? (
          <MapContainer
            ref={mapRef}
            center={RW_CENTER}
            zoom={RW_ZOOM}
            minZoom={7}
            maxBounds={RW_PAN_BOUNDS}
            maxBoundsViscosity={1.0}
            zoomControl
            scrollWheelZoom={false}
            style={{ height: "100%", width: "100%" }}
            className="z-0"
          >
            <MapFocus
              selectedDistrict={selectedDistrict}
              getDistrictBounds={getDistrictBounds}
              nationalBounds={RW_BOUNDS}
              maxZoom={FOCUS_MAX_ZOOM}
            />
            <GeoJSON
              ref={layerRef}
              data={geo}
              key={`choropleth-${tone}-${metricKey}-v${rows.length}`}
              style={styleFeature}
              eventHandlers={{
                click: (e) => {
                  const name = e?.layer?.feature?.properties?.district;
                  if (name) onSelectDistrict(name);
                },
                mouseover: (e) => setHovered(e?.layer?.feature?.properties?.district ?? null),
              }}
            />
          </MapContainer>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 bg-slate-50">
            <Satellite className="h-6 w-6 text-slate-300" aria-hidden="true" />
            <p className="text-xs font-medium text-slate-400">Loading Rwanda district boundaries…</p>
          </div>
        )}
      </div>

      {hovered && (
        <p className="mt-3 sr-only" aria-live="polite">
          {hovered}: {regional.get(hovered.toLowerCase())?.toFixed(1) ?? "no value"} percent, {def?.label}
        </p>
      )}
    </SectionCard>
  );
}
