import { useState } from "react";

import useToast from "../../../hooks/useToast";
import { useT } from "../../../i18n/useT";
import parseApiError from "../../../lib/parseApiError";
import { LANGS, type Lang } from "../../../store/lang";
import InlineEditRow from "../components/InlineEditRow";
import ToggleRow from "../components/ToggleRow";
import { Accordion, Button, SegmentedControl, StatusChip } from "../ui";
import { useAdminStatePatch } from "../useAdminQueries";
import type { AdminState, AdminStatePatch } from "../types";

export type SettingsTabProps = {
  state: AdminState;
  /** Optimistic-lock counter from `GET /admin/state` (absent on older caches). */
  version?: number;
  /** Re-fetches `/admin/state` after a 409 SETTINGS_CONFLICT. */
  onReload: () => void;
};

export default function SettingsTab({ state, version, onReload }: SettingsTabProps) {
  const t = useT();
  const toast = useToast();
  const patch = useAdminStatePatch();
  const saving = patch.isPending;
  const [conflict, setConflict] = useState(false);

  const apply = (payload: AdminStatePatch) => {
    setConflict(false);
    // `expected_version` makes the write conditional; a stale one 409s with
    // SETTINGS_CONFLICT instead of silently clobbering a concurrent edit.
    const body: Record<string, unknown> = { ...payload };
    if (version !== undefined) body.expected_version = version;
    patch.mutate(body as unknown as AdminStatePatch, {
      onSuccess: () => toast.success(t("admin.settings.saved")),
      onError: (error) => {
        if (parseApiError(error).code === "SETTINGS_CONFLICT") setConflict(true);
        else toast.apiError(error);
      },
    });
  };

  /** Shared client-side guard: non-empty, numeric, non-negative, then custom. */
  const saveNumber = (
    label: string,
    raw: string,
    build: (value: number) => AdminStatePatch,
    validate?: (value: number) => string | null,
  ) => {
    const trimmed = raw.trim();
    if (!trimmed) {
      toast.error(t("admin.settings.validation.empty", { label }));
      return;
    }
    const value = Number(trimmed);
    if (!Number.isFinite(value)) {
      toast.error(t("admin.settings.validation.number", { label }));
      return;
    }
    if (value < 0) {
      toast.error(t("admin.settings.validation.negative", { label }));
      return;
    }
    const problem = validate?.(value);
    if (problem) {
      toast.error(problem);
      return;
    }
    apply(build(value));
  };

  const saveText = (label: string, raw: string, build: (value: string) => AdminStatePatch) => {
    const trimmed = raw.trim();
    if (!trimmed) {
      toast.error(t("admin.settings.validation.empty", { label }));
      return;
    }
    apply(build(trimmed));
  };

  const perDayLabelMin = t("admin.settings.field.perDayMin");
  const perDayLabelMax = t("admin.settings.field.perDayMax");
  const onOff = (value: boolean) => t(value ? "admin.status.on" : "admin.status.off");

  return (
    <div className="space-y-2">
      {conflict && (
        <div
          role="alert"
          className="flex items-center justify-between gap-2 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2"
        >
          <span className="min-w-0 text-[13px] text-warning">{t("admin.settings.conflict.message")}</span>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              setConflict(false);
              onReload();
            }}
          >
            {t("admin.settings.conflict.reload")}
          </Button>
        </div>
      )}

      {saving && (
        <div role="status" className="px-1">
          <StatusChip status="pending" label={t("admin.settings.saving")} />
        </div>
      )}

      <Accordion
        queryKey="section"
        defaultOpen="autopost"
        items={[
          {
            id: "autopost",
            titleKey: "admin.settings.group.autoPost",
            summary: onOff(state.auto_post_enabled),
            content: (
              <div className="divide-y divide-border">
                <ToggleRow
                  label={t("admin.settings.field.enabled")}
                  checked={state.auto_post_enabled}
                  disabled={saving}
                  onChange={(value) => apply({ auto_post_enabled: value })}
                />
                <InlineEditRow
                  label={t("admin.settings.field.channel")}
                  value={state.auto_post_channel}
                  saving={saving}
                  onSave={(value) =>
                    saveText(t("admin.settings.field.channel"), value, (channel) => ({
                      auto_post_channel: channel,
                    }))
                  }
                />
                <div className="flex min-h-[40px] items-center justify-between gap-2">
                  <span className="min-w-0 truncate text-[13px] text-text">
                    {t("admin.settings.field.channelLang")}
                  </span>
                  <div className={saving ? "pointer-events-none opacity-60" : ""}>
                    <SegmentedControl
                      ariaLabel={t("admin.settings.field.channelLang")}
                      options={LANGS.map((lang) => ({ value: lang, label: lang.toUpperCase() }))}
                      value={state.channel_lang}
                      onChange={(lang) => apply({ channel_lang: lang as Lang })}
                    />
                  </div>
                </div>
                <InlineEditRow
                  label={t("admin.settings.field.autoPostMinSalary")}
                  value={state.auto_post_min_salary}
                  type="number"
                  saving={saving}
                  onSave={(value) =>
                    saveNumber(t("admin.settings.field.autoPostMinSalary"), value, (n) => ({
                      auto_post_min_salary: n,
                    }))
                  }
                />
                <InlineEditRow
                  label={perDayLabelMin}
                  value={state.auto_post_per_day_min}
                  type="number"
                  saving={saving}
                  onSave={(value) =>
                    saveNumber(
                      perDayLabelMin,
                      value,
                      (n) => ({ auto_post_per_day_min: n }),
                      // The bot calls random.randint(min, max) — min > max raises there.
                      (n) =>
                        n > state.auto_post_per_day_max
                          ? t("admin.settings.validation.perDayRange", {
                              min: n,
                              max: state.auto_post_per_day_max,
                            })
                          : null,
                    )
                  }
                />
                <InlineEditRow
                  label={perDayLabelMax}
                  value={state.auto_post_per_day_max}
                  type="number"
                  saving={saving}
                  onSave={(value) =>
                    saveNumber(
                      perDayLabelMax,
                      value,
                      (n) => ({ auto_post_per_day_max: n }),
                      (n) =>
                        n < state.auto_post_per_day_min
                          ? t("admin.settings.validation.perDayRange", {
                              min: state.auto_post_per_day_min,
                              max: n,
                            })
                          : null,
                    )
                  }
                />
              </div>
            ),
          },
          {
            id: "referral",
            titleKey: "admin.settings.group.referralGate",
            summary: onOff(state.referral_enabled),
            content: (
              <div className="divide-y divide-border">
                <ToggleRow
                  label={t("admin.settings.field.enabled")}
                  checked={state.referral_enabled}
                  disabled={saving}
                  onChange={(value) => apply({ referral_enabled: value })}
                />
                <InlineEditRow
                  label={t("admin.settings.field.requiredRefs")}
                  value={state.referral_required_count}
                  type="number"
                  saving={saving}
                  onSave={(value) =>
                    saveNumber(t("admin.settings.field.requiredRefs"), value, (n) => ({
                      referral_required_count: n,
                    }))
                  }
                />
              </div>
            ),
          },
          {
            id: "pricing",
            titleKey: "admin.settings.group.pro",
            content: (
              <div className="divide-y divide-border">
                <InlineEditRow
                  label={t("admin.settings.field.proPrice")}
                  value={state.pro_price}
                  type="number"
                  saving={saving}
                  onSave={(value) =>
                    saveNumber(t("admin.settings.field.proPrice"), value, (n) => ({ pro_price: n }))
                  }
                />
                <InlineEditRow
                  label={t("admin.settings.field.referralReward")}
                  value={state.referral_reward}
                  type="number"
                  saving={saving}
                  onSave={(value) =>
                    saveNumber(t("admin.settings.field.referralReward"), value, (n) => ({
                      referral_reward: n,
                    }))
                  }
                />
                <InlineEditRow
                  label={t("admin.settings.field.proMinSalary")}
                  value={state.pro_min_salary}
                  type="number"
                  saving={saving}
                  onSave={(value) =>
                    saveNumber(t("admin.settings.field.proMinSalary"), value, (n) => ({
                      pro_min_salary: n,
                    }))
                  }
                />
              </div>
            ),
          },
          {
            id: "resume",
            titleKey: "admin.settings.group.resumeKpi",
            content: (
              <div className="divide-y divide-border">
                <InlineEditRow
                  label={t("admin.settings.field.targetCreationMinutes")}
                  value={state.resume_target_creation_minutes}
                  type="number"
                  saving={saving}
                  onSave={(value) =>
                    saveNumber(t("admin.settings.field.targetCreationMinutes"), value, (n) => ({
                      resume_target_creation_minutes: n,
                    }))
                  }
                />
                <InlineEditRow
                  label={t("admin.settings.field.targetCompletionRate")}
                  value={state.resume_target_completion_rate}
                  type="number"
                  saving={saving}
                  onSave={(value) =>
                    saveNumber(t("admin.settings.field.targetCompletionRate"), value, (n) => ({
                      resume_target_completion_rate: n,
                    }))
                  }
                />
                <InlineEditRow
                  label={t("admin.settings.field.targetSendRate")}
                  value={state.resume_target_send_success_rate}
                  type="number"
                  saving={saving}
                  onSave={(value) =>
                    saveNumber(t("admin.settings.field.targetSendRate"), value, (n) => ({
                      resume_target_send_success_rate: n,
                    }))
                  }
                />
                <InlineEditRow
                  label={t("admin.settings.field.targetExportRate")}
                  value={state.resume_target_export_success_rate}
                  type="number"
                  saving={saving}
                  onSave={(value) =>
                    saveNumber(t("admin.settings.field.targetExportRate"), value, (n) => ({
                      resume_target_export_success_rate: n,
                    }))
                  }
                />
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}
