import { categoryStyle } from "../lib/categories";

const BADGE_BASE =
  "inline-flex max-w-full items-center gap-1.5 truncate rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset";

export function CategoryBadge({ categoryId, category, className = "" }) {
  const style = categoryStyle(categoryId);
  return (
    <span className={`${BADGE_BASE} ${style.badge} ${className}`}>
      {category ?? "Uncategorized"}
    </span>
  );
}

export function CategoryDot({ categoryId, className = "" }) {
  return (
    <span
      aria-hidden="true"
      className={`h-1.5 w-1.5 shrink-0 rounded-full ${categoryStyle(categoryId).dot} ${className}`}
    />
  );
}

export function DistrictBadge({ district }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1.5 truncate rounded-md bg-slate-50 px-2 py-0.5 text-[11px] font-bold text-slate-700 ring-1 ring-inset ring-slate-200">
      <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-sky-500" />
      {district}
    </span>
  );
}
