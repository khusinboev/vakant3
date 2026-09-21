import type { ElementType } from "react";
import { Activity, Bug, ScrollText, Users } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import type { SystemTabId } from "./useSystemTab";

const TABS: { id: SystemTabId; labelKey: TranslationKey; icon: ElementType }[] = [
  { id: "health", labelKey: "adminSystem.tab.health", icon: Activity },
  { id: "admins", labelKey: "adminSystem.tab.admins", icon: Users },
  { id: "audit", labelKey: "adminSystem.tab.audit", icon: ScrollText },
  { id: "errors", labelKey: "adminSystem.tab.errors", icon: Bug },
];

export type SystemTabsProps = {
  active: SystemTabId;
  onChange: (id: SystemTabId) => void;
};

/** The System page's own sub-navigation (health / admins / audit / errors). */
export default function SystemTabs({ active, onChange }: SystemTabsProps) {
  const t = useT();
  return (
    <div
      role="tablist"
      aria-label={t("adminSystem.tab.aria")}
      className="flex flex-wrap gap-1.5 border-b border-border pb-2"
    >
      {TABS.map(({ id, labelKey, icon: Icon }) => {
        const isActive = id === active;
        return (
          <button
            key={id}
            type="button"
            role="tab"
            id={`system-tab-${id}`}
            aria-selected={isActive}
            aria-controls={`system-panel-${id}`}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onChange(id)}
            className={`tap-target inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-semibold transition-colors ${
              isActive ? "bg-primary/10 text-primary" : "text-muted hover:text-text"
            }`}
          >
            <Icon size={14} aria-hidden="true" />
            {t(labelKey)}
          </button>
        );
      })}
    </div>
  );
}
