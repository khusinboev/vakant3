import { useT } from "../../i18n/useT";
import type { ResumeProfileData } from "./types";

/**
 * Live preview of the resume itself. Like `TemplatePreview`, it stands in for a
 * printed page, so its palette is literal white/slate and stays light in dark
 * mode — only the frame around it follows the theme.
 */
export default function ResumePreview({
  profile,
  accentColor,
  templateName,
}: {
  profile: ResumeProfileData;
  accentColor: string;
  templateName: string;
}) {
  const t = useT();
  const contacts = [profile.phone, profile.email, profile.location].filter(Boolean).join(" · ");

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-white shadow-sm">
      <div className="px-4 py-3 text-white" style={{ backgroundColor: accentColor }}>
        <p className="text-sm font-bold">{profile.full_name || t("resume.card.unnamed")}</p>
        <p className="mt-0.5 text-xs opacity-90">{profile.position || t("resume.card.noPosition")}</p>
        <p className="mt-0.5 text-[10px] opacity-75">{contacts || t("resume.card.noContact")}</p>
      </div>

      <div className="space-y-2.5 p-3 text-xs">
        {profile.summary && (
          <div>
            <p className="mb-1 text-[9px] font-semibold uppercase tracking-wide text-slate-600">
              {t("resume.card.summary")}
            </p>
            <p className="line-clamp-3 leading-relaxed text-slate-700">{profile.summary}</p>
          </div>
        )}

        {profile.experiences.length > 0 && (
          <div>
            <p className="mb-1 text-[9px] font-semibold uppercase tracking-wide text-slate-600">
              {t("resume.card.experience")}
            </p>
            {profile.experiences.slice(0, 2).map((item, index) => (
              <p key={index} className="text-slate-700">
                {[item.role, item.company].filter(Boolean).join(" @ ") || t("resume.card.experience")}
                {item.start_date && <span className="ml-1 text-slate-400">· {item.start_date}</span>}
              </p>
            ))}
          </div>
        )}

        {profile.skills.length > 0 && (
          <div>
            <p className="mb-1 text-[9px] font-semibold uppercase tracking-wide text-slate-600">
              {t("resume.card.skills")}
            </p>
            <p className="line-clamp-2 text-slate-700">{profile.skills.slice(0, 8).join(", ")}</p>
          </div>
        )}

        <p className="text-right text-[9px] text-slate-400">{templateName}</p>
      </div>
    </div>
  );
}
