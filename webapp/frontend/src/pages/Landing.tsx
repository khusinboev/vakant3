export default function Landing() {
  return (
    <div className="flex min-h-[var(--app-viewport-height)] items-center justify-center px-4 py-8">
      <div className="card w-full max-w-xl p-6 text-center md:p-8">
        <p className="font-display text-3xl font-extrabold text-brand-700 md:text-4xl">IshBot</p>
        <p className="mt-3 text-sm leading-6 text-slate-600 md:text-base">
          Ish topish uchun Telegram botdan foydalaning. Quyidagi tugma orqali botga o‘ting va
          webappni to‘g‘ridan to‘g‘ri oching.
        </p>

        <div className="mt-6 space-y-3">
          <a
            href="https://t.me/bandlikuzbot"
            target="_blank"
            rel="noopener noreferrer"
            className="tap-target block rounded-2xl bg-brand-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-brand-700"
          >
            Telegram botga o‘tish
          </a>

          <a
            href="/app"
            className="tap-target block rounded-2xl border border-slate-300 px-4 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            Webappni ochish
          </a>
        </div>
      </div>
    </div>
  );
}
