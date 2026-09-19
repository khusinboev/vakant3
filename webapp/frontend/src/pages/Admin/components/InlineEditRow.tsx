import { useId, useState } from "react";
import { Pencil } from "lucide-react";

import { useT } from "../../../i18n/useT";

export type InlineEditRowProps = {
  label: string;
  value: string | number;
  type?: "text" | "number";
  /** Called with the trimmed draft when it differs from the current value. */
  onSave: (value: string) => void;
  saving?: boolean;
};

/**
 * A settings row that turns into an input when tapped.
 * Validation lives in the caller (SettingsTab) so this stays presentational.
 */
export default function InlineEditRow({
  label,
  value,
  type = "text",
  onSave,
  saving,
}: InlineEditRowProps) {
  const t = useT();
  const inputId = useId();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  const stop = () => {
    setEditing(false);
    setDraft("");
  };

  const commit = () => {
    const next = draft.trim();
    if (next && next !== String(value)) onSave(next);
    stop();
  };

  if (editing) {
    return (
      <div className="flex items-center justify-between py-2.5">
        <label className="mr-3 shrink-0 text-sm text-muted" htmlFor={inputId}>
          {label}
        </label>
        <input
          id={inputId}
          autoFocus
          type={type}
          inputMode={type === "number" ? "numeric" : "text"}
          className="w-32 rounded-xl border border-primary bg-primary/10 px-2.5 py-1 text-right text-sm font-medium text-text focus:outline-none focus:ring-1 focus:ring-primary"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Enter") commit();
            if (event.key === "Escape") stop();
          }}
          disabled={saving}
        />
      </div>
    );
  }

  return (
    <button
      type="button"
      aria-label={t("admin.edit.aria", { label })}
      className="flex w-full items-center justify-between py-2.5 text-left"
      onClick={() => {
        setDraft(String(value));
        setEditing(true);
      }}
    >
      <span className="text-sm text-text">{label}</span>
      <span className="flex items-center gap-1.5 text-sm font-semibold text-primary">
        {String(value)}
        <Pencil size={11} className="text-muted" aria-hidden="true" />
      </span>
    </button>
  );
}
