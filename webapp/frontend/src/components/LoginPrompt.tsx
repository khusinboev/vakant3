import BottomSheet from "./ui/BottomSheet";
import { useT } from "../i18n/useT";

type Props = {
  onClose: () => void;
};

/**
 * Bottom sheet shown when an unauthenticated user tries to use a protected
 * feature (save a vacancy, open Saves or Profile).
 *
 * "Back to the bot" closes the Mini App so the user can interact with the bot
 * and reopen the app, which then auto-authenticates via initData.
 */
export default function LoginPrompt({ onClose }: Props) {
  const t = useT();

  const goToBot = () => {
    const tg = window.Telegram?.WebApp;
    if (tg?.close) tg.close();
    else onClose();
  };

  return (
    <BottomSheet open onClose={onClose} ariaLabel={t("login.title")}>
      <p className="text-center text-lg font-bold text-text">{t("login.title")}</p>
      <p className="mt-2 text-center text-sm text-muted">{t("login.body")}</p>

      <button
        type="button"
        className="tap-target mt-6 w-full rounded-2xl bg-primary px-4 py-3 text-sm font-semibold text-primaryFg"
        onClick={goToBot}
      >
        {t("login.toBot")}
      </button>
      <button
        type="button"
        className="tap-target mt-2 w-full rounded-2xl border border-border px-4 py-3 text-sm font-semibold text-muted"
        onClick={onClose}
      >
        {t("common.cancel")}
      </button>
    </BottomSheet>
  );
}
