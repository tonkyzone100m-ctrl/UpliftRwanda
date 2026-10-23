/**
 * Client-side parsing for ministerial microdata uploads.
 *
 * The API is JSON-only by contract; it takes structured JSON rows:
 *   POST /api/admin/microdata  { rows: [{ district, indicator_code, survey_year, value }] }
 * so the browser does the CSV parsing and cheap pre-validation, keeping the
 * server contract small and the per-row error report consistent.
 */

export const UPLOAD_ROW_LIMIT = 5000;

const REQUIRED_COLUMNS = ["district", "indicator_code", "survey_year", "value"];

/** RFC-4180-ish single-line splitter (handles quoted commas + "" escapes). */
export function splitCsvLine(line) {
  const fields = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      fields.push(field);
      field = "";
    } else {
      field += ch;
    }
  }
  fields.push(field);
  return fields.map((f) => f.trim());
}

/**
 * Parse pasted or uploaded CSV text into server-ready rows.
 * Returns { rows, errors, skipped } where errors mirror the API shape:
 *   [{ row, error }]  (row is 1-based, counts the data rows)
 */
export function parseMicrodataCsv(text) {
  const lines = String(text ?? "")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  if (lines.length === 0) {
    throw new Error("The file is empty — expected district, indicator_code, survey_year, value columns.");
  }

  const header = splitCsvLine(lines[0]).map((h) => h.toLowerCase().replace(/\s+/g, "_"));
  const colIndex = Object.fromEntries(header.map((name, i) => [name, i]));
  const missing = REQUIRED_COLUMNS.filter((c) => colIndex[c] === undefined);
  if (missing.length > 0) {
    throw new Error(
      `Missing column(s): ${missing.join(", ")} — the file must start with district, indicator_code, survey_year, value.`,
    );
  }

  const rows = [];
  const errors = [];

  lines.slice(1).forEach((line, i) => {
    const rowNumber = i + 1;
    const cell = (col) => splitCsvLine(line)[colIndex[col]];
    const district = cell("district");
    const indicator_code = cell("indicator_code");
    const yearRaw = cell("survey_year");
    const valueRaw = cell("value");

    if (!district || !indicator_code) {
      errors.push({ row: rowNumber, error: "Missing district or indicator_code." });
      return;
    }
    if (district.length > 64 || indicator_code.length > 64) {
      errors.push({ row: rowNumber, district, indicator_code, error: "district / indicator_code must be at most 64 characters." });
      return;
    }
    const survey_year = Number.parseInt(yearRaw, 10);
    if (!/^\d{4}$/.test(yearRaw) || !Number.isInteger(survey_year) || survey_year < 1990 || survey_year > 2100) {
      errors.push({ row: rowNumber, district, indicator_code, error: `survey_year must be an integer in 1990-2100 (got "${yearRaw}").` });
      return;
    }
    const value = Number.parseFloat(valueRaw);
    if (!Number.isFinite(value)) {
      errors.push({ row: rowNumber, district, indicator_code, error: `value must be a number (got "${valueRaw}").` });
      return;
    }
    rows.push({ district, indicator_code, survey_year, value });
  });

  if (rows.length > UPLOAD_ROW_LIMIT) {
    throw new Error(`Please upload at most ${UPLOAD_ROW_LIMIT.toLocaleString("en-US")} rows (this file parses to ${rows.length.toLocaleString("en-US")}).`);
  }
  return { rows, errors, skipped: errors.length };
}
