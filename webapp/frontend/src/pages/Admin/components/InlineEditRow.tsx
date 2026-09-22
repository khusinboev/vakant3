import { useId, useState } from "react";
import { Pencil } from "lucide-react";

import { useT } from "../../../i18n/useT";
import { Chip } from "../ui";

export type InlineEditRowProps = {
  label: string;
  value: string | number;
  type?: "text" | "number";
  /** Called with the trimmed draft when it differs from the current value. */
  onSave: (value: string) => void;
  saving?: boolean;
};

/**
 * A dense (40px) settings row: label left, value right as a tappable `Chip`.
 * Tapping it opens an inline input; it saves automatically on blur/Enter
 * (spec §4: "saqlash avtomatik (blur)"), Escape cancels. Validation lives in
 * the caller (SettingsTab), which stays presentational.
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
      <div className="flex min-h-[40px] items-center justify-between gap-2">
        <label className="min-w-0 shrink-0 text-[13px] text-muted" htmlFor={inputId}>
          {label}
        </label>
        <input
          id={inputId}
          autoFocus
          type={type}
          inputMode={type === "number" ? "decimal" : "text"}
          className="w-24 min-w-0 rounded-lg border border-primary bg-primary/10 px-2 py-1 text-right text-[13px] font-semibold tabular-nums text-text focus:outline-none focus:ring-1 focus:ring-primary"
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
    <div className="flex min-h-[40px] items-center justify-between gap-2">
      <span className="min-w-0 truncate text-[13px] text-text">{label}</span>
      <button
        type="button"
        aria-label={t("admin.settings.editAria", { label })}
        disabled={saving}
        onClick={() => {
          setDraft(String(value));
          setEditing(true);
        }}
        className="shrink-0 rounded-full disabled:opacity-60"
      >
        <Chip tone="primary" icon={Pencil} label={String(value)} className="tabular-nums" />
      </button>
    </div>
  );
}
