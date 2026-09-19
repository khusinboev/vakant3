import { useRef, useState } from "react";
import { X } from "lucide-react";

import { useT } from "../../i18n/useT";

export type TagInputProps = {
  tags: string[];
  onAdd: (tag: string) => void;
  onRemove: (index: number) => void;
  /** Shown while the list is empty. */
  placeholder: string;
};

/**
 * Chip list with a free-text input: Enter or a comma commits, Backspace on an
 * empty input removes the last chip. Duplicates are ignored.
 */
export default function TagInput({ tags, onAdd, onRemove, placeholder }: TagInputProps) {
  const t = useT();
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const commit = (raw: string) => {
    const tag = raw.trim().replace(/,+$/, "").trim();
    if (tag && !tags.some((item) => item.toLowerCase() === tag.toLowerCase())) onAdd(tag);
    setValue("");
  };

  return (
    <div
      className="flex min-h-[48px] cursor-text flex-wrap gap-1.5 rounded-xl border border-border bg-surface p-2 transition-all focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/40"
      onClick={() => inputRef.current?.focus()}
    >
      {tags.map((tag, index) => (
        <span
          key={`${tag}-${index}`}
          className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary"
        >
          {tag}
          <button
            type="button"
            aria-label={t("resume.tag.remove", { tag })}
            className="leading-none text-primary/70 transition-colors hover:text-danger"
            onClick={(event) => {
              event.stopPropagation();
              onRemove(index);
            }}
          >
            <X size={10} />
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        className="min-w-[80px] flex-1 bg-transparent py-0.5 text-sm text-text outline-none placeholder:text-muted/70"
        placeholder={tags.length === 0 ? placeholder : t("resume.tag.add")}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === ",") {
            event.preventDefault();
            commit(value);
          }
          if (event.key === "Backspace" && !value && tags.length > 0) onRemove(tags.length - 1);
        }}
        onBlur={() => {
          if (value.trim()) commit(value);
        }}
      />
    </div>
  );
}
