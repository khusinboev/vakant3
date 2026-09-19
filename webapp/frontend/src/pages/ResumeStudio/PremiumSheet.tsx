import { Link } from "react-router-dom";
import { Check } from "lucide-react";

import BottomSheet from "../../components/ui/BottomSheet";
import { useT } from "../../i18n/useT";

export type PremiumSheetProps = {
  open: boolean;
  onClose: () => void;
  /** How many templates the Pro plan unlocks. */
  premiumCount: number;
};

/** Upsell shown when a premium template is picked (or refused by the API). */
export default function PremiumSheet({ open, onClose, premiumCount }: PremiumSheetProps) {
  const t = useT();

  const perks = [
    t("resume.premium.perk1", { n: premiumCount }),
    t("resume.premium.perk2"),
    t("resume.premium.perk3"),
  ];

  return (
    <BottomSheet open={open} onClose={onClose} ariaLabel={t("resume.premium.title")}>
      <div className="mb-4 text-center">
        <div className="mb-2 text-4xl">💎</div>
        <p className="text-base font-bold text-text">{t("resume.premium.title")}</p>
        <p className="mt-1 text-sm text-muted">{t("resume.premium.body")}</p>
      </div>

      <ul className="mb-4 space-y-2">
        {perks.map((perk) => (
          <li key={perk} className="flex items-center gap-2 text-sm text-muted">
            <Check size={14} className="shrink-0 text-success" /> {perk}
          </li>
        ))}
      </ul>

      <Link
        to="/wallet"
        className="tap-target mb-2 flex w-full items-center justify-center rounded-2xl bg-primary py-3.5 text-sm font-bold text-primaryFg"
        onClick={onClose}
      >
        💳 {t("resume.premium.toWallet")}
      </Link>
      <button
        type="button"
        className="tap-target w-full rounded-2xl bg-surfaceAlt py-3 text-sm font-medium text-text"
        onClick={onClose}
      >
        {t("common.close")}
      </button>
    </BottomSheet>
  );
}
