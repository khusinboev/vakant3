import { Plus, X } from "lucide-react";

import type { BroadcastButton } from "../../../api/adminTypes";
import { useT } from "../../../i18n/useT";
import { Button, IconButton } from "../ui";
import { FIELD_CLS } from "./labels";
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
      {value.map((row, index) => {
        const urlInvalid = row.url.trim() !== "" && !isAllowedButtonUrl(row.url);
        const textInvalid = row.url.trim() !== "" && row.text.trim() === "";
        return (
          <div
            key={index}
            className="space-y-1.5 border-t border-border pt-2 first:border-t-0 first:pt-0"
          >
            <div className="flex items-center gap-1.5">
              <input
                value={row.text}
                onChange={(event) => patch(index, "text", event.target.value)}
                placeholder={t("adminBroadcasts.buttons.text")}
                aria-label={t("adminBroadcasts.buttons.text")}
                aria-invalid={textInvalid}
                className={FIELD_CLS}
              />
              <IconButton
                icon={X}
                variant="ghost"
                ariaLabel={t("adminBroadcasts.buttons.remove", { index: index + 1 })}
                onClick={() => onChange(value.filter((_, i) => i !== index))}
              />
            </div>
            <input
              value={row.url}
              onChange={(event) => patch(index, "url", event.target.value)}
              placeholder="https://"
              inputMode="url"
              aria-label={t("adminBroadcasts.buttons.url")}
              aria-invalid={urlInvalid}
              className={FIELD_CLS}
            />
            {textInvalid && (
              <p role="alert" className="text-[11px] text-danger">
                {t("adminBroadcasts.buttons.textRequired")}
              </p>
            )}
            {urlInvalid && (
              <p role="alert" className="text-[11px] text-danger">
                {t("adminBroadcasts.buttons.invalidUrl")}
              </p>
            )}
          </div>
        );
      })}

      <div className="flex items-center justify-between gap-2">
        <Button
          size="sm"
          variant="secondary"
          icon={Plus}
          labelKey="adminBroadcasts.buttons.add"
          disabled={value.length >= MAX_BUTTONS}
          onClick={() => onChange([...value, { text: "", url: "" }])}
        />
        <span className="text-[11px] text-muted">{t("adminBroadcasts.buttons.hint")}</span>
      </div>
    </div>
  );
}
