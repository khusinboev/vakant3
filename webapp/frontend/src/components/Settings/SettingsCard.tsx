import { Check, ChevronRight, Languages, Palette, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import useTheme from "../../hooks/useTheme";
import useToast from "../../hooks/useToast";
import { useT } from "../../i18n/useT";
import type { TranslationKey } from "../../i18n";
import { ROLE_LABEL_KEY, useAdminRole } from "../../pages/Admin/hooks/useAdminRole";
import { LANGS, LANG_META, useLangStore, type Lang } from "../../store/lang";
import { THEME_MODES, type ThemeMode } from "../../store/theme";

const THEME_LABEL: Record<ThemeMode, TranslationKey> = {
  telegram: "settings.theme.telegram",
  light: "settings.theme.light",
  dark: "settings.theme.dark",
  system: "settings.theme.system",
};

/**
 * Language selector + theme segmented control.
 * Rendered on the Profile page; self-contained, no props.
 */
export default function SettingsCard() {
  const t = useT();
  const toast = useToast();
  const lang = useLangStore((s) => s.lang);
  const setLang = useLangStore((s) => s.setLang);
  const { mode, setMode } = useTheme();
  // Shown only to actual admins — the role comes from `/auth/gate`.
  const { role } = useAdminRole();

  const pickLang = (next: Lang) => {
    if (next === lang) return;
    setLang(next);
    toast.success(t("settings.langSaved"));
  };

  return (
    <section className="card p-4">
      <h3 className="text-sm font-semibold text-text">{t("settings.title")}</h3>

      {/* Language */}
      <div className="mt-3">
        <div className="mb-2 flex items-center gap-2">
          <Languages size={14} className="text-muted" />
          <p className="text-xs font-medium text-muted">{t("settings.language")}</p>
        </div>
        <div role="radiogroup" aria-label={t("settings.language")} className="space-y-1.5">
          {LANGS.map((code) => {
            const active = code === lang;
            return (
              <button
                type="button"
                key={code}
                role="radio"
                aria-checked={active}
                onClick={() => pickLang(code)}
                className={`tap-target flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-sm transition-colors ${
                  active
                    ? "border-primary bg-primary/10 font-semibold text-primary"
                    : "border-border bg-surface text-text"
                }`}
              >
                <span className="text-base leading-none">{LANG_META[code].flag}</span>
                <span className="flex-1 text-left">{LANG_META[code].native}</span>
                {active && <Check size={16} />}
              </button>
            );
          })}
        </div>
      </div>

      {/* Theme */}
      <div className="mt-4">
        <div className="mb-2 flex items-center gap-2">
          <Palette size={14} className="text-muted" />
          <p className="text-xs font-medium text-muted">{t("settings.theme")}</p>
        </div>
        <div
          role="radiogroup"
          aria-label={t("settings.theme")}
          className="grid grid-cols-4 gap-1 rounded-xl border border-border bg-surfaceAlt p-1"
        >
          {THEME_MODES.map((option) => {
            const active = option === mode;
            return (
              <button
                type="button"
                key={option}
                role="radio"
                aria-checked={active}
                onClick={() => setMode(option)}
                className={`rounded-lg px-2 py-2 text-[11px] font-semibold transition-colors ${
                  active ? "bg-primary text-primaryFg" : "text-muted"
                }`}
              >
                {t(THEME_LABEL[option])}
              </button>
            );
          })}
        </div>
      </div>

      {/* Admin panel — only rendered when the gate reports a role. */}
      {role && (
        <Link
          to="/admin"
          aria-label={t("admin.shell.openPanel")}
          className="tap-target mt-4 flex w-full items-center gap-3 rounded-xl border border-primary/40 bg-primary/10 px-3 py-2.5 text-sm font-semibold text-primary"
        >
          <ShieldCheck size={16} aria-hidden="true" />
          <span className="flex-1 text-left">{t("nav.admin")}</span>
          <span className="text-[11px] font-medium opacity-80">{t(ROLE_LABEL_KEY[role])}</span>
          <ChevronRight size={16} aria-hidden="true" />
        </Link>
      )}
    </section>
  );
}
