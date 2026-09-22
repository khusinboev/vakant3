import type { ElementType, ReactNode } from "react";

import type { TranslationKey } from "../../../i18n";
import Button from "./Button";

export type ActionSpec = {
  labelKey?: TranslationKey;
  label?: string;
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  icon?: ElementType;
  danger?: boolean;
};

export type ActionBarProps = {
  /** The screen's one primary action (40px, full width). */
  primary?: ActionSpec;
  /** At most one secondary action next to it. */
  secondary?: ActionSpec;
  children?: ReactNode;
  className?: string;
};

/**
 * The in-page fallback for Telegram's MainButton: sticky just above the
 * `AdminBar`, never a floating button. `AdminShell` renders it automatically
 * for `useAdminHeader({ primary })` when no native MainButton exists.
 */
export default function ActionBar({ primary, secondary, children, className = "" }: ActionBarProps) {
  if (!primary && !secondary && !children) return null;

  return (
    <div
      className={`sticky z-20 -mx-3 mt-2 flex items-center gap-2 border-t border-border bg-surface/95 px-3 py-2 backdrop-blur ${className}`}
      style={{ bottom: "calc(var(--admin-bar-h, 0px) + var(--bottom-safe, 0px))" }}
    >
      {children}
      {secondary && (
        <Button
          size="md"
          variant={secondary.danger ? "danger" : "secondary"}
          labelKey={secondary.labelKey}
          icon={secondary.icon}
          disabled={secondary.disabled}
          loading={secondary.loading}
          onClick={secondary.onClick}
        >
          {secondary.label}
        </Button>
      )}
      {primary && (
        <Button
          size="md"
          full
          variant={primary.danger ? "danger" : "primary"}
          labelKey={primary.labelKey}
          icon={primary.icon}
          disabled={primary.disabled}
          loading={primary.loading}
          onClick={primary.onClick}
        >
          {primary.label}
        </Button>
      )}
    </div>
  );
}
