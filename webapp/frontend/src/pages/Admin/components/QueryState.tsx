import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";

import ErrorCard from "./ErrorCard";

export type QueryStateProps<T> = {
  query: UseQueryResult<T>;
  /** Height/shape of the pulse placeholder, e.g. "h-40". */
  skeletonClassName?: string;
  /** Rendered when the query succeeded but returned nothing useful. */
  empty?: ReactNode;
  children: (data: T) => ReactNode;
};

/**
 * Loading / error / data for one query, in one place.
 *
 * Every admin query used `retry: false` and rendered `null` on failure, so a
 * 403 or a 500 looked exactly like "no data yet". This makes all three states
 * visible.
 */
export default function QueryState<T>({
  query,
  skeletonClassName = "h-40",
  empty = null,
  children,
}: QueryStateProps<T>) {
  if (query.isPending) {
    return <div className={`animate-pulse rounded-2xl bg-surfaceAlt ${skeletonClassName}`} />;
  }
  if (query.isError) {
    return <ErrorCard error={query.error} onRetry={() => void query.refetch()} />;
  }
  if (query.data === undefined) return <>{empty}</>;
  return <>{children(query.data)}</>;
}
