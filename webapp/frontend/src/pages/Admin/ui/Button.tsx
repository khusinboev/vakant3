import type { ElementType, MouseEventHandler, ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { Link } from "react-router-dom";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";

export type ButtonSize = "sm" | "md";
export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export type ButtonProps = {
  /** Preferred over `children` — keeps pages translation-typed. */
  labelKey?: TranslationKey;
  children?: ReactNode;
  size?: ButtonSize;
  variant?: ButtonVariant;
  icon?: ElementType;
  /** 32×32 (sm) / 40×40 (md) square. Requires `ariaLabel`. */
  iconOnly?: boolean;
  loading?: boolean;
  disabled?: boolean;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  type?: "button" | "submit" | "reset";
  /** Renders a react-router `<Link>` instead of a `<button>`. */
  to?: string;
  /** Renders an `<a>` (external links). */
  href?: string;
  full?: boolean;
  ariaLabel?: string;
  /** Desktop tooltip; defaults to `ariaLabel` for icon-only buttons. */
  title?: string;
  className?: string;
};

const VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primaryFg hover:bg-primary/90",
  secondary: "border border-border bg-surface text-text hover:bg-surfaceAlt",
  ghost: "text-muted hover:bg-surfaceAlt hover:text-text",
  danger: "bg-danger text-white hover:bg-danger/90",
};

const SIZE: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-[12px]",
  md: "h-10 px-4 text-[13px]",
};

const ICON_SIZE: Record<ButtonSize, string> = {
  sm: "h-8 w-8",
  md: "h-10 w-10",
};

const BASE =
  "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-xl font-semibold leading-none transition-colors disabled:cursor-not-allowed disabled:opacity-60";

/**
 * The only button style inside the admin panel (spec §3).
 *
 *   <Button labelKey="adminUsers.save" onClick={save} loading={pending} />
 *   <Button variant="danger" size="sm" icon={Trash2} iconOnly ariaLabel={t("…")} />
 */
export default function Button({
  labelKey,
  children,
  size = "sm",
  variant = "secondary",
  icon: Icon,
  iconOnly = false,
  loading = false,
  disabled = false,
  onClick,
  type = "button",
  to,
  href,
  full = false,
  ariaLabel,
  title,
  className = "",
}: ButtonProps) {
  const t = useT();
  const label = labelKey ? t(labelKey) : children;
  const glyph = size === "sm" ? 14 : 16;

  const classes = [
    BASE,
    iconOnly ? ICON_SIZE[size] : SIZE[size],
    VARIANT[variant],
    full ? "w-full" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const body = (
    <>
      {loading ? (
        <Loader2 size={glyph} aria-hidden="true" className="animate-spin" />
      ) : (
        Icon && <Icon size={glyph} aria-hidden="true" />
      )}
      {!iconOnly && <span className="min-w-0 truncate">{label}</span>}
    </>
  );

  const shared = {
    className: classes,
    "aria-label": iconOnly ? (ariaLabel ?? (labelKey ? t(labelKey) : undefined)) : ariaLabel,
    title: title ?? (iconOnly ? (ariaLabel ?? (labelKey ? t(labelKey) : undefined)) : undefined),
  };

  if (to && !disabled) {
    return (
      <Link to={to} {...shared}>
        {body}
      </Link>
    );
  }

  if (href && !disabled) {
    return (
      <a href={href} target="_blank" rel="noreferrer" {...shared}>
        {body}
      </a>
    );
  }

  return (
    <button type={type} onClick={onClick} disabled={disabled || loading} {...shared}>
      {body}
    </button>
  );
}

export type IconButtonProps = Omit<ButtonProps, "iconOnly" | "labelKey" | "children"> & {
  icon: ElementType;
  /** Required: an icon-only control needs an accessible name. */
  ariaLabel: string;
};

/** A 32×32 (or 40×40) icon button with the name and tooltip wired up. */
export function IconButton({ icon, ariaLabel, ...rest }: IconButtonProps) {
  return <Button {...rest} icon={icon} iconOnly ariaLabel={ariaLabel} />;
}
