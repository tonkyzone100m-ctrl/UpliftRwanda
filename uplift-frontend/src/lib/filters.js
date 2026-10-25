import { normKey } from "./metrics";

/** Stable display id for a data category (e.g. "Poverty Dynamics" → "povertydynamics"). */
export function categoryIdOf(category) {
  return normKey(category) || "uncategorized";
}

export function toDisplayRows(rows) {
  return rows.map((row, index) => ({
    ...row,
    rowId: `${row.province}|${row.district}|${row.indicator_code}|${row.survey_year ?? "x"}|${index}`,
    categoryId: categoryIdOf(row.category),
  }));
}

/** Filters indicator rows by free-text query, category id and district. */
export function filterDisplayRows(displayRows, { query, categoryId, district }) {
  const q = normKey(query);
  const filtered = displayRows.filter((row) => {
    if (categoryId !== "all" && row.categoryId !== categoryId) return false;
    if (district && row.district !== district) return false;
    if (!q) return true;
    return (
      normKey(row.indicator_name).includes(q) ||
      normKey(row.indicator_code).includes(q) ||
      normKey(row.district).includes(q) ||
      normKey(row.province).includes(q)
    );
  });
  return filtered.sort(
    (a, b) =>
      a.province.localeCompare(b.province) ||
      a.district.localeCompare(b.district) ||
      (a.category ?? "").localeCompare(b.category ?? "") ||
      (a.indicator_name ?? "").localeCompare(b.indicator_name ?? ""),
  );
}

/** Whether the user has narrowed the table from its default "everything" view. */
export function hasActiveFilters({ query, categoryId, district }) {
  return Boolean(query || categoryId !== "all" || district);
}

export function categoryOptions(displayRows) {
  const counts = new Map();
  for (const row of displayRows) {
    counts.set(row.categoryId, (counts.get(row.categoryId) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

export function categoryLabels(displayRows) {
  return new Map(
    [...new Set(displayRows.filter((r) => r.category).map((r) => r.categoryId))]
      .map((id) => [id, displayRows.find((r) => r.categoryId === id)?.category ?? id]),
  );
}
