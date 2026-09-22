import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { useQueryState } from "../hooks/useQueryState";

export type AccordionItem = {
  id: string;
  titleKey?: TranslationKey;
  title?: string;
  /** Right-aligned one-liner shown while the section is closed. */
  summary?: ReactNode;
  content: ReactNode;
};

export type AccordionProps = {
  items: AccordionItem[];
  /** Only one section open at a time. Default `true`. */
  single?: boolean;
  /** Section id(s) open on first render. */
  defaultOpen?: string | string[];
  /** Keeps the open section in the URL (`?section=…`), so back closes it. */
  queryKey?: string;
  className?: string;
};

function asArray(value: string | string[] | undefined): string[] {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

/**
 * Collapsible sections — the spec's answer to long forms and tall charts.
 *
 *   <Accordion queryKey="section" defaultOpen="autopost" items={[…]} />
 */
export default function Accordion({
  items,
  single = true,
  defaultOpen,
  queryKey,
  className = "",
}: AccordionProps) {
  const t = useT();
  const fallback = asArray(defaultOpen);
  const [urlValue, setUrlValue] = useQueryState(queryKey ?? "section", fallback.join(","));
  const [localValue, setLocalValue] = useState<string[]>(fallback);

  const open = queryKey ? urlValue.split(",").filter(Boolean) : localValue;

  const setOpen = (next: string[]) => {
    if (queryKey) setUrlValue(next.join(","));
    else setLocalValue(next);
  };

  const toggle = (id: string) => {
    const isOpen = open.includes(id);
    if (single) setOpen(isOpen ? [] : [id]);
    else setOpen(isOpen ? open.filter((entry) => entry !== id) : [...open, id]);
  };

  return (
    <div className={`divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface ${className}`}>
      {items.map((item) => {
        const isOpen = open.includes(item.id);
        const title = item.titleKey ? t(item.titleKey) : (item.title ?? "");
        return (
          <section key={item.id}>
            <h3>
              <button
                type="button"
                onClick={() => toggle(item.id)}
                aria-expanded={isOpen}
                aria-controls={`acc-${item.id}`}
                className="flex min-h-[40px] w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-surfaceAlt"
              >
                <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-text">
                  {title}
                </span>
                {!isOpen && item.summary && (
                  <span className="min-w-0 shrink truncate text-[11px] text-muted">
                    {item.summary}
                  </span>
                )}
                <ChevronDown
                  size={14}
                  aria-hidden="true"
                  className={`shrink-0 text-muted transition-transform ${isOpen ? "rotate-180" : ""}`}
                />
              </button>
            </h3>
            {isOpen && (
              <div id={`acc-${item.id}`} className="border-t border-border px-3 py-2">
                {item.content}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
