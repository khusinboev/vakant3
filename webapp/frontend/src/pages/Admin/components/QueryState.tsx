import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";

import Skeleton from "../ui/Skeleton";
import ErrorCard from "./ErrorCard";

export type QueryStateProps<T> = {
  query: UseQueryResult<T>;
  /** Height of the pulse placeholder, e.g. "h-24". */
  skeletonClassName?: string;
  /** Rendered when the query succeeded but returned nothing useful. */
  empty?: ReactNode;
  children: (data: T) => ReactNode;
};

/** Loading / error / data for one query, in one place. */
export default function QueryState<T>({
  query,
  skeletonClassName = "h-24",
  empty = null,
  children,
}: QueryStateProps<T>) {
  if (query.isPending) return <Skeleton height={skeletonClassName} />;
  if (query.isError) {
    return <ErrorCard error={query.error} onRetry={() => void query.refetch()} />;
  }
  if (query.data === undefined) return <>{empty}</>;
  return <>{children(query.data)}</>;
}
