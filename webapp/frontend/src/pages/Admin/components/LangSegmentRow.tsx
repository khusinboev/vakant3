import { LANG_META, LANGS, type Lang } from "../../../store/lang";

export type LangSegmentRowProps = {
  label: string;
  value: Lang;
  disabled?: boolean;
  onChange: (lang: Lang) => void;
};

/**
 * Language picker for a single setting (currently `channel_lang`).
 * A radio group rather than a `<select>` so the three options stay tappable
 * and the active one is visible without opening anything.
 */
export default function LangSegmentRow({
  label,
  value,
  disabled,
  onChange,
}: LangSegmentRowProps) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5">
      <span id="admin-channel-lang-label" className="shrink-0 text-sm text-text">
        {label}
      </span>
      <div
        role="radiogroup"
        aria-labelledby="admin-channel-lang-label"
        className="flex shrink-0 gap-1 rounded-xl bg-surfaceAlt p-0.5"
      >
        {LANGS.map((lang) => {
          const active = lang === value;
          return (
            <button
              key={lang}
              type="button"
              role="radio"
              aria-checked={active}
              aria-label={LANG_META[lang].native}
              disabled={disabled}
              onClick={() => !active && onChange(lang)}
              className={`rounded-lg px-2.5 py-1 text-xs font-semibold uppercase transition-colors ${
                active ? "bg-primary text-primaryFg" : "text-muted"
              }`}
            >
              {lang}
            </button>
          );
        })}
      </div>
    </div>
  );
}
