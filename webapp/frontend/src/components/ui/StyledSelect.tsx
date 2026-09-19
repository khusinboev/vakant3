import type { ChangeEvent, ReactNode } from "react";
import { ChevronDown } from "lucide-react";

export type StyledSelectProps = {
  value: string;
  onChange: (event: ChangeEvent<HTMLSelectElement>) => void;
  children: ReactNode;
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
};

/** A native `<select>` with the app's input skin and a chevron affordance. */
export default function StyledSelect({
  value,
  onChange,
  children,
  disabled,
  className = "",
  "aria-label": ariaLabel,
}: StyledSelectProps) {
  return (
    <div className="relative">
      <select
        aria-label={ariaLabel}
        className={`w-full appearance-none rounded-xl border border-border bg-surface px-3 py-2.5 pr-8 text-sm text-text transition-all focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40 ${
          disabled ? "cursor-not-allowed bg-surfaceAlt opacity-50" : ""
        } ${className}`}
        value={value}
        onChange={onChange}
        disabled={disabled}
      >
        {children}
      </select>
      <ChevronDown
        size={14}
        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted"
      />
    </div>
  );
}
