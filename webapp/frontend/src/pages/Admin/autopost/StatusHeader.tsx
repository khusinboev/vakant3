import { Link } from "react-router-dom";
import { Pencil, Radio } from "lucide-react";

import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import { LANG_META } from "../../../store/lang";
import GroupCard from "../components/GroupCard";
import QueryState from "../components/QueryState";
import { adminPagePath } from "../routing";
import { useAdminState } from "../useAdminQueries";
import StatusBadge from "./StatusBadge";

/**
 * Read-only summary of the `webapp_admin_settings` fields that drive
 * auto-posting. Editing happens on the Settings page — this only links there
 * (per UI_SHELL_API.md: "do not duplicate the form").
 */
export default function StatusHeader() {
  const t = useT();
  const locale = useLocale();
  const state = useAdminState();

  return (
    <GroupCard icon={Radio} title={t("adminAutopost.status.title")}>
      <QueryState query={state} skeletonClassName="h-28">
        {(data) => (
          <div className="space-y-1">
            <div className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <span className="text-sm text-text">{t("adminAutopost.status.enabledLabel")}</span>
              <StatusBadge
                tone={data.auto_post_enabled ? "success" : "muted"}
                labelKey={
                  data.auto_post_enabled ? "adminAutopost.status.enabled" : "adminAutopost.status.disabled"
                }
              />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <span className="text-sm text-text">{t("adminAutopost.status.channel")}</span>
              <span className="max-w-[60%] truncate text-sm font-medium text-text" title={data.auto_post_channel}>
                {data.auto_post_channel || t("adminAutopost.status.notSet")}
              </span>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <span className="text-sm text-text">{t("adminAutopost.status.channelLang")}</span>
              <span className="text-sm font-medium text-text">{LANG_META[data.channel_lang]?.native ?? data.channel_lang}</span>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <span className="text-sm text-text">{t("adminAutopost.status.minSalary")}</span>
              <span className="text-sm font-medium text-text">{locale.formatMoney(data.auto_post_min_salary)}</span>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <span className="text-sm text-text">{t("adminAutopost.status.perDay")}</span>
              <span className="text-sm font-medium text-text">
                {t("adminAutopost.status.perDayRange", {
                  min: locale.formatNumber(data.auto_post_per_day_min),
                  max: locale.formatNumber(data.auto_post_per_day_max),
                })}
              </span>
            </div>
            <div className="pt-2.5">
              <Link
                to={adminPagePath("settings")}
                className="tap-target inline-flex items-center gap-1.5 rounded-xl border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-primary hover:bg-surfaceAlt"
              >
                <Pencil size={12} aria-hidden="true" />
                {t("adminAutopost.status.editLink")}
              </Link>
            </div>
          </div>
        )}
      </QueryState>
    </GroupCard>
  );
}
