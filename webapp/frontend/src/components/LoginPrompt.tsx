type Props = {
  onClose: () => void;
};

/**
 * Bottom-sheet modal shown when an unauthenticated user tries to use a
 * protected feature (save a vacancy, open Saves or Profile tabs).
 *
 * Tapping "Botga qaytish" closes the Telegram Mini App so the user can
 * interact with the bot and then re-open the app (which will auto-authenticate
 * via Telegram.WebApp.initData on the next open).
 */
export default function LoginPrompt({ onClose }: Props) {
  const goToBot = () => {
    // Close the Mini App — the user will land back in the Telegram chat.
    const tg = (window as Window & { Telegram?: { WebApp?: { close?: () => void } } }).Telegram?.WebApp;
    if (tg?.close) {
      tg.close();
    } else {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center"
      onClick={onClose}
    >
      {/* backdrop */}
      <div className="absolute inset-0 bg-black/40" />

      {/* sheet */}
      <div
        className="relative w-full max-w-lg rounded-t-3xl bg-white px-6 pb-10 pt-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* drag handle */}
        <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-slate-200" />

        <p className="text-center text-lg font-bold text-slate-900">Kirish kerak</p>
        <p className="mt-2 text-center text-sm text-slate-500">
          Bu funksiyadan foydalanish uchun botda hisobingiz bo'lishi kerak.
        </p>

        <button
          className="tap-target mt-6 w-full rounded-2xl bg-brand-500 px-4 py-3 text-sm font-semibold text-white"
          onClick={goToBot}
        >
          Botga qaytish
        </button>
        <button
          className="tap-target mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-600"
          onClick={onClose}
        >
          Bekor qilish
        </button>
      </div>
    </div>
  );
}
