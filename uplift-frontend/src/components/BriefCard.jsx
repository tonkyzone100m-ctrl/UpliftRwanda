import { useMemo, useState } from "react";
import { FileDown, FileSpreadsheet, Printer } from "lucide-react";
import SectionCard from "./Card";
import { briefDownloadUrl } from "../lib/api";

/**
 * Executive Policy Brief (Module D) — one-click PDF/CSV downloads straight
 * from the FastAPI brief endpoints for any district or the national view.
 */
export default function BriefCard({ districts = [], selectedDistrict = "" }) {
  const [ref, setRef] = useState(selectedDistrict || "national");
  const effectiveRef = useMemo(
    () => (ref && districts.includes(ref) ? ref : "national"),
    [ref, districts],
  );

  return (
    <SectionCard
      ariaLabel="Executive policy brief generator"
      icon={Printer}
      tone="sky"
      title="Executive Policy Brief — one click, boardroom-ready"
      subtitle="Cabinet-grade PDF with headline economics, five survey layers, verdicts and recommended interventions · CSV for analysts"
      actions={
        <select
          value={effectiveRef}
          onChange={(e) => setRef(e.target.value)}
          aria-label="Choose district for the brief"
          className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 focus:border-sky-500 focus:outline-none"
        >
          <option value="national">National (all 30 districts)</option>
          {districts.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      }
    >
      <div className="flex flex-wrap items-center gap-3">
        <a
          href={briefDownloadUrl(effectiveRef, "pdf")}
          className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
        >
          <FileDown className="h-4 w-4" aria-hidden="true" />
          Download PDF brief
        </a>
        <a
          href={briefDownloadUrl(effectiveRef, "csv")}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-500"
        >
          <FileSpreadsheet className="h-4 w-4" aria-hidden="true" />
          Download CSV dataset
        </a>
        <p className="text-[11px] text-slate-500">
          <code className="rounded bg-slate-100 px-1 py-0.5">GET /api/brief/{effectiveRef === "national" ? "national" : effectiveRef}.pdf</code>
          {" "}· auto-refreshes whenever NISR publishes a new survey layer
        </p>
      </div>
    </SectionCard>
  );
}
