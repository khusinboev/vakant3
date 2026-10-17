import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";

export type ListProps = {
  children: ReactNode;
  /** Accessible name of the list. */
  ariaLabelKey?: TranslationKey;
  ariaLabel?: string;
  /** Wraps the rows in a card. Default `true`. */
  card?: boolean;
  className?: string;
};

/** The dense list container: one hairline between rows, one border around. */
export function List({ children, ariaLabelKey, ariaLabel, card = true, className = "" }: ListProps) {
  const t = useT();
  return (
    <ul
      aria-label={ariaLabelKey ? t(ariaLabelKey) : ariaLabel}
      className={`divide-y divide-border ${
        card ? "overflow-hidden rounded-xl border border-border bg-surface" : ""
      } ${className}`}
    >
      {children}
    </ul>
  );
}

export type ListRowProps = {
  /** 28px avatar / icon slot. */
  leading?: ReactNode;
  title: ReactNode;
  /** Second line (max 56px row in total). */
  subtitle?: ReactNode;
  /** Right-aligned secondary text under the trailing slot. */
  meta?: ReactNode;
  trailing?: ReactNode;
  onClick?: () => void;
  /** Renders the whole row as a link. */
  to?: string;
  chevron?: boolean;
  /** Accessible name when the row is interactive and the title is not text. */
  ariaLabel?: string;
  className?: string;
};

/**
 * 40px for a single line, 56px with a subtitle — the mobile replacement for a
 * table row (spec §1.4).
 */
export function ListRow({
  leading,
  title,
  subtitle,
  meta,
  trailing,
  onClick,
  to,
  chevron,
  ariaLabel,
  className = "",
}: ListRowProps) {
  const interactive = Boolean(onClick || to);
  const showChevron = chevron ?? interactive;

  const body = (
    <>
      {leading && <span className="flex h-7 w-7 shrink-0 items-center justify-center">{leading}</span>}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-medium text-text">{title}</span>
        {subtitle && <span className="block truncate text-[11px] text-muted">{subtitle}</span>}
      </span>
      {(trailing || meta) && (
        <span className="flex shrink-0 flex-col items-end gap-0.5 text-right">
          {trailing}
          {meta && <span className="text-[11px] tabular-nums text-muted">{meta}</span>}
        </span>
      )}
      {showChevron && (
        <ChevronRight size={14} aria-hidden="true" className="shrink-0 text-muted" />
      )}
    </>
  );

  const inner = `flex w-full items-center gap-2 px-3 text-left ${
    subtitle ? "min-h-[56px] py-1.5" : "min-h-[40px] py-1"
  } ${interactive ? "hover:bg-surfaceAlt" : ""} ${className}`;

  return (
    <li>
      {to ? (
        <Link to={to} aria-label={ariaLabel} className={inner}>
          {body}
        </Link>
      ) : onClick ? (
        <button type="button" onClick={onClick} aria-label={ariaLabel} className={inner}>
          {body}
        </button>
      ) : (
        <div className={inner}>{body}</div>
      )}
    </li>
  );
}

export default List;
