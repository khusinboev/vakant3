import { useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";

export type SearchBarProps = {
  value: string;
  onChange: (value: string) => void;
  placeholderKey?: TranslationKey;
  /** Milliseconds before `onChange` fires. 0 disables the debounce. */
  debounceMs?: number;
  autoFocus?: boolean;
  className?: string;
};

/**
 * 36px search input with a debounce and a clear button.
 * Pair it with `useQueryState(key, "", { replace: true })` so typing does not
 * fill the history stack.
 */
export default function SearchBar({
  value,
  onChange,
  placeholderKey = "admin.filter.searchPlaceholder",
  debounceMs = 300,
  autoFocus = false,
  className = "",
}: SearchBarProps) {
  const t = useT();
  const [draft, setDraft] = useState(value);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  // Outside changes (a cleared filter, a restored URL) win over the draft.
  useEffect(() => {
    setDraft(value);
  }, [value]);

  useEffect(() => {
    if (draft === value) return;
    if (debounceMs <= 0) {
      onChangeRef.current(draft);
      return;
    }
    const timer = setTimeout(() => onChangeRef.current(draft), debounceMs);
    return () => clearTimeout(timer);
    // `value` is deliberately excluded: it would restart the timer mid-typing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, debounceMs]);

  const placeholder = t(placeholderKey);

  return (
    <div className={`relative ${className}`}>
      <Search
        size={14}
        aria-hidden="true"
        className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted"
      />
      <input
        type="search"
        value={draft}
        autoFocus={autoFocus}
        onChange={(event) => setDraft(event.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="h-9 w-full rounded-xl border border-border bg-surface pl-8 pr-8 text-[13px] text-text placeholder:text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      />
      {draft && (
        <button
          type="button"
          onClick={() => setDraft("")}
          aria-label={t("admin.search.clear")}
          className="absolute right-1.5 top-1/2 inline-flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full text-muted hover:bg-surfaceAlt hover:text-text"
        >
          <X size={13} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
