import { lazy, Suspense, useState, type ElementType } from "react";
import { BarChart2, LayoutDashboard, Settings, Users } from "lucide-react";

import type { TranslationKey } from "../../i18n";
import { useT } from "../../i18n/useT";
import ErrorCard from "./components/ErrorCard";
import OverviewTab from "./tabs/OverviewTab";
import SettingsTab from "./tabs/SettingsTab";
import UsersTab from "./tabs/UsersTab";
import { useAdminState } from "./useAdminQueries";

// recharts lives only in the analytics tab — keep it out of this chunk.
const AnalyticsTab = lazy(() => import("./tabs/AnalyticsTab"));

type TabId = "overview" | "settings" | "analytics" | "users";

const TABS: { id: TabId; labelKey: TranslationKey; icon: ElementType }[] = [
  { id: "overview", labelKey: "admin.tab.overview", icon: LayoutDashboard },
  { id: "settings", labelKey: "admin.tab.settings", icon: Settings },
  { id: "analytics", labelKey: "admin.tab.analytics", icon: BarChart2 },
  { id: "users", labelKey: "admin.tab.users", icon: Users },
];

function TabFallback() {
  const t = useT();
  return (
    <div className="flex h-40 items-center justify-center text-sm text-muted">
      {t("common.loading")}
    </div>
  );
}

export default function Admin() {
  const t = useT();
  const [tab, setTab] = useState<TabId>("overview");
  const state = useAdminState();

  return (
    <div className="-mx-4 -mt-4">
      <header className="bg-gradient-to-br from-brand-700 via-brand-600 to-brand-500 px-5 pb-5 pt-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wider text-brand-100">
              {t("admin.brand")}
            </p>
            <h1 className="mt-0.5 font-display text-xl font-extrabold text-white">
              {t("admin.title")}
            </h1>
          </div>
          <div className="flex items-center gap-1.5 rounded-full bg-white/20 px-3 py-1.5">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-emerald-300" />
            <span className="text-xs font-semibold text-white">{t("admin.online")}</span>
          </div>
        </div>
      </header>

      {state.isPending ? (
        <div className="px-4 py-4">
          <div className="h-40 animate-pulse rounded-2xl bg-surfaceAlt" />
        </div>
      ) : state.isError || !state.data ? (
        <div className="px-4 py-4">
          <ErrorCard error={state.error} onRetry={() => void state.refetch()} />
        </div>
      ) : (
        <>
          <nav
            aria-label={t("admin.title")}
            className="sticky top-14 z-10 flex border-b border-border bg-surface shadow-sm"
          >
            {TABS.map(({ id, labelKey, icon: Icon }) => (
              <button
                key={id}
                type="button"
                aria-current={tab === id ? "page" : undefined}
                onClick={() => setTab(id)}
                className={`flex flex-1 flex-col items-center gap-0.5 border-b-2 py-2.5 text-[10px] font-semibold transition-colors ${
                  tab === id ? "border-primary text-primary" : "border-transparent text-muted"
                }`}
              >
                <Icon size={15} aria-hidden="true" />
                {t(labelKey)}
              </button>
            ))}
          </nav>

          <div className="px-4 py-4">
            {tab === "overview" && <OverviewTab state={state.data} />}
            {tab === "settings" && <SettingsTab state={state.data} />}
            {tab === "analytics" && (
              <Suspense fallback={<TabFallback />}>
                <AnalyticsTab />
              </Suspense>
            )}
            {tab === "users" && <UsersTab />}
          </div>
        </>
      )}
    </div>
  );
}
