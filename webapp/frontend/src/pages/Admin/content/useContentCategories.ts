import { useQuery } from "@tanstack/react-query";

import { adminKeys } from "../../../api/admin";
import { listContentCategories } from "../../../api/admin";
import type { ContentCategory } from "../../../api/adminTypes";

export type UseContentCategoriesResult = {
  categories: ContentCategory[];
  isLoading: boolean;
  error: unknown;
  refetch: () => void;
};

/** Shared by ArticlesTab (select + name lookup) and CategoriesTab. */
export function useContentCategories(): UseContentCategoriesResult {
  const query = useQuery({
    queryKey: adminKeys.contentCategories(),
    queryFn: listContentCategories,
    retry: false,
  });
  return {
    categories: query.data?.items ?? [],
    isLoading: query.isLoading,
    error: query.isError ? query.error : null,
    refetch: () => void query.refetch(),
  };
}

export default useContentCategories;
