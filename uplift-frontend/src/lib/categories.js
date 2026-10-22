export const CATEGORY_STYLES = {
  foodsecurity: { badge: "bg-amber-50 text-amber-700 ring-amber-600/20", dot: "bg-amber-500" },
  financialinclusion: { badge: "bg-sky-50 text-sky-700 ring-sky-600/20", dot: "bg-sky-500" },
  financialhealth: { badge: "bg-emerald-50 text-emerald-700 ring-emerald-600/20", dot: "bg-emerald-500" },
  livingconditions: { badge: "bg-violet-50 text-violet-700 ring-violet-600/20", dot: "bg-violet-500" },
  socialprotection: { badge: "bg-teal-50 text-teal-700 ring-teal-600/20", dot: "bg-teal-500" },
  povertydynamics: { badge: "bg-rose-50 text-rose-700 ring-rose-600/20", dot: "bg-rose-500" },
  climateresilience: { badge: "bg-cyan-50 text-cyan-700 ring-cyan-600/20", dot: "bg-cyan-500" },
  uncategorized: { badge: "bg-slate-100 text-slate-600 ring-slate-500/20", dot: "bg-slate-400" },
};

const FALLBACK_STYLE = CATEGORY_STYLES.uncategorized;

export function categoryStyle(categoryId) {
  return CATEGORY_STYLES[categoryId] ?? FALLBACK_STYLE;
}
