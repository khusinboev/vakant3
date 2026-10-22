export type SkeletonProps = {
  /** Text placeholder lines (11–13px each). */
  lines?: number;
  /** List/table row placeholders (40px each). Wins over `lines`. */
  rows?: number;
  /** A single block of this Tailwind height, e.g. "h-24". */
  height?: string;
  className?: string;
};

/** The only pulse placeholder in the panel — no inline `animate-pulse`. */
export default function Skeleton({ lines, rows, height, className = "" }: SkeletonProps) {
  if (rows) {
    return (
      <div className={`space-y-1.5 ${className}`} aria-busy="true" aria-live="polite">
        {Array.from({ length: rows }, (_, index) => (
          <div key={index} className="h-10 animate-pulse rounded-xl bg-surfaceAlt" />
        ))}
      </div>
    );
  }

  if (lines) {
    return (
      <div className={`space-y-1.5 ${className}`} aria-busy="true" aria-live="polite">
        {Array.from({ length: lines }, (_, index) => (
          <div
            key={index}
            className="h-3 animate-pulse rounded-lg bg-surfaceAlt"
            style={{ width: index === lines - 1 ? "60%" : "100%" }}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      aria-busy="true"
      className={`animate-pulse rounded-xl bg-surfaceAlt ${height ?? "h-16"} ${className}`}
    />
  );
}
