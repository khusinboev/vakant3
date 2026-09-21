import { Users } from "lucide-react";

import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import { INPUT_CLS } from "../../../components/ui/Field";
import { useRegions, regionName } from "../../../hooks/useStaticList";
import { SEGMENT_KINDS, SEGMENT_LABEL_KEY, type SegmentKind } from "./segments";

export type TargetPickerProps = {
  kind: SegmentKind;
  value: string;
  onKindChange: (kind: SegmentKind) => void;
  onValueChange: (value: string) => void;
  excludeBlocked: boolean;
  onExcludeBlockedChange: (value: boolean) => void;
  /** Recipient count the queue call reported; `null` until then. */
  estimate: number | null;
};

const LANGS = ["uz", "ru", "en"] as const;

/** Segment picker: the kind, then the extra control its `<prefix>:<value>` form needs. */
export default function TargetPicker({
  kind,
  value,
  onKindChange,
  onValueChange,
  excludeBlocked,
  onExcludeBlockedChange,
  estimate,
}: TargetPickerProps) {
  const t = useT();
  const { formatNumber } = useLocale();
  const regions = useRegions();

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <label htmlFor="broadcast-segment" className="block text-xs font-semibold text-muted">
          {t("adminBroadcasts.target.label")}
        </label>
        <select
          id="broadcast-segment"
          value={kind}
          onChange={(event) => {
            const next = event.target.value as SegmentKind;
            onKindChange(next);
            onValueChange(next === "lang" ? "uz" : next === "active_days" ? "30" : "");
          }}
          className={INPUT_CLS}
        >
          {SEGMENT_KINDS.map((option) => (
            <option key={option} value={option}>
              {t(SEGMENT_LABEL_KEY[option])}
            </option>
          ))}
        </select>
      </div>

      {kind === "lang" && (
        <div className="space-y-1.5">
          <label htmlFor="broadcast-segment-lang" className="block text-xs font-semibold text-muted">
            {t("adminBroadcasts.target.langValue")}
          </label>
          <select
            id="broadcast-segment-lang"
            value={value || "uz"}
            onChange={(event) => onValueChange(event.target.value)}
            className={INPUT_CLS}
          >
            {LANGS.map((code) => (
              <option key={code} value={code}>
                {code.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
      )}

      {kind === "region" && (
        <div className="space-y-1.5">
          <label htmlFor="broadcast-segment-region" className="block text-xs font-semibold text-muted">
            {t("adminBroadcasts.target.regionValue")}
          </label>
          <select
            id="broadcast-segment-region"
            value={value}
            onChange={(event) => onValueChange(event.target.value)}
            className={INPUT_CLS}
          >
            <option value="">—</option>
            {(regions.data ?? []).map((region) => (
              <option key={region.soato} value={region.soato}>
                {regionName(region)}
              </option>
            ))}
          </select>
        </div>
      )}

      {kind === "active_days" && (
        <div className="space-y-1.5">
          <label htmlFor="broadcast-segment-days" className="block text-xs font-semibold text-muted">
            {t("adminBroadcasts.target.daysValue")}
          </label>
          <input
            id="broadcast-segment-days"
            type="number"
            min={1}
            max={9999}
            inputMode="numeric"
            value={value}
            onChange={(event) => onValueChange(event.target.value.replace(/\D/g, "").slice(0, 4))}
            className={INPUT_CLS}
          />
        </div>
      )}

      <label className="flex items-center gap-2 text-sm text-text">
        <input
          type="checkbox"
          checked={excludeBlocked}
          onChange={(event) => onExcludeBlockedChange(event.target.checked)}
          className="h-4 w-4 rounded border-border text-primary focus:ring-primary/40"
        />
        {t("adminBroadcasts.target.excludeBlocked")}
      </label>

      <p className="flex items-center gap-1.5 text-xs text-muted">
        <Users size={13} aria-hidden="true" />
        {estimate === null
          ? t("adminBroadcasts.target.estimateHint")
          : t("adminBroadcasts.target.estimate", { count: formatNumber(estimate) })}
      </p>
    </div>
  );
}
