import { Lock, X } from "lucide-react";
import { useNavigate } from "react-router-dom";

import BottomSheet from "../ui/BottomSheet";
import { botDeepLink, openTelegramLink } from "../../lib/constants";
import { useT, useVacancyCodeLabel } from "../../i18n/useT";
import { useLocale } from "../../i18n/useLocale";
import type { VacancyCodes, VacancyDetailResponse } from "../../types";

type Props = {
  open: boolean;
  onClose: () => void;
  data: VacancyDetailResponse | null;
  isLoading?: boolean;
  isLocked?: boolean;
};

function Row({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex gap-2 text-sm">
      <span className="w-28 shrink-0 font-medium text-muted">{label}</span>
      <span className="text-text">{value}</span>
    </div>
  );
}

function cleanHtmlText(value: unknown): string {
  if (typeof value !== "string") return "";
  return value
    .replace(/<\s*br\s*\/?\s*>/gi, "\n")
    .replace(/<\s*\/\s*(p|div|li|ul|ol|h[1-6])\s*>/gi, "\n")
    .replace(/<\s*li\b[^>]*>/gi, "- ")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** "" -> null, so `Row` can skip the line instead of printing an empty value. */
function str(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  return text ? text : null;
}

export default function VacancyDetail({ open, onClose, data, isLoading, isLocked = false }: Props) {
  const navigate = useNavigate();
  const t = useT();
  const { formatNumber } = useLocale();
  const codeLabel = useVacancyCodeLabel();

  if (!open) return null;

  if (isLoading || !data) {
    return (
      <BottomSheet open onClose={onClose} showHandle={false} ariaLabel={t("common.loading")}>
        <div className="flex h-40 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      </BottomSheet>
    );
  }

  const d = data.data;
  const normalized = d.normalized ?? {};
  const codes: VacancyCodes = normalized.codes ?? {};

  const title = str(normalized.title) || str(d.title) || t("vacancy.fallbackTitle");
  const companyObj = d.company as Record<string, unknown> | null | undefined;
  const company = str(normalized.company) || str(companyObj?.name) || str(d.company_name);

  const minSalary = typeof d.min_salary === "number" ? d.min_salary : null;
  const maxSalary = typeof d.max_salary === "number" ? d.max_salary : null;
  const salary =
    str(normalized.salary) ||
    (minSalary && maxSalary
      ? t("vacancy.salary.range", { min: formatNumber(minSalary), max: formatNumber(maxSalary) })
      : minSalary
        ? t("vacancy.salary.from", { min: formatNumber(minSalary) })
        : str(d.salary_text) || t("vacancy.salary.negotiable"));

  const address = str(normalized.address) || str(d.address);
  const districtObj = d.soato_district as Record<string, unknown> | null | undefined;
  const district = str(normalized.district) || str(districtObj?.name) || str(districtObj?.name_uz);
  const regionObj = d.soato_region as Record<string, unknown> | null | undefined;
  const region = str(normalized.region) || str(regionObj?.name) || str(regionObj?.name_uz);

  const hrObj = d.hr as Record<string, unknown> | null | undefined;
  const hrPhone = str(hrObj?.phone) || str(d.phone);
  const hrEmail = str(hrObj?.email) || str(d.email);
  const hrName = str(hrObj?.name) || str(hrObj?.full_name);

  const info =
    str(normalized.description) ||
    str(cleanHtmlText(d.info ?? d.description ?? d.requirements));

  // Prefer our own maps over the server-rendered label (CONTRACT.md).
  const workType = codeLabel("vacancy.work_type", codes.work_type ?? d.work_type) || str(normalized.work_type);
  const busyness = codeLabel("vacancy.busyness", codes.busyness_type ?? d.busyness_type) || str(normalized.busyness_type);
  const payment = codeLabel("vacancy.payment", codes.payment_type ?? d.payment_type) || str(normalized.payment_type);
  const experience = codeLabel("vacancy.experience", codes.experience ?? d.work_experiance) || str(normalized.experience);
  const education = codeLabel("vacancy.education", codes.education ?? d.min_education) || str(normalized.education);
  const gender = codeLabel("vacancy.gender", codes.gender ?? d.gender) || str(normalized.gender);

  const age = str(d.age);
  const deadline = str(normalized.deadline) || str(d.deadline) || str(d.end_date);
  const postedAt = str(normalized.posted_at) || str(d.created_at) || str(d.posted_at);
  const workingHours =
    str(normalized.working_hours) ||
    str([d.working_time_from, d.working_time_to].filter(Boolean).join(" - "));
  const count = str(normalized.count) || str(d.count);

  const primaryAction = () => {
    if (isLocked) {
      // Locked vacancy: the contact is behind Pro — send the user to the wallet.
      onClose();
      navigate("/wallet");
      return;
    }
    // Unlocked: open the bot, which posts the full vacancy with contacts.
    openTelegramLink(botDeepLink(`vacancy_${data.uid}`));
    window.Telegram?.WebApp?.close?.();
  };

  return (
    <BottomSheet open onClose={onClose} maxHeightClass="max-h-[90dvh]" ariaLabel={title}>
      {/* Header */}
      <div className="-mx-5 -mt-4 mb-4 flex items-start justify-between gap-3 border-b border-border px-5 pb-3 pt-1">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="min-w-0 flex-1 text-lg font-bold leading-snug text-text">{title}</h3>
            {isLocked && (
              <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-warning/15 px-2 py-0.5 text-xs font-bold text-warning">
                <Lock size={12} /> PRO
              </span>
            )}
          </div>
          {company && <p className="mt-0.5 text-sm font-medium text-primary">{company}</p>}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label={t("common.close")}
          className="shrink-0 rounded-full p-1.5 text-muted hover:bg-surfaceAlt hover:text-text"
        >
          <X size={16} />
        </button>
      </div>

      <span className="inline-block rounded-full bg-primary/10 px-3 py-1 text-sm font-semibold text-primary">
        {salary}
      </span>

      <div className="mt-4 space-y-2">
        <Row label={t("vacancy.row.address")} value={address || [district, region].filter(Boolean).join(", ") || null} />
        <Row label={t("vacancy.row.district")} value={district} />
        <Row label={t("vacancy.row.region")} value={region} />
        <Row label={t("vacancy.row.workType")} value={workType} />
        <Row label={t("vacancy.row.busyness")} value={busyness} />
        <Row label={t("vacancy.row.payment")} value={payment} />
        <Row label={t("vacancy.row.experience")} value={experience} />
        <Row label={t("vacancy.row.education")} value={education} />
        <Row label={t("vacancy.row.gender")} value={gender} />
        <Row label={t("vacancy.row.age")} value={age} />
        <Row label={t("vacancy.row.workingHours")} value={workingHours} />
        <Row label={t("vacancy.row.count")} value={count} />
        <Row label={t("vacancy.row.deadline")} value={deadline} />
        <Row label={t("vacancy.row.postedAt")} value={postedAt ? postedAt.slice(0, 10) : null} />
      </div>

      {isLocked && (
        <div className="mt-4 rounded-2xl border border-warning/30 bg-warning/10 p-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-lg">🔒</span>
            <p className="text-sm font-bold text-warning">{t("vacancy.lockedTitle")}</p>
          </div>
          <div className="mb-3 space-y-2">
            <div className="flex h-8 items-center rounded-lg bg-warning/15 px-3">
              <span className="select-none text-xs text-warning/70">📞 ••• ••• ••••</span>
            </div>
            <div className="flex h-8 items-center rounded-lg bg-warning/15 px-3">
              <span className="select-none text-xs text-warning/70">✉️ •••@•••.com</span>
            </div>
          </div>
          <p className="text-xs text-warning">{t("vacancy.lockedHint")}</p>
        </div>
      )}

      {info && (
        <div className="mt-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            {t("vacancy.description")}
          </p>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-text">{info}</p>
        </div>
      )}

      {(hrName || hrPhone || hrEmail) && !isLocked && (
        <div className="mt-4 rounded-2xl bg-surfaceAlt p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            {t("vacancy.contacts")}
          </p>
          <div className="mt-2 space-y-1">
            {hrName && <p className="text-sm font-medium text-text">{hrName}</p>}
            {hrPhone && (
              <a href={`tel:${hrPhone}`} className="block text-sm text-primary underline-offset-2 hover:underline">
                📞 {hrPhone}
              </a>
            )}
            {hrEmail && (
              <a href={`mailto:${hrEmail}`} className="block text-sm text-primary underline-offset-2 hover:underline">
                ✉️ {hrEmail}
              </a>
            )}
          </div>
        </div>
      )}

      {isLocked ? (
        <button
          type="button"
          onClick={primaryAction}
          className="tap-target mt-4 w-full rounded-2xl bg-warning px-4 py-3 text-sm font-semibold text-white dark:text-bg"
        >
          💳 {t("vacancy.goPro")}
        </button>
      ) : (
        <button
          type="button"
          onClick={primaryAction}
          className="tap-target mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-[#2AABEE] px-4 py-3 text-sm font-semibold text-white"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5" aria-hidden="true">
            <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.248-2.012 9.47c-.148.658-.537.818-1.088.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.56-4.456c.537-.194 1.006.12.889.746z" />
          </svg>
          {t("vacancy.openInBot")}
        </button>
      )}
    </BottomSheet>
  );
}
