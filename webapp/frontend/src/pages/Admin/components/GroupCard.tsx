import type { ElementType, ReactNode } from "react";

export type GroupAccent = "primary" | "success" | "warning" | "danger";

const ACCENTS: Record<GroupAccent, string> = {
  primary: "bg-primary/10 text-primary",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  danger: "bg-danger/10 text-danger",
};

export type GroupCardProps = {
  icon: ElementType;
  title: string;
  accent?: GroupAccent;
  /** Rows are separated by hairlines; pass `false` for free-form bodies. */
  divide?: boolean;
  children: ReactNode;
};

/** A titled settings/section card. */
export default function GroupCard({
  icon: Icon,
  title,
  accent = "primary",
  divide = true,
  children,
}: GroupCardProps) {
  return (
    <section className="card overflow-hidden">
      <header className="flex items-center gap-2.5 border-b border-border px-4 py-3">
        <span className={`flex h-7 w-7 items-center justify-center rounded-full ${ACCENTS[accent]}`}>
          <Icon size={14} aria-hidden="true" />
        </span>
        <h2 className="text-sm font-semibold text-text">{title}</h2>
      </header>
      <div className={`px-4 ${divide ? "divide-y divide-border" : ""}`}>{children}</div>
    </section>
  );
}
