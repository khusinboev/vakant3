/** Client-side CSV export of already-loaded rows — no server round trip. */

/** A text cell starting with one of these is evaluated as a formula by Excel/Sheets. */
const FORMULA_START = /^[=+\-@\t\r]/;

function escapeCell(value: string | number): string {
  let s = String(value);
  // Neutralize formula injection (a username like `=HYPERLINK(...)`): a
  // leading apostrophe makes spreadsheets show the text as-is. Real numbers
  // stay numeric, so a negative amount is not touched.
  if (typeof value === "string" && FORMULA_START.test(s)) s = `'${s}`;
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function downloadCsv(filename: string, headers: string[], rows: (string | number)[][]): void {
  const lines = [headers, ...rows].map((row) => row.map(escapeCell).join(","));
  // BOM so Excel opens UTF-8 (Cyrillic/Uzbek) correctly.
  const blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
