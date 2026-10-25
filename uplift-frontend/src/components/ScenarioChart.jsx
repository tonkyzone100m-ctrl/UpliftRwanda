/**
 * Minimal dependency-free chart renderer used by the Scenario Lab.
 * Renders grouped columns (Baseline + one bar per projection year) for several
 * outcomes on an inline SVG with delta badges — small enough for field tablets.
 */

function niceCeil(v) {
  if (!Number.isFinite(v)) return 10;
  const step = Math.max(0.5, Math.ceil(v / 12));
  return Math.ceil(v / step) * step;
}

export default function ScenarioChart({ outcomes, uncertainty = {}, labelWidth = 132 }) {
  if (!outcomes || Object.keys(outcomes).length === 0) {
    return (
      <p className="py-8 text-center text-xs text-slate-400" role="status">
        Adjust the policy levers — projections appear here after the simulation runs.
      </p>
    );
  }
  const rows = Object.entries(outcomes);
  const maxVal = niceCeil(Math.max(...rows.flatMap(([, spec]) => [spec.baseline, ...spec.path])));
  const chartH = 152;
  const colW = 26;
  const gapW = 7;
  const seriesPerRow = 1 + rows[0][1].path.length;

  return (
    <div className="overflow-x-auto">
      <svg
        className="mx-auto block"
        role="img"
        aria-label="Baseline versus projected policy scenario outcomes"
        viewBox={`0 0 ${rows.length * (labelWidth + 14) + 8} ${chartH + 34}`}
        style={{ maxWidth: 900, minWidth: 560, width: "100%" }}
      >
        {rows.map(([key, spec], rowIndex) => {
          const originX = rowIndex * (labelWidth + 14) + 8;
          const bars = [
            { label: "Baseline", value: spec.baseline, tone: "#0ea5e9", dashed: false },
            ...spec.path.map((v, i) => ({ label: `Yr ${i + 1}`, value: v, tone: "#047857", dashed: i === spec.path.length - 1 })),
          ];
          const groupW = seriesPerRow * (colW + gapW);
          return (
            <g key={key} transform={`translate(${originX},0)`}>
              <title>{key}</title>
              {/* frame */}
              <line x1={0} y1={chartH} x2={groupW} y2={chartH} stroke="#94a3b8" strokeWidth={1} />
              {[0.5, 1].map((f) => (
                <g key={f}>
                  <line x1={0} y1={chartH * (1 - f)} x2={groupW} y2={chartH * (1 - f)} stroke="#e2e8f0" strokeDasharray="3 3" />
                  <text x={0} y={chartH * (1 - f) - 3} fontSize="8" fill="#94a3b8">{Math.round(maxVal * f)}</text>
                </g>
              ))}
              {bars.map((b, i) => {
                const h = (b.value / maxVal) * chartH;
                const x = i * (colW + gapW);
                const band = uncertainty[key] ?? 0;
                return (
                  <g key={b.label}>
                    <rect
                      x={x}
                      y={chartH - h}
                      width={colW}
                      height={h}
                      rx={3}
                      fill={b.tone}
                      fillOpacity={b.dashed ? 0.85 : 1}
                    />
                    {i === 0 ? (
                      <text x={x + colW / 2} y={chartH - h - 4} fontSize="9" textAnchor="middle" fill="#475569">
                        {b.value.toFixed(1)}
                      </text>
                    ) : (
                      <text
                        x={x + colW / 2}
                        y={chartH - h - 4}
                        fontSize="9"
                        textAnchor="middle"
                        fill={b.value < spec.baseline ? "#065f46" : "#047857"}
                        fontWeight="600"
                      >
                        {b.value >= spec.baseline ? "+" : ""}
                        {(b.value - spec.baseline).toFixed(1)}
                      </text>
                    )}
                    {band > 0 && (
                      <line
                        x1={x + colW / 2}
                        y1={chartH - Math.min(chartH, ((b.value + band) / maxVal) * chartH)}
                        x2={x + colW / 2}
                        y2={chartH - Math.max(0, ((b.value - band) / maxVal) * chartH)}
                        stroke="#334155"
                        strokeWidth={1}
                        strokeDasharray="2 2"
                      />
                    )}
                  </g>
                );
              })}
              {/* row caption */}
              <text x={groupW / 2} y={chartH + 16} fontSize="10" textAnchor="middle" fill="#334155" fontWeight="700">
                {cleanLabel(key)}
              </text>
              <text x={groupW / 2} y={chartH + 28} fontSize="8" textAnchor="middle" fill="#64748b">
                {bars.map((b) => b.label).join(" · ")}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function cleanLabel(key) {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace("Poverty Headcount", "Poverty")
    .replace("Extreme Poverty Rate", "Extreme Poverty")
    .replace("Financial Health", "Fin. Health")
    .replace("Financially Vulnerable", "Avg Vulnerability");
}
