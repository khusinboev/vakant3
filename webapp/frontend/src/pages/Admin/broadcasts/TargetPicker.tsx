import { Users } from "lucide-react";

import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import { useRegions, regionName } from "../../../hooks/useStaticList";
import { SegmentedControl } from "../ui";
import { FIELD_CLS } from "./labels";
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

const LANGS: { value: string; label: string }[] = [
  { value: "uz", label: "UZ" },
  { value: "ru", label: "RU" },
  { value: "en", label: "EN" },
];

/**
 * Segment picker: the kind (seven values — a select, not a segmented control,
 * at 390px), then the extra control its `<prefix>:<value>` form needs.
 */
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
    <div className="space-y-2">
      <select
        id="broadcast-segment"
        value={kind}
        aria-label={t("adminBroadcasts.target.label")}
        onChange={(event) => {
          const next = event.target.value as SegmentKind;
          onKindChange(next);
          onValueChange(next === "lang" ? "uz" : next === "active_days" ? "30" : "");
        }}
        className={FIELD_CLS}
      >
        {SEGMENT_KINDS.map((option) => (
          <option key={option} value={option}>
            {t(SEGMENT_LABEL_KEY[option])}
          </option>
        ))}
      </select>

      {kind === "lang" && (
        <SegmentedControl
          full
          options={LANGS}
          value={value || "uz"}
          onChange={onValueChange}
          ariaLabel={t("adminBroadcasts.target.langValue")}
        />
      )}

      {kind === "region" && (
        <select
          value={value}
          aria-label={t("adminBroadcasts.target.regionValue")}
          onChange={(event) => onValueChange(event.target.value)}
          className={FIELD_CLS}
        >
          <option value="">—</option>
          {(regions.data ?? []).map((region) => (
            <option key={region.soato} value={region.soato}>
              {regionName(region)}
            </option>
          ))}
        </select>
      )}

      {kind === "active_days" && (
        <input
          type="number"
          min={1}
          max={9999}
          inputMode="numeric"
          value={value}
          aria-label={t("adminBroadcasts.target.daysValue")}
          onChange={(event) => onValueChange(event.target.value.replace(/\D/g, "").slice(0, 4))}
          className={FIELD_CLS}
        />
      )}

      <label className="flex min-h-[32px] items-center justify-between gap-2 text-[13px] text-text">
        <span className="min-w-0">{t("adminBroadcasts.target.excludeBlocked")}</span>
        <input
          type="checkbox"
          checked={excludeBlocked}
          onChange={(event) => onExcludeBlockedChange(event.target.checked)}
          className="h-4 w-4 shrink-0 rounded border-border text-primary focus:ring-primary/40"
        />
      </label>

      <p className="flex items-center gap-1.5 text-[11px] text-muted">
        <Users size={12} aria-hidden="true" />
        {estimate === null
          ? t("adminBroadcasts.target.estimateHint")
          : t("adminBroadcasts.target.estimate", { count: formatNumber(estimate) })}
      </p>
    </div>
  );
}
