import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import { LANG_META } from "../../../store/lang";
import QueryState from "../components/QueryState";
import { StatusDot } from "../ui/Chip";
import KeyValue from "../ui/KeyValue";
import { useAdminState } from "../useAdminQueries";

/**
 * Read-only summary of the `webapp_admin_settings` fields that drive
 * auto-posting. Editing happens on the Settings page — this only links there
 * (via the header `menu`, per UI_SHELL_API.md: "do not duplicate the form").
 */
export default function AutoPostStatus() {
  const t = useT();
  const locale = useLocale();
  const state = useAdminState();

  return (
    <QueryState query={state} skeletonClassName="h-28">
      {(data) => (
        <KeyValue
          rows={[
            {
              labelKey: "adminAutopost.status.enabledLabel",
              value: (
                <StatusDot
                  status={data.auto_post_enabled ? "active" : "disabled"}
                  label={t(
                    data.auto_post_enabled
                      ? "adminAutopost.status.enabled"
                      : "adminAutopost.status.disabled",
                  )}
                />
              ),
            },
            {
              labelKey: "adminAutopost.status.channel",
              value: data.auto_post_channel || t("adminAutopost.status.notSet"),
            },
            {
              labelKey: "adminAutopost.status.channelLang",
              value: LANG_META[data.channel_lang]?.native ?? data.channel_lang,
            },
            {
              labelKey: "adminAutopost.status.minSalary",
              value: locale.formatMoney(data.auto_post_min_salary),
            },
            {
              labelKey: "adminAutopost.status.perDay",
              value: t("adminAutopost.status.perDayRange", {
                min: locale.formatNumber(data.auto_post_per_day_min),
                max: locale.formatNumber(data.auto_post_per_day_max),
              }),
            },
          ]}
        />
      )}
    </QueryState>
  );
}
