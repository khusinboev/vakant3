import { Moon, ShieldCheck, Sun, SunMoon } from "lucide-react";

import useTheme from "../../../hooks/useTheme";
import { useT } from "../../../i18n/useT";
import { LANGS, useLangStore, type Lang } from "../../../store/lang";
import type { ThemeMode } from "../../../store/theme";
import { ROLE_LABEL_KEY, type AdminRole } from "../hooks/useAdminRole";

const LANG_SHORT: Record<Lang, string> = { uz: "UZ", ru: "RU", en: "EN" };

/** telegram -> light -> dark -> system -> telegram */
const THEME_CYCLE: ThemeMode[] = ["telegram", "light", "dark", "system"];
const THEME_ICON: Record<ThemeMode, typeof Sun> = {
  telegram: SunMoon,
  system: SunMoon,
  light: Sun,
  dark: Moon,
};

export type AdminHeaderProps = {
  /** Already translated page title. */
  title: string;
  role: AdminRole | null;
};

/**
 * Panel header: page title, the actor's role, and quick language/theme
 * switches. Both switches drive the app-wide stores (`store/lang`,
 * `store/theme`), so a change here is the same change as in Profile settings.
 */
export default function AdminHeader({ title, role }: AdminHeaderProps) {
  const t = useT();
  const lang = useLangStore((s) => s.lang);
  const setLang = useLangStore((s) => s.setLang);
  const { mode, setMode } = useTheme();
  const ThemeIcon = THEME_ICON[mode];

  return (
    <header className="flex items-center gap-2 border-b border-border bg-surface px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">
          {t("admin.title")}
        </p>
        <h1 className="truncate font-display text-lg font-extrabold leading-tight text-text">
          {title}
        </h1>
      </div>

      {role && (
        <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-[11px] font-semibold text-primary">
          <ShieldCheck size={12} aria-hidden="true" />
          {t(ROLE_LABEL_KEY[role])}
        </span>
      )}

      <div
        role="radiogroup"
        aria-label={t("admin.shell.langToggle")}
        className="flex shrink-0 items-center rounded-xl border border-border bg-surfaceAlt p-0.5"
      >
        {LANGS.map((code) => (
          <button
            key={code}
            type="button"
            role="radio"
            aria-checked={code === lang}
            onClick={() => setLang(code)}
            className={`rounded-lg px-1.5 py-1 text-[10px] font-bold transition-colors ${
              code === lang ? "bg-primary text-primaryFg" : "text-muted"
            }`}
          >
            {LANG_SHORT[code]}
          </button>
        ))}
      </div>

      <button
        type="button"
        aria-label={t("admin.shell.themeToggle")}
        onClick={() => setMode(THEME_CYCLE[(THEME_CYCLE.indexOf(mode) + 1) % THEME_CYCLE.length])}
        className="tap-target shrink-0 rounded-xl border border-border bg-surfaceAlt p-2 text-muted"
      >
        <ThemeIcon size={15} aria-hidden="true" />
      </button>
    </header>
  );
}
