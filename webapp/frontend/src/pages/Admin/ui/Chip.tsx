/* eslint-disable react-refresh/only-export-components -- the kit ships helpers next to their component. */
import type { ElementType, ReactNode } from "react";
import { X } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";

export type Tone = "neutral" | "primary" | "success" | "warning" | "danger" | "info";

export const TONE_CLASS: Record<Tone, string> = {
  neutral: "bg-surfaceAlt text-muted border-border",
  primary: "bg-primary/10 text-primary border-primary/30",
  success: "bg-success/10 text-success border-success/30",
  warning: "bg-warning/10 text-warning border-warning/30",
  danger: "bg-danger/10 text-danger border-danger/30",
  info: "bg-primary/10 text-primary border-primary/30",
};

export const TONE_DOT: Record<Tone, string> = {
  neutral: "bg-muted",
  primary: "bg-primary",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-primary",
};

/**
 * The status vocabulary shared by broadcasts, auto-post, users, channels and
 * content — one map instead of the seven copies the audit found.
 */
const STATUS_TONE: Record<string, Tone> = {
  done: "success",
  completed: "success",
  sent: "success",
  ok: "success",
  healthy: "success",
  enabled: "success",
  active: "success",
  published: "success",
  pro: "success",
  running: "info",
  sending: "info",
  processing: "info",
  scheduled: "info",
  queued: "warning",
  pending: "warning",
  degraded: "warning",
  partial: "warning",
  failed: "danger",
  error: "danger",
  banned: "danger",
  blocked: "danger",
  down: "danger",
  cancelled: "neutral",
  canceled: "neutral",
  skipped: "neutral",
  disabled: "neutral",
  draft: "neutral",
  free: "neutral",
  off: "neutral",
  inactive: "neutral",
  unknown: "neutral",
};

/** The tone a status string maps to (`neutral` for anything unknown). */
export function statusTone(status: string): Tone {
  return STATUS_TONE[status.toLowerCase()] ?? "neutral";
}

export type ChipProps = {
  labelKey?: TranslationKey;
  label?: string;
  children?: ReactNode;
  tone?: Tone;
  icon?: ElementType;
  /** Shows a × that calls `onRemove` (active-filter chips). */
  removable?: boolean;
  onRemove?: () => void;
  onClick?: () => void;
  selected?: boolean;
  className?: string;
};

/** 24px pill: a filter value, a tag, a small label. */
export function Chip({
  labelKey,
  label,
  children,
  tone = "neutral",
  icon: Icon,
  removable = false,
  onRemove,
  onClick,
  selected = false,
  className = "",
}: ChipProps) {
  const t = useT();
  const text = labelKey ? t(labelKey) : (label ?? children);
  const base = `inline-flex h-6 max-w-full items-center gap-1 rounded-full border px-2 text-[11px] font-semibold ${
    selected ? TONE_CLASS.primary : TONE_CLASS[tone]
  } ${className}`;

  const content = (
    <>
      {Icon && <Icon size={11} aria-hidden="true" className="shrink-0" />}
      <span className="min-w-0 truncate">{text}</span>
    </>
  );

  if (removable) {
    return (
      <span className={base}>
        {content}
        <button
          type="button"
          onClick={onRemove}
          aria-label={t("admin.filter.removeAria", { label: String(text ?? "") })}
          className="-mr-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full hover:bg-black/10"
        >
          <X size={11} aria-hidden="true" />
        </button>
      </span>
    );
  }

  if (onClick) {
    return (
      <button type="button" onClick={onClick} aria-pressed={selected} className={base}>
        {content}
      </button>
    );
  }

  return <span className={base}>{content}</span>;
}

export type BadgeProps = {
  children?: ReactNode;
  count?: number;
  tone?: Tone;
  className?: string;
};

/** A count or a one-word marker; smaller and flatter than a Chip. */
export function Badge({ children, count, tone = "primary", className = "" }: BadgeProps) {
  const body = count === undefined ? children : count > 99 ? "99+" : count;
  if (body === undefined || body === null || body === "") return null;
  return (
    <span
      className={`inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full border px-1 text-[11px] font-bold tabular-nums ${TONE_CLASS[tone]} ${className}`}
    >
      {body}
    </span>
  );
}

export type StatusChipProps = {
  /** A raw server status (`done`, `queued`, `failed`, `banned`, …). */
  status: string;
  /** Overrides the mapped tone. */
  tone?: Tone;
  /** Overrides the visible text (the status itself is shown otherwise). */
  labelKey?: TranslationKey;
  label?: string;
  className?: string;
};

/** One status pill for the whole panel. */
export function StatusChip({ status, tone, labelKey, label, className = "" }: StatusChipProps) {
  return (
    <Chip
      tone={tone ?? statusTone(status)}
      labelKey={labelKey}
      label={label ?? status}
      className={className}
    />
  );
}

export type StatusDotProps = {
  status?: string;
  tone?: Tone;
  /** Visible text next to the dot. */
  label?: string;
  labelKey?: TranslationKey;
  className?: string;
};

/** An 8px dot — the densest status marker, for list rows. */
export function StatusDot({ status, tone, label, labelKey, className = "" }: StatusDotProps) {
  const t = useT();
  const resolved = tone ?? (status ? statusTone(status) : "neutral");
  const text = labelKey ? t(labelKey) : label;
  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      <span
        aria-hidden="true"
        className={`h-2 w-2 shrink-0 rounded-full ${TONE_DOT[resolved]}`}
      />
      {text !== undefined && (
        <span className="min-w-0 truncate text-[11px] text-muted">{text}</span>
      )}
      {text === undefined && status && <span className="sr-only">{status}</span>}
    </span>
  );
}

export default Chip;
