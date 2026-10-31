import { useId, type ReactNode } from "react";
import { AlertCircle } from "lucide-react";

/** Shared input/select/textarea skin — semantic tokens, theme-aware. */
export const INPUT_CLS =
  "w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm text-text " +
  "placeholder:text-muted/70 focus:outline-none focus:ring-2 focus:ring-primary/40 " +
  "focus:border-primary transition-all";

export type FieldProps = {
  label: string;
  required?: boolean;
  /** Small grey addition after the label, e.g. "(optional)". */
  hint?: string;
  /** Validation message; also marks the control as invalid for screen readers. */
  error?: string;
  children: ReactNode;
};

/**
 * Labelled form field with an optional hint and error line.
 *
 *   <Field label={t("resume.field.email")} error={errors.email}>
 *     <input className={INPUT_CLS} … />
 *   </Field>
 */
export default function Field({ label, required, hint, error, children }: FieldProps) {
  const errorId = useId();

  return (
    <div className="space-y-1.5">
      <label className="flex items-baseline gap-1 text-xs font-semibold text-muted">
        {label}
        {required && <span className="text-danger">*</span>}
        {hint && <span className="ml-1 font-normal text-muted/80">{hint}</span>}
      </label>
      {children}
      {error && (
        <p id={errorId} role="alert" className="flex items-center gap-1 text-xs text-danger">
          <AlertCircle size={11} className="shrink-0" /> {error}
        </p>
      )}
    </div>
  );
}
