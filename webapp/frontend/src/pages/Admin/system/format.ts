import type { TFunction } from "../../../i18n";

/** 1536 -> "1.5 KB". Binary (1024) units, matches how SQLite reports file sizes. */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  const digits = unitIndex > 0 && value < 10 ? 1 : 0;
  return `${value.toFixed(digits)} ${units[unitIndex]}`;
}

/** 93650 -> "1d 2h 34m" (localized unit suffixes via adminSystem.health.*Short). */
export function formatUptime(seconds: number, t: TFunction): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  const total = Math.floor(seconds);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const day = t("adminSystem.health.dayShort");
  const hour = t("adminSystem.health.hourShort");
  const minute = t("adminSystem.health.minuteShort");
  const parts: string[] = [];
  if (days) parts.push(`${days}${day}`);
  if (days || hours) parts.push(`${hours}${hour}`);
  parts.push(`${minutes}${minute}`);
  return parts.join(" ");
}
