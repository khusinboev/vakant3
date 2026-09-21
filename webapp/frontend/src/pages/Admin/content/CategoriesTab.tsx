import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen, Pencil, Plus } from "lucide-react";

import { adminKeys, listContentCategories } from "../../../api/admin";
import type { ContentCategory } from "../../../api/adminTypes";
import { useT } from "../../../i18n/useT";
import DataTable, { type Column, type SortState } from "../components/DataTable";
import FilterBar from "../components/FilterBar";
import CategoryEditor from "./CategoryEditor";

type EditorState = { mode: "create" } | { mode: "edit"; category: ContentCategory } | null;

export default function CategoriesTab() {
  const t = useT();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: adminKeys.contentCategories(), queryFn: listContentCategories, retry: false });

  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortState>(null);
  const [editor, setEditor] = useState<EditorState>(null);

  const rows = useMemo(() => {
    let items = query.data?.items ?? [];
    const q = search.trim().toLowerCase();
    if (q) items = items.filter((c) => c.id.toLowerCase().includes(q) || c.name.uz.toLowerCase().includes(q));

    const sorted = [...items];
    if (sort) {
      sorted.sort((a, b) => {
        const dir = sort.direction === "asc" ? 1 : -1;
        if (sort.key === "sort_order") return (a.sort_order - b.sort_order) * dir;
        if (sort.key === "id") return a.id.localeCompare(b.id) * dir;
        return 0;
      });
    } else {
      sorted.sort((a, b) => a.sort_order - b.sort_order || a.id.localeCompare(b.id));
    }
    return sorted;
  }, [query.data, search, sort]);

  // Articles reference categories by id (`ContentArticleAdmin.category_id`); a
  // category delete/rename can change what the Articles tab's cached list
  // shows (the category name column reads its own `useContentCategories`
  // query), so both caches are invalidated together on any category mutation.
  const onMutated = () => {
    void queryClient.invalidateQueries({ queryKey: adminKeys.contentArticles() });
    setEditor(null);
  };

  if (editor?.mode === "create") {
    return <CategoryEditor mode="create" initial={null} onClose={() => setEditor(null)} onSaved={onMutated} onDeleted={onMutated} />;
  }
  if (editor?.mode === "edit") {
    return (
      <CategoryEditor mode="edit" initial={editor.category} onClose={() => setEditor(null)} onSaved={onMutated} onDeleted={onMutated} />
    );
  }

  const columns: Column<ContentCategory>[] = [
    { key: "id", labelKey: "adminContent.list.id", render: (row) => row.id, sortKey: "id" },
    { key: "name", labelKey: "adminContent.list.name", render: (row) => row.name.uz },
    {
      key: "sort_order",
      labelKey: "adminContent.list.sort",
      align: "right",
      render: (row) => row.sort_order,
      sortKey: "sort_order",
      hideOnCard: true,
    },
    {
      key: "actions",
      labelKey: "adminContent.list.actions",
      align: "right",
      hideOnCard: true,
      render: (row) => (
        <button
          type="button"
          onClick={() => setEditor({ mode: "edit", category: row })}
          aria-label={t("adminContent.list.edit")}
          className="tap-target rounded-lg p-1.5 text-muted hover:bg-surfaceAlt hover:text-text"
        >
          <Pencil size={14} aria-hidden="true" />
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-3">
      <FilterBar onReset={() => setSearch("")}>
        <FilterBar.Search value={search} onChange={setSearch} />
        <button
          type="button"
          onClick={() => setEditor({ mode: "create" })}
          className="tap-target ml-auto inline-flex items-center gap-1.5 rounded-xl bg-primary px-3 py-2 text-xs font-semibold text-primaryFg"
        >
          <Plus size={14} aria-hidden="true" />
          {t("adminContent.new.category")}
        </button>
      </FilterBar>

      <DataTable
        columns={columns}
        rows={rows}
        getRowId={(row) => row.id}
        loading={query.isLoading}
        error={query.error}
        onRetry={() => void query.refetch()}
        emptyKey="adminContent.empty.categories"
        emptyIcon={FolderOpen}
        onRowClick={(row) => setEditor({ mode: "edit", category: row })}
        sort={sort}
        onSortChange={setSort}
        captionKey="adminContent.tab.categories"
      />
    </div>
  );
}
