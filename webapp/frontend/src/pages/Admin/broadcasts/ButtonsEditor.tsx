import { Plus, X } from "lucide-react";

import type { BroadcastButton } from "../../../api/adminTypes";
import { useT } from "../../../i18n/useT";
import { INPUT_CLS } from "../../../components/ui/Field";
import { MAX_BUTTONS, isAllowedButtonUrl } from "./telegramHtml";

export type ButtonsEditorProps = {
  value: BroadcastButton[];
  onChange: (value: BroadcastButton[]) => void;
};

/** Inline keyboard rows of one button each — `validate_buttons` allows 6 max. */
export default function ButtonsEditor({ value, onChange }: ButtonsEditorProps) {
  const t = useT();

  const patch = (index: number, field: keyof BroadcastButton, next: string) => {
    onChange(value.map((row, i) => (i === index ? { ...row, [field]: next } : row)));
  };

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-muted">{t("adminBroadcasts.buttons.label")}</p>

      {value.map((row, index) => {
        const urlInvalid = row.url.trim() !== "" && !isAllowedButtonUrl(row.url);
        const textInvalid = row.url.trim() !== "" && row.text.trim() === "";
        return (
          <div key={index} className="rounded-xl border border-border bg-surface p-2.5">
            <div className="flex items-start gap-2">
              <div className="grid min-w-0 flex-1 gap-2 sm:grid-cols-2">
                <input
                  value={row.text}
                  onChange={(event) => patch(index, "text", event.target.value)}
                  placeholder={t("adminBroadcasts.buttons.text")}
                  aria-label={t("adminBroadcasts.buttons.text")}
                  aria-invalid={textInvalid}
                  className={INPUT_CLS}
                />
                <input
                  value={row.url}
                  onChange={(event) => patch(index, "url", event.target.value)}
                  placeholder="https://"
                  inputMode="url"
                  aria-label={t("adminBroadcasts.buttons.url")}
                  aria-invalid={urlInvalid}
                  className={INPUT_CLS}
                />
              </div>
              <button
                type="button"
                onClick={() => onChange(value.filter((_, i) => i !== index))}
                aria-label={t("adminBroadcasts.buttons.remove", { index: index + 1 })}
                className="mt-1 rounded-lg p-1.5 text-muted hover:bg-surfaceAlt hover:text-danger focus:outline-none focus:ring-2 focus:ring-primary/40"
              >
                <X size={15} aria-hidden="true" />
              </button>
            </div>
            {textInvalid && (
              <p role="alert" className="mt-1.5 text-xs text-danger">
                {t("adminBroadcasts.buttons.textRequired")}
              </p>
            )}
            {urlInvalid && (
              <p role="alert" className="mt-1.5 text-xs text-danger">
                {t("adminBroadcasts.buttons.invalidUrl")}
              </p>
            )}
          </div>
        );
      })}

      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          disabled={value.length >= MAX_BUTTONS}
          onClick={() => onChange([...value, { text: "", url: "" }])}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium text-text hover:bg-surfaceAlt focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50"
        >
          <Plus size={14} aria-hidden="true" /> {t("adminBroadcasts.buttons.add")}
        </button>
        <span className="text-xs text-muted">{t("adminBroadcasts.buttons.hint")}</span>
      </div>
    </div>
  );
}
