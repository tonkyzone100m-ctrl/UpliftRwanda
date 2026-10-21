import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, GeoJSON } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { Map as MapIcon, Satellite } from "lucide-react";
import { METRIC_DEFS, formatMetricValue } from "../lib/metrics";

const RW_CENTER = [-1.96, 29.87];
const RW_BOUNDS = [[-2.85, 28.85], [-1.02, 30.95]];

const GEO_URL = "/geo/rw-districts.geojson";

// Discrete 5-step ramps (light → dark). For "higher is better", the LAST color
// is the worst band; for "lower is better", the FIRST color is the worst band.
const RAMP_WORST_FIRST = ["#b91c1c", "#f87171", "#fbbf24", "#93c5fd", "#22c55e"];

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
      if (v <= qs[i] + 1e-9) return i - 1; // 0 = worst-first index
    }
    return qs.length - 2;
  };
}

function bandColor(bandIndex, direction) {
  if (bandIndex == null) return "#e5e7eb";
  const idx = direction === "higher" ? 4 - bandIndex : bandIndex;
  return RAMP_WORST_FIRST[idx];
}

export default function DistrictMap({ regions = [], selectedDistrict = "", onSelectDistrict }) {
  const [geo, setGeo] = useState(null);
  const [metricKey, setMetricKey] = useState("povertyRate");
  const layerRef = useRef(null);
  const [hovered, setHovered] = useState(null);

  // Heatmap layer toggles. The CFSVA 2024 chips only light up once the
  // food-security rows are in memory (Rule 3: toggle CFSVA layers onto the
  // heatmap without touching the core FinScope layer behaviour).
  const MAP_CHIP_GROUPS = [
    {
      id: "finscope",
      label: "FinScope · EICV7",
      keys: ["povertyRate", "extremePoverty", "vulnerableShare", "climateShock",
        "financialInclusion", "mobileMoney", "formalCredit", "socialProtection"],
      accent: "sky",
    },
    {
      id: "cfsva",
      label: "CFSVA 2024",
      keys: ["fiesModerateSevere", "fiesSevere", "foodConsumptionScore", "hdds", "stunting"],
      accent: "amber",
    },
  ];

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

  const def = useMemo(
    () => METRIC_DEFS.find((d) => d.key === metricKey) ?? METRIC_DEFS[0],
    [metricKey],
  );

  const availableKeys = useMemo(() => {
    const present = new Set();
    for (const region of regions) {
      for (const key of Object.keys(region.metricMap ?? {})) {
        if (region.metricMap?.[key] != null) present.add(key);
      }
    }
    return present;
  }, [regions]);
  const defIsCfsva = MAP_CHIP_GROUPS[1].keys.includes(metricKey);

  // district -> { value, defKey, weight } straight from canonical metricMap
  const regional = useMemo(() => {
    const map = new Map();
    for (const region of regions) {
      const entry = region.metricMap?.[metricKey];
      if (entry) map.set(String(region.district).toLowerCase(), entry.value);
    }
    return map;
  }, [regions, metricKey]);

  const bucketFor = useMemo(
    () => quintileBuckets([...regional.values()]),
    [regional],
  );

  const styleFeature = (feature) => {
    const name = String(feature.properties.district ?? "").toLowerCase();
    const value = regional.get(name);
    const band = bucketFor ? bucketFor(value) : null;
    const active = selectedDistrict && name === selectedDistrict.toLowerCase();
    return {
      fillColor: bandColor(band, def.direction),
      fillOpacity: 0.82,
      color: active ? "#0b2534" : "#475569",
      weight: active ? 3 : 1,
    };
  };

  const legendBands = useMemo(() => {
    if (!bucketFor) return [];
    const values = [...regional.values()].filter((v) => v != null).sort((a, b) =>
      def.direction === "higher" ? b - a : a - b
    );
    return [0].concat(Array.from({ length: 5 }, (_, i) => Math.round(((i + 1) / 5) * (values.length - 1))))
      .slice(0, 5)
      .map((idx, i) => ({ color: bandColor(i, def.direction), label: values[idx] }));
  }, [bucketFor, regional, def.direction]);

  const nationalMean = useMemo(() => {
    const values = [...regional.values()].filter((v) => v != null);
    if (!values.length) return null;
    return values.reduce((acc, v) => acc + v, 0) / values.length;
  }, [regional]);

  // per-feature tooltips bound imperatively (data-driven GeoJSON shares one otherwise)
  useEffect(() => {
    if (!layerRef.current) return;
    for (const layer of layerRef.current.getLayers()) {
      const name = layer.feature?.properties?.district ?? "";
      const value = regional.get(String(name).toLowerCase());
      const valueLine = value == null
        ? "No match in dataset"
        : `${def.label}: <b>${formatMetricValue({ value, unit: "%" }, { compact: true })}</b>`;
      layer.bindTooltip(`<b>${name}</b><br>${valueLine}<br>${def.target}`, { sticky: true, className: "uplift-map-tip" });
    }
  }, [geo, regional, def, hovered, selectedDistrict]);

  return (
    <section
      aria-label="Rwanda district choropleth"
      className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="rounded-lg bg-sky-50 p-2.5 text-sky-600">
            <MapIcon className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h2 className="text-lg font-bold text-gray-900">Rwanda District Heatmap</h2>
            <p className="mt-0.5 text-xs text-gray-500">
              Click a district to sync filters, insights and tables · boundaries: geoboundaries RWA-ADM2 (CC BY 4.0)
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <span
            aria-hidden="true"
            className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
              defIsCfsva ? "bg-amber-100 text-amber-800" : "bg-sky-100 text-sky-700"
            }`}
          >
            {defIsCfsva ? "Source: CFSVA 2024" : "Source: FinScope / EICV7"}
          </span>
          <div className="flex flex-wrap items-center justify-end gap-1.5" role="group" aria-label="Indicator selector for the map">
            {MAP_CHIP_GROUPS.map((group) => (
              <div key={group.id} className="flex flex-wrap items-center gap-1.5">
                <span
                  className={`${group.id === "cfsva" ? "text-amber-700" : "text-sky-700"} select-none text-[9px] font-bold uppercase tracking-wider`}
                >
                  {group.label}
                </span>
                {group.keys.map((key) => {
                  const d = METRIC_DEFS.find((e) => e.key === key);
                  if (!d) return null;
                  const loaded = availableKeys.has(key);
                  const active = metricKey === key;
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => loaded && setMetricKey(key)}
                      disabled={!loaded}
                      title={loaded ? d.label : `${d.label} — CFSVA rows not loaded yet`}
                      aria-pressed={active}
                      className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold transition sm:text-[11px] ${
                        active
                          ? group.id === "cfsva"
                            ? "border-amber-700 bg-amber-700 text-white"
                            : "border-slate-900 bg-slate-900 text-white"
                          : loaded
                            ? "border-slate-300 bg-white text-slate-600 hover:border-slate-500"
                            : "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                      }`}
                    >
                      {loaded ? d.label : `${d.label} ·`}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </header>

      <div className="mt-3 h-[420px] overflow-hidden rounded-xl border border-slate-200 sm:h-[520px]">
        {geo ? (
          <MapContainer
            center={RW_CENTER}
            bounds={RW_BOUNDS}
            zoomControl
            scrollWheelZoom={false}
            style={{ height: "100%", width: "100%" }}
            className="z-0"
          >
            <GeoJSON
              ref={layerRef}
              data={geo}
              key={`rw-map-${metricKey}-v${regions.length}`}
              style={styleFeature}
              eventHandlers={{
                click: (e) => {
                  const name = e?.layer?.feature?.properties?.district;
                  if (name && onSelectDistrict) onSelectDistrict(name);
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
        <p className="sr-only" aria-live="polite">
          {hovered}: {regional.get(hovered.toLowerCase())?.toFixed(1) ?? "no value"} percent, {def.label}
        </p>
      )}

      <footer className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1.5" aria-label="Quantile legend">
          <span className="text-[11px] font-semibold text-slate-500">
            {def.direction === "higher" ? "High ↓" : "Low ↓"} value → color:
          </span>
          {legendBands.map((band, i) => (
            <span
              key={i}
              className="flex items-center gap-1 text-[11px] text-slate-600"
              title={`Band ${i + 1} edge`}
            >
              <span className="h-3 w-5 rounded-sm border border-slate-300" style={{ background: band.color }} />
              {band.label != null ? band.label.toFixed(1) : "—"}
            </span>
          ))}
        </div>
        <p className="text-[11px] text-slate-500">
          Benchmark: <b>{def.label}</b> {def.target} · simple mean n={regional.size}
          {nationalMean != null && <> · mean {nationalMean.toFixed(1)}%</>}
        </p>
      </footer>
    </section>
  );
}
