import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { adminPagePath } from "../routing";

/**
 * The entry gate (CONTRACT_P12 §m006, `require_entry`) is checked in order:
 * bot start -> subscription to every enabled channel below -> the referral
 * gate configured on the Settings page. Rendered as the body of a closed
 * `Accordion` item on `ChannelsPage` (spec §4/§4b) — the item's own header
 * already carries the title, so this component is body content only.
 */
export default function GateInfoCard() {
  const t = useT();

  const steps: { key: string; labelKey: TranslationKey }[] = [
    { key: "start", labelKey: "adminChannels.info.step.start" },
    { key: "subscribe", labelKey: "adminChannels.info.step.subscribe" },
    { key: "referral", labelKey: "adminChannels.info.step.referral" },
  ];

  return (
    <div className="space-y-2">
      <ol className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
        {steps.map((step, index) => (
          <li key={step.key} className="flex items-center gap-1.5">
            <span className="rounded-full bg-surfaceAlt px-2 py-1 font-medium text-text">
              {t(step.labelKey)}
            </span>
            {index < steps.length - 1 && <ArrowRight size={11} aria-hidden="true" />}
          </li>
        ))}
      </ol>
      <p className="text-[11px] text-muted">
        {t("adminChannels.info.description")}{" "}
        <Link to={adminPagePath("settings")} className="font-semibold text-primary underline-offset-2 hover:underline">
          {t("adminChannels.info.settingsLink")}
        </Link>
      </p>
    </div>
  );
}
