import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";

import { useT } from "../../../i18n/useT";
import ErrorCard from "../components/ErrorCard";
import { useAdminHeader } from "../hooks/useAdminHeader";
import { useQueryState } from "../hooks/useQueryState";
import EmptyState from "../ui/EmptyState";
import { FilterChips, useAdminFilters, type FilterDef } from "../ui/Filters";
import { List, ListRow } from "../ui/List";
import SearchBar from "../ui/SearchBar";
import Skeleton from "../ui/Skeleton";
import { StatusChip } from "../ui/Chip";
import Tabs from "../ui/Tabs";
import { CONTENT_CONFIG, CONTENT_KINDS, contentPath, type ContentKind, type ContentRecord } from "./kinds";
import { useContentCategories } from "./useContentCategories";

function recordTitle(record: ContentRecord, titleField: "title" | "name"): string {
  const text = titleField === "name" ? record.name : record.title;
  return text?.uz?.trim() || record.id;
}

/**
 * `/admin/content/:kind` — one list for all three kinds. The kind lives in the
 * URL (the `Tabs` navigate, they do not hold state), search and filters live
 * in the query string, so back undoes each of them one step at a time.
 */
export default function ContentList({ kind }: { kind: ContentKind }) {
  const t = useT();
  const navigate = useNavigate();
  const config = CONTENT_CONFIG[kind];
  const { categories } = useContentCategories();

  const [search, setSearch] = useQueryState<string>("q", "", { replace: true });

  const filterDefs = useMemo<FilterDef[]>(() => {
    const defs: FilterDef[] = [];
    if (config.hasCategory) {
      defs.push({
        key: "cat",
        labelKey: "adminContent.list.category",
        type: "select",
        options: categories.map((category) => ({ value: category.id, label: category.name.uz })),
      });
    }
    if (config.hasPublished) {
      defs.push({
        key: "pub",
        labelKey: "adminContent.list.published",
        type: "select",
        options: [
          { value: "1", labelKey: "adminContent.filter.yes" },
          { value: "0", labelKey: "adminContent.filter.no" },
        ],
      });
    }
    return defs;
  }, [categories, config.hasCategory, config.hasPublished]);

  const filters = useAdminFilters(filterDefs, "content.filters");

  const query = useQuery({ queryKey: config.queryKey(), queryFn: config.list, retry: false });

  const categoryName = useMemo(() => {
    const map = new Map(categories.map((category) => [category.id, category.name.uz]));
    return (id: string) => map.get(id) ?? id;
  }, [categories]);

  const rows = useMemo(() => {
    let items = query.data?.items ?? [];
    const needle = search.trim().toLowerCase();
    if (needle) {
      items = items.filter(
        (item) =>
          item.id.toLowerCase().includes(needle) ||
          recordTitle(item, config.titleField).toLowerCase().includes(needle),
      );
    }
    if (filters.values.cat) items = items.filter((item) => item.category_id === filters.values.cat);
    if (filters.values.pub) {
      const want = filters.values.pub === "1";
      items = items.filter((item) => Boolean(item.published) === want);
    }
    return [...items].sort((a, b) => a.sort_order - b.sort_order || a.id.localeCompare(b.id));
  }, [query.data, search, filters.values.cat, filters.values.pub, config.titleField]);

  useAdminHeader({
    titleKey: "admin.nav.content",
    primary: {
      labelKey: config.newLabelKey,
      icon: Plus,
      onClick: () => navigate(`${contentPath(kind)}/new`),
    },
  });

  return (
    <div className="space-y-2 pb-2">
      <Tabs
        ariaLabelKey="adminContent.tabs.aria"
        tabs={CONTENT_KINDS.map((id) => ({ id, labelKey: CONTENT_CONFIG[id].tabLabelKey }))}
        value={kind}
        onChange={(next) => navigate(contentPath(next))}
      />

      <SearchBar value={search} onChange={setSearch} placeholderKey="adminContent.list.searchPlaceholder" />
      {filterDefs.length > 0 && <FilterChips defs={filterDefs} state={filters} />}

      {query.isLoading ? (
        <Skeleton rows={6} />
      ) : query.isError ? (
        <ErrorCard error={query.error} onRetry={() => void query.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState labelKey={config.emptyKey} />
      ) : (
        <List ariaLabelKey={config.tabLabelKey}>
          {rows.map((row) => {
            const meta = [
              config.hasCategory && row.category_id ? categoryName(row.category_id) : "",
              `${t("adminContent.list.sort")} ${row.sort_order}`,
            ].filter(Boolean);
            return (
              <ListRow
                key={row.id}
                title={recordTitle(row, config.titleField)}
                subtitle={meta.join(" · ")}
                trailing={
                  config.hasPublished ? (
                    <StatusChip
                      status={row.published ? "published" : "draft"}
                      labelKey={
                        row.published ? "adminContent.list.published" : "adminContent.list.unpublished"
                      }
                    />
                  ) : undefined
                }
                to={contentPath(kind, row.id)}
              />
            );
          })}
        </List>
      )}
    </div>
  );
}
