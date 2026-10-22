export type SparklineProps = {
  /** Daily values, oldest first. */
  points: number[];
  ariaLabel: string;
  className?: string;
};

const WIDTH = 280;
const HEIGHT = 40;
const PAD = 3;

/**
 * A dependency-free 7-day trend line (spec §4: "recharts'siz — SVG"). Kept
 * tiny on purpose — this is the dashboard's only chart and it must not pull
 * in the ~300 KB charting library that `analytics/Charts.tsx` uses.
 */
export default function Sparkline({ points, ariaLabel, className = "" }: SparklineProps) {
  if (points.length === 0) {
    return <div className={`h-10 w-full ${className}`} aria-hidden="true" />;
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const stepX = points.length > 1 ? (WIDTH - PAD * 2) / (points.length - 1) : 0;

  const coords = points.map((value, index) => {
    const x = PAD + index * stepX;
    const y = HEIGHT - PAD - ((value - min) / span) * (HEIGHT - PAD * 2);
    return [x, y] as const;
  });

  const linePath = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L${coords[coords.length - 1][0].toFixed(1)},${HEIGHT} L${coords[0][0].toFixed(1)},${HEIGHT} Z`;
  const [lastX, lastY] = coords[coords.length - 1];

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className={`h-10 w-full text-primary ${className}`}
      role="img"
      aria-label={ariaLabel}
      preserveAspectRatio="none"
    >
      <path d={areaPath} fill="currentColor" opacity={0.12} stroke="none" />
      <path d={linePath} fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lastX} cy={lastY} r={2.5} fill="currentColor" />
    </svg>
  );
}
