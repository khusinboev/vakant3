import type { ElementType, ReactNode } from "react";
import { Inbox } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";

export type EmptyStateProps = {
  /** A lucide icon component. Defaults to `Inbox`. */
  icon?: ElementType;
  labelKey?: TranslationKey;
  descriptionKey?: TranslationKey;
  /** Optional call-to-action rendered under the text. */
  action?: ReactNode;
  className?: string;
};

/** "Nothing here" — the third state every list needs next to loading and error. */
export default function EmptyState({
  icon: Icon = Inbox,
  labelKey = "admin.empty.default",
  descriptionKey,
  action,
  className = "",
}: EmptyStateProps) {
  const t = useT();
  return (
    <div className={`flex flex-col items-center justify-center px-4 py-10 text-center ${className}`}>
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-surfaceAlt text-muted">
        <Icon size={20} aria-hidden="true" />
      </span>
      <p className="mt-3 text-sm font-medium text-text">{t(labelKey)}</p>
      {descriptionKey && <p className="mt-1 max-w-xs text-xs text-muted">{t(descriptionKey)}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
