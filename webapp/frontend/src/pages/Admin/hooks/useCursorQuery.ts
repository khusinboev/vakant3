import { useMemo } from "react";
import { useInfiniteQuery, type QueryKey } from "@tanstack/react-query";

import type { CursorPage } from "../../../api/adminTypes";

/** The cursor page shape every admin list endpoint returns (CONTRACT_P12). */
export type { CursorPage };

export type CursorQueryOptions = {
  enabled?: boolean;
  staleTime?: number;
  refetchInterval?: number | false;
};

export type CursorQueryResult<T> = {
  items: T[];
  hasMore: boolean;
  loadMore: () => void;
  isLoading: boolean;
  isFetchingMore: boolean;
  error: unknown;
  refetch: () => void;
  /** Server-reported total for the whole filtered set, when it sends one. */
  total: number | null;
};

/**
 * `useInfiniteQuery` bound to the admin cursor convention.
 *
 *   const users = useCursorQuery(["admin","users",filters],
 *     (cursor) => listUsers({ ...filters, cursor }));
 *   <DataTable rows={users.items} hasMore={users.hasMore} onLoadMore={users.loadMore} … />
 *
 * `retry: false` matches the rest of the admin queries: a 403 must surface,
 * not be hammered.
 */
export function useCursorQuery<T>(
  key: QueryKey,
  fetcher: (cursor: string | null) => Promise<CursorPage<T>>,
  options: CursorQueryOptions = {},
): CursorQueryResult<T> {
  const query = useInfiniteQuery<CursorPage<T>>({
    queryKey: key,
    queryFn: ({ pageParam }) => fetcher((pageParam as string | null) ?? null),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    retry: false,
    enabled: options.enabled,
    staleTime: options.staleTime,
    refetchInterval: options.refetchInterval,
  });

  const pages = query.data?.pages;
  const items = useMemo(() => (pages ?? []).flatMap((page) => page.items), [pages]);
  const fetchNextPage = query.fetchNextPage;
  const refetch = query.refetch;

  return {
    items,
    hasMore: Boolean(query.hasNextPage),
    loadMore: () => void fetchNextPage(),
    isLoading: query.isLoading,
    isFetchingMore: query.isFetchingNextPage,
    error: query.isError ? query.error : null,
    refetch: () => void refetch(),
    total: pages?.[0]?.total ?? null,
  };
}

export default useCursorQuery;
