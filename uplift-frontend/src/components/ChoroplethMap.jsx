import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, GeoJSON } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { Map as MapIcon, Satellite } from "lucide-react";
import {
  FOCUS_MAX_ZOOM,
  RW_BOUNDS,
  RW_CENTER,
  RW_PAN_BOUNDS,
  RW_ZOOM,
  bandColor,
  getLayerBounds,
  quintileBuckets,
  useDistrictGeo,
  useLeafletResizer,
} from "../lib/mapkit";
import SectionCard from "./Card";
import MapFocus from "./MapFocus";

// District choropleth reused by the LFS / VUP / inclusion panels.
// rows: [{ district, ...metricKey: number }] · metricDefs: [{ key, label, direction, format }]
export default function ChoroplethMap({
  rows = [],
  metricDefs = [],
  selectedDistrict = "",
  onSelectDistrict = () => {},
  title = "District Choropleth",
  subtitle,
  tone = "sky",
}) {
  const geo = useDistrictGeo();
  const { shellRef, mapRef } = useLeafletResizer();
  const [metricKey, setMetricKey] = useState(metricDefs[0]?.key ?? "");
  const layerRef = useRef(null);
  const [hovered, setHovered] = useState(null);

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

  const getDistrictBounds = useCallback(
    (name) => getLayerBounds(layerRef, name),
    [],
  );

  const styleFeature = (feature) => {
    const name = String(feature.properties.district ?? "").toLowerCase();
    const band = bucketFor?.(regional.get(name)) ?? null;
    const active = !!selectedDistrict && name === selectedDistrict.toLowerCase();
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
          aria-label="Indicator selector"
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
                className={`rounded-full border px-2.5 py-1.5 text-[10px] font-semibold transition sm:text-[11px] ${
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
        </footer>
      }
    >
      <div ref={shellRef} className="h-[320px] overflow-hidden rounded-xl border border-slate-200 sm:h-[460px]">
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
