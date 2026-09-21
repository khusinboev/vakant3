import { LANG_META, LANGS, type Lang } from "../../../store/lang";
import { useT } from "../../../i18n/useT";

export type LangTabsProps = {
  value: Lang;
  onChange: (lang: Lang) => void;
  /** Non-empty per language -> a small green dot on that tab. */
  filled?: Partial<Record<Lang, boolean>>;
  /** A field problem in that language -> a small red dot (wins over `filled`). */
  invalid?: Partial<Record<Lang, boolean>>;
  /** Shown next to the tabs while `value !== "uz"`; copies every field's uz text over. */
  onCopyFromUz?: () => void;
};

/** The one language switcher for the content editor: title/summary/full_text/etc. all follow it. */
export default function LangTabs({ value, onChange, filled, invalid, onCopyFromUz }: LangTabsProps) {
  const t = useT();
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div
        role="tablist"
        aria-label={t("adminContent.editor.langTabs")}
        className="flex gap-1 rounded-xl bg-surfaceAlt p-1"
      >
        {LANGS.map((lang) => {
          const active = lang === value;
          const isInvalid = Boolean(invalid?.[lang]);
          const isFilled = Boolean(filled?.[lang]);
          return (
            <button
              key={lang}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onChange(lang)}
              className={`relative rounded-lg px-3 py-1.5 text-xs font-semibold uppercase transition-colors ${
                active ? "bg-primary text-primaryFg" : "text-muted hover:text-text"
              }`}
            >
              {LANG_META[lang].native}
              {(isInvalid || isFilled) && (
                <span
                  aria-hidden="true"
                  className={`absolute right-0.5 top-0.5 h-1.5 w-1.5 rounded-full ${
                    isInvalid ? "bg-danger" : "bg-success"
                  }`}
                />
              )}
            </button>
          );
        })}
      </div>
      {onCopyFromUz && value !== "uz" && (
        <button
          type="button"
          onClick={onCopyFromUz}
          className="tap-target rounded-xl border border-border bg-surface px-2.5 py-1.5 text-xs font-semibold text-muted transition-colors hover:text-text"
        >
          {t("adminContent.editor.copyFromUz")}
        </button>
      )}
    </div>
  );
}
