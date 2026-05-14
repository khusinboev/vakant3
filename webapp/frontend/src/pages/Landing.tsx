export default function Landing() {
  return (
    <div className="relative flex min-h-[var(--app-viewport-height)] items-center justify-center overflow-hidden bg-[#f7f8fc] px-4 py-10">
      <div className="pointer-events-none absolute -left-16 -top-16 h-64 w-64 rounded-full bg-emerald-200/50 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 top-20 h-72 w-72 rounded-full bg-amber-200/50 blur-3xl" />
      <div className="pointer-events-none absolute bottom-0 left-1/2 h-56 w-[34rem] -translate-x-1/2 rounded-full bg-sky-200/45 blur-3xl" />

      <div className="relative w-full max-w-2xl rounded-[2rem] border border-white/70 bg-white/80 p-6 shadow-[0_20px_70px_rgba(15,23,42,0.12)] backdrop-blur md:p-10">
        <div className="mx-auto max-w-xl text-center">
          <p className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-4 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">
            Ish qidirish platformasi
          </p>

          <h1 className="mt-5 text-4xl font-black leading-tight text-slate-900 md:text-6xl">Bandlik.uz</h1>

          <p className="mt-4 text-sm leading-7 text-slate-600 md:text-lg">
            Eng dolzarb bo‘sh ish o‘rinlarini Telegram bot orqali tez va qulay toping.
            Barcha imkoniyatlar bot ichida bir joyda.
          </p>

          <a
            href="https://t.me/bandlikuzbot"
            target="_blank"
            rel="noopener noreferrer"
            className="tap-target mt-8 inline-flex w-full items-center justify-center rounded-2xl bg-slate-900 px-6 py-3.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-slate-800 md:w-auto md:text-base"
          >
            Telegram botga o‘tish
          </a>
        </div>
      </div>
    </div>
  );
}
