import type { ElementType, ReactNode } from "react";
import { Inbox } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";

export type EmptyStateProps = {
  icon?: ElementType;
  labelKey?: TranslationKey;
  label?: string;
  descriptionKey?: TranslationKey;
  description?: string;
  /** One call to action, usually a `sm` Button. */
  action?: ReactNode;
  className?: string;
};

/** "Nothing here", in 96px (spec §3) — loading and error are the other two. */
export default function EmptyState({
  icon: Icon = Inbox,
  labelKey = "admin.empty.default",
  label,
  descriptionKey,
  description,
  action,
  className = "",
}: EmptyStateProps) {
  const t = useT();
  return (
    <div
      className={`flex min-h-[96px] flex-col items-center justify-center gap-1 px-3 py-3 text-center ${className}`}
    >
      <Icon size={18} aria-hidden="true" className="text-muted" />
      <p className="text-[13px] font-medium text-text">{label ?? t(labelKey)}</p>
      {(descriptionKey || description) && (
        <p className="max-w-xs text-[11px] text-muted">
          {description ?? (descriptionKey ? t(descriptionKey) : "")}
        </p>
      )}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
