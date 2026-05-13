import { useState } from "react";

import client from "../../api/client";

type Props = {
  open: boolean;
  onClose: () => void;
  data: { uid: string; data: Record<string, unknown> } | null;
};

function Row({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex gap-2 text-sm">
      <span className="w-28 shrink-0 font-medium text-slate-500">{label}</span>
      <span className="text-slate-800">{value}</span>
    </div>
  );
}

export default function VacancyDetail({ open, onClose, data }: Props) {
  const [isSending, setIsSending] = useState(false);
  if (!open || !data) return null;

  const d = data.data;
  const normalized = (d.normalized as Record<string, unknown> | undefined) || {};

  const cleanHtmlText = (value: unknown) => {
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
  };

  const mapCode = (value: unknown, mapping: Record<number, string>) => {
    const asNumber = typeof value === "number" ? value : Number(value);
    if (!Number.isFinite(asNumber)) return "";
    return mapping[asNumber] || `Kod ${asNumber}`;
  };

  const genderMap: Record<number, string> = { 1: "Erkak", 2: "Ayol", 3: "Farqi yo'q" };
  const workTypeMap: Record<number, string> = { 1: "Doimiy ish", 2: "Vaqtinchalik ish", 3: "Mavsumiy ish" };
  const busynessTypeMap: Record<number, string> = { 1: "To'liq bandlik", 2: "Qisman bandlik" };
  const educationMap: Record<number, string> = { 1: "Umumiy o'rta", 2: "O'rta maxsus", 3: "Bakalavr", 4: "Magistr" };
  const experienceMap: Record<number, string> = { 1: "Tajriba talab etilmaydi", 2: "1 yilgacha", 3: "1-3 yil", 4: "3+ yil" };

  // Basic fields
  const title = String(normalized.title || d.title || "Vakansiya");
  const companyObj = d.company as Record<string, unknown> | null | undefined;
  const company = String(normalized.company || companyObj?.name || d.company_name || "");
  const minSalary = d.min_salary as number | null | undefined;
  const maxSalary = d.max_salary as number | null | undefined;
  const salary =
    String(normalized.salary || "") ||
    (minSalary && maxSalary
      ? `${minSalary.toLocaleString("uz")} – ${maxSalary.toLocaleString("uz")} so'm`
      : minSalary
        ? `${minSalary.toLocaleString("uz")} so'mdan`
        : String(d.salary_text || "Kelishiladi"));

  const address = String(normalized.address || d.address || "");
  const districtObj = d.soato_district as Record<string, unknown> | null | undefined;
  const district = String(normalized.district || districtObj?.name_uz || districtObj?.name || "");
  const regionObj = d.soato_region as Record<string, unknown> | null | undefined;
  const region = String(normalized.region || regionObj?.name_uz || regionObj?.name || "");

  const hrObj = d.hr as Record<string, unknown> | null | undefined;
  const hrPhone = String(hrObj?.phone || d.phone || "");
  const hrEmail = String(hrObj?.email || d.email || "");
  const hrName = String(hrObj?.name || hrObj?.full_name || "");

  const info = String(normalized.description || cleanHtmlText(d.info || d.description || d.requirements || ""));
  const workType = String(normalized.work_type || mapCode(d.work_type, workTypeMap) || d.employment_type || "");
  const busynessType = String(normalized.busyness_type || mapCode(d.busyness_type, busynessTypeMap) || "");
  const experience = String(normalized.experience || mapCode(d.work_experiance, experienceMap) || d.work_experience || "");
  const education = String(normalized.education || mapCode(d.min_education, educationMap) || d.education || "");
  const gender = String(normalized.gender || mapCode(d.gender, genderMap) || "");
  const age = String(d.age || "");
  const deadline = String(normalized.deadline || d.deadline || d.end_date || "");
  const postedAt = String(normalized.posted_at || d.created_at || d.posted_at || "");
  const workingHours = String(normalized.working_hours || [d.working_time_from, d.working_time_to].filter(Boolean).join(" - "));
  const count = String(normalized.count || d.count || "");

  const sendToTelegram = async () => {
    if (isSending) return;
    setIsSending(true);
    try {
      await client.post(`/jobs/${data.uid}/send-telegram`);
      alert("Vakansiya botga yuborildi.");
      const chatLink = "https://t.me/alingniurmabot";
      const webApp = (window.Telegram?.WebApp as { openTelegramLink?: (url: string) => void } | undefined);
      if (webApp?.openTelegramLink) {
        webApp.openTelegramLink(chatLink);
      } else {
        window.open(chatLink, "_blank", "noopener,noreferrer");
      }
    } catch {
      alert("Yuborishda xatolik. Qayta urinib ko'ring.");
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-30 bg-slate-950/50" onClick={onClose}>
      <div
        className="absolute bottom-0 left-0 right-0 flex max-h-[90vh] flex-col rounded-t-3xl bg-white shadow-2xl md:left-1/2 md:top-1/2 md:max-h-[85vh] md:w-[42rem] md:-translate-x-1/2 md:-translate-y-1/2 md:rounded-3xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 pb-3 pt-4">
          <div className="min-w-0">
            <h3 className="text-lg font-bold leading-snug text-slate-900">{title}</h3>
            {company && <p className="mt-0.5 text-sm font-medium text-brand-600">{company}</p>}
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            ✕
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 pb-[calc(1rem+var(--tg-content-safe-area-bottom))] pl-[calc(1.25rem+var(--tg-content-safe-area-left))] pr-[calc(1.25rem+var(--tg-content-safe-area-right))] md:pb-4 md:pl-5 md:pr-5">
          {/* Salary badge */}
          <span className="inline-block rounded-full bg-brand-50 px-3 py-1 text-sm font-semibold text-brand-700">
            {salary}
          </span>

          {/* Details grid */}
          <div className="mt-4 space-y-2">
            <Row label="Manzil" value={address || [district, region].filter(Boolean).join(", ") || null} />
            <Row label="Tuman/shahar" value={district || null} />
            <Row label="Viloyat" value={region || null} />
            <Row label="Ish turi" value={workType || null} />
            <Row label="Bandlik" value={busynessType || null} />
            <Row label="Tajriba" value={experience || null} />
            <Row label="Ta'lim" value={education || null} />
            <Row label="Jins" value={gender || null} />
            <Row label="Yosh" value={age || null} />
            <Row label="Ish vaqti" value={workingHours || null} />
            <Row label="O'rinlar soni" value={count || null} />
            <Row label="Muddati" value={deadline || null} />
            <Row label="E'lon sanasi" value={postedAt ? postedAt.slice(0, 10) : null} />
          </div>

          {/* Description */}
          {info && (
            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Tavsif</p>
              <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{info}</p>
            </div>
          )}

          {/* HR contacts */}
          {(hrName || hrPhone || hrEmail) && (
            <div className="mt-4 rounded-2xl bg-slate-50 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Aloqa</p>
              <div className="mt-2 space-y-1">
                {hrName && <p className="text-sm font-medium text-slate-800">{hrName}</p>}
                {hrPhone && (
                  <a href={`tel:${hrPhone}`} className="block text-sm text-brand-600 underline-offset-2 hover:underline">
                    📞 {hrPhone}
                  </a>
                )}
                {hrEmail && (
                  <a href={`mailto:${hrEmail}`} className="block text-sm text-brand-600 underline-offset-2 hover:underline">
                    ✉️ {hrEmail}
                  </a>
                )}
              </div>
            </div>
          )}

          {/* Telegram button */}
          <button
            onClick={sendToTelegram}
            disabled={isSending}
            className="tap-target mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-[#2AABEE] px-4 py-3 text-sm font-semibold text-white"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
              <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.248-2.012 9.47c-.148.658-.537.818-1.088.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.56-4.456c.537-.194 1.006.12.889.746z" />
            </svg>
            {isSending ? "Yuborilmoqda..." : "Telegramda ko'rish"}
          </button>
        </div>
      </div>
    </div>
  );
}
