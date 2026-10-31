import { botDeepLink } from "../lib/constants";
import { useT } from "../i18n/useT";

export default function Landing() {
  const t = useT();

  return (
    <div className="relative flex min-h-[var(--app-viewport-height)] items-center justify-center overflow-hidden bg-bg px-4 py-10">
      <div className="pointer-events-none absolute -left-16 -top-16 h-64 w-64 rounded-full bg-primary/20 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 top-20 h-72 w-72 rounded-full bg-warning/20 blur-3xl" />
      <div className="pointer-events-none absolute bottom-0 left-1/2 h-56 w-[34rem] -translate-x-1/2 rounded-full bg-primary/10 blur-3xl" />

      <div className="relative w-full max-w-2xl rounded-[2rem] border border-border bg-surface/80 p-6 shadow-[0_20px_70px_rgba(15,23,42,0.12)] backdrop-blur md:p-10">
        <div className="mx-auto max-w-xl text-center">
          <p className="inline-flex rounded-full border border-primary/30 bg-primary/10 px-4 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-primary">
            {t("landing.badge")}
          </p>

          <h1 className="mt-5 text-4xl font-black leading-tight text-text md:text-6xl">
            {t("app.name")}
          </h1>

          <p className="mt-4 text-sm leading-7 text-muted md:text-lg">{t("landing.body")}</p>

          <a
            href={botDeepLink()}
            target="_blank"
            rel="noopener noreferrer"
            className="tap-target mt-8 inline-flex w-full items-center justify-center rounded-2xl bg-primary px-6 py-3.5 text-sm font-semibold text-primaryFg transition hover:-translate-y-0.5 md:w-auto md:text-base"
          >
            {t("landing.cta")}
          </a>
        </div>
      </div>
    </div>
  );
}
