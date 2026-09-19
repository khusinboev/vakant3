import { Crown, GitBranch, Megaphone, Zap } from "lucide-react";

import useToast from "../../../hooks/useToast";
import { useT } from "../../../i18n/useT";
import GroupCard from "../components/GroupCard";
import InlineEditRow from "../components/InlineEditRow";
import LangSegmentRow from "../components/LangSegmentRow";
import ToggleRow from "../components/ToggleRow";
import { useAdminStatePatch } from "../useAdminQueries";
import type { AdminState, AdminStatePatch } from "../types";

export default function SettingsTab({ state }: { state: AdminState }) {
  const t = useT();
  const toast = useToast();
  const patch = useAdminStatePatch();
  const saving = patch.isPending;

  const apply = (payload: AdminStatePatch) => {
    patch.mutate(payload, {
      onSuccess: () => toast.success(t("admin.settings.saved")),
      onError: (error) => toast.apiError(error),
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
      toast.error(t("admin.validation.empty", { label }));
      return;
    }
    const value = Number(trimmed);
    if (!Number.isFinite(value)) {
      toast.error(t("admin.validation.number", { label }));
      return;
    }
    if (value < 0) {
      toast.error(t("admin.validation.negative", { label }));
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
      toast.error(t("admin.validation.empty", { label }));
      return;
    }
    apply(build(trimmed));
  };

  const perDayLabelMin = t("admin.field.perDayMin");
  const perDayLabelMax = t("admin.field.perDayMax");

  return (
    <div className="space-y-4">
      {saving && (
        <p
          role="status"
          className="rounded-xl bg-primary/10 px-4 py-2 text-center text-xs text-primary"
        >
          {t("common.saving")}
        </p>
      )}

      <GroupCard icon={Megaphone} title={t("admin.group.autoPost")}>
        <ToggleRow
          label={t("admin.field.enabled")}
          checked={state.auto_post_enabled}
          disabled={saving}
          onChange={(value) => apply({ auto_post_enabled: value })}
        />
        <InlineEditRow
          label={t("admin.field.channel")}
          value={state.auto_post_channel}
          saving={saving}
          onSave={(value) =>
            saveText(t("admin.field.channel"), value, (channel) => ({
              auto_post_channel: channel,
            }))
          }
        />
        <LangSegmentRow
          label={t("admin.field.channelLang")}
          value={state.channel_lang}
          disabled={saving}
          onChange={(lang) => apply({ channel_lang: lang })}
        />
        <InlineEditRow
          label={t("admin.field.autoPostMinSalary")}
          value={state.auto_post_min_salary}
          type="number"
          saving={saving}
          onSave={(value) =>
            saveNumber(t("admin.field.autoPostMinSalary"), value, (n) => ({
              auto_post_min_salary: n,
            }))
          }
        />
        <div className="grid grid-cols-2 gap-x-6">
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
                    ? t("admin.validation.perDayRange", {
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
                    ? t("admin.validation.perDayRange", {
                        min: state.auto_post_per_day_min,
                        max: n,
                      })
                    : null,
              )
            }
          />
        </div>
      </GroupCard>

      <GroupCard icon={GitBranch} title={t("admin.group.referralGate")}>
        <ToggleRow
          label={t("admin.field.enabled")}
          checked={state.referral_enabled}
          disabled={saving}
          onChange={(value) => apply({ referral_enabled: value })}
        />
        <InlineEditRow
          label={t("admin.field.requiredRefs")}
          value={state.referral_required_count}
          type="number"
          saving={saving}
          onSave={(value) =>
            saveNumber(t("admin.field.requiredRefs"), value, (n) => ({
              referral_required_count: n,
            }))
          }
        />
      </GroupCard>

      <GroupCard icon={Crown} title={t("admin.group.pro")} accent="warning">
        <InlineEditRow
          label={t("admin.field.proPrice")}
          value={state.pro_price}
          type="number"
          saving={saving}
          onSave={(value) =>
            saveNumber(t("admin.field.proPrice"), value, (n) => ({ pro_price: n }))
          }
        />
        <InlineEditRow
          label={t("admin.field.referralReward")}
          value={state.referral_reward}
          type="number"
          saving={saving}
          onSave={(value) =>
            saveNumber(t("admin.field.referralReward"), value, (n) => ({ referral_reward: n }))
          }
        />
        <InlineEditRow
          label={t("admin.field.proMinSalary")}
          value={state.pro_min_salary}
          type="number"
          saving={saving}
          onSave={(value) =>
            saveNumber(t("admin.field.proMinSalary"), value, (n) => ({ pro_min_salary: n }))
          }
        />
      </GroupCard>

      <GroupCard icon={Zap} title={t("admin.group.resumeKpi")}>
        <InlineEditRow
          label={t("admin.field.targetCreationMinutes")}
          value={state.resume_target_creation_minutes}
          type="number"
          saving={saving}
          onSave={(value) =>
            saveNumber(t("admin.field.targetCreationMinutes"), value, (n) => ({
              resume_target_creation_minutes: n,
            }))
          }
        />
        <InlineEditRow
          label={t("admin.field.targetCompletionRate")}
          value={state.resume_target_completion_rate}
          type="number"
          saving={saving}
          onSave={(value) =>
            saveNumber(t("admin.field.targetCompletionRate"), value, (n) => ({
              resume_target_completion_rate: n,
            }))
          }
        />
        <InlineEditRow
          label={t("admin.field.targetSendRate")}
          value={state.resume_target_send_success_rate}
          type="number"
          saving={saving}
          onSave={(value) =>
            saveNumber(t("admin.field.targetSendRate"), value, (n) => ({
              resume_target_send_success_rate: n,
            }))
          }
        />
        <InlineEditRow
          label={t("admin.field.targetExportRate")}
          value={state.resume_target_export_success_rate}
          type="number"
          saving={saving}
          onSave={(value) =>
            saveNumber(t("admin.field.targetExportRate"), value, (n) => ({
              resume_target_export_success_rate: n,
            }))
          }
        />
      </GroupCard>
    </div>
  );
}
