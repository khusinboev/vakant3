import { ArrowRight, Info } from "lucide-react";
import { Link } from "react-router-dom";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { adminPagePath } from "../routing";

/**
 * The entry gate (CONTRACT_P12 §m006, `require_entry`) is checked in order:
 * bot start -> subscription to every enabled channel below -> the referral
 * gate configured on the Settings page. This card explains that chain so an
 * admin adding a channel here understands what it plugs into.
 */
export default function GateInfoCard() {
  const t = useT();

  const steps: { key: string; labelKey: TranslationKey }[] = [
    { key: "start", labelKey: "adminChannels.info.step.start" },
    { key: "subscribe", labelKey: "adminChannels.info.step.subscribe" },
    { key: "referral", labelKey: "adminChannels.info.step.referral" },
  ];

  return (
    <section className="card p-4">
      <div className="flex items-start gap-2.5">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Info size={14} aria-hidden="true" />
        </span>
        <div className="min-w-0 space-y-2">
          <h2 className="text-sm font-semibold text-text">{t("adminChannels.info.title")}</h2>
          <ol className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
            {steps.map((step, index) => (
              <li key={step.key} className="flex items-center gap-1.5">
                <span className="rounded-full bg-surfaceAlt px-2 py-1 font-medium text-text">
                  {t(step.labelKey)}
                </span>
                {index < steps.length - 1 && <ArrowRight size={12} aria-hidden="true" />}
              </li>
            ))}
          </ol>
          <p className="text-xs text-muted">
            {t("adminChannels.info.description")}{" "}
            <Link to={adminPagePath("settings")} className="font-semibold text-primary underline-offset-2 hover:underline">
              {t("adminChannels.info.settingsLink")}
            </Link>
          </p>
        </div>
      </div>
    </section>
  );
}
