import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, CheckCircle2, Circle, Pencil, Plus } from "lucide-react";

import { adminKeys, listContentArticles } from "../../../api/admin";
import type { ContentArticleAdmin } from "../../../api/adminTypes";
import StyledSelect from "../../../components/ui/StyledSelect";
import { useT } from "../../../i18n/useT";
import DataTable, { type Column, type SortState } from "../components/DataTable";
import FilterBar from "../components/FilterBar";
import ArticleEditor from "./ArticleEditor";
import { useContentCategories } from "./useContentCategories";

type EditorState = { mode: "create" } | { mode: "edit"; article: ContentArticleAdmin } | null;

export default function ArticlesTab() {
  const t = useT();
  const { categories } = useContentCategories();
  const query = useQuery({ queryKey: adminKeys.contentArticles(), queryFn: listContentArticles, retry: false });

  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [publishedFilter, setPublishedFilter] = useState("");
  const [sort, setSort] = useState<SortState>(null);
  const [editor, setEditor] = useState<EditorState>(null);

  const categoryName = useMemo(() => {
    const map = new Map(categories.map((c) => [c.id, c.name.uz]));
    return (id: string) => map.get(id) ?? id;
  }, [categories]);

  const rows = useMemo(() => {
    let items = query.data?.items ?? [];
    const q = search.trim().toLowerCase();
    if (q) {
      items = items.filter(
        (a) => a.id.toLowerCase().includes(q) || a.title.uz.toLowerCase().includes(q),
      );
    }
    if (categoryFilter) items = items.filter((a) => a.category_id === categoryFilter);
    if (publishedFilter) items = items.filter((a) => String(a.published) === publishedFilter);

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
  }, [query.data, search, categoryFilter, publishedFilter, sort]);

  if (editor?.mode === "create") {
    return (
      <ArticleEditor
        mode="create"
        initial={null}
        categories={categories}
        onClose={() => setEditor(null)}
        onSaved={() => setEditor(null)}
        onDeleted={() => setEditor(null)}
      />
    );
  }
  if (editor?.mode === "edit") {
    return (
      <ArticleEditor
        mode="edit"
        initial={editor.article}
        categories={categories}
        onClose={() => setEditor(null)}
        onSaved={() => setEditor(null)}
        onDeleted={() => setEditor(null)}
      />
    );
  }

  const columns: Column<ContentArticleAdmin>[] = [
    { key: "id", labelKey: "adminContent.list.id", render: (row) => row.id, sortKey: "id" },
    { key: "title", labelKey: "adminContent.list.title", render: (row) => row.title.uz },
    { key: "category", labelKey: "adminContent.list.category", render: (row) => categoryName(row.category_id) },
    {
      key: "published",
      labelKey: "adminContent.list.published",
      align: "center",
      render: (row) =>
        row.published ? (
          <CheckCircle2 size={15} className="mx-auto text-success" aria-label={t("adminContent.list.published")} />
        ) : (
          <Circle size={15} className="mx-auto text-muted" aria-label={t("adminContent.list.unpublished")} />
        ),
    },
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
          onClick={() => setEditor({ mode: "edit", article: row })}
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
      <FilterBar onReset={() => { setSearch(""); setCategoryFilter(""); setPublishedFilter(""); }}>
        <FilterBar.Search value={search} onChange={setSearch} />
        <label className="min-w-0">
          <span className="sr-only">{t("adminContent.list.category")}</span>
          <StyledSelect
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value)}
            aria-label={t("adminContent.list.category")}
          >
            <option value="">{t("admin.filter.all")}</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name.uz}
              </option>
            ))}
          </StyledSelect>
        </label>
        <FilterBar.Toggle
          value={publishedFilter === "true"}
          onChange={(v) => setPublishedFilter(v ? "true" : "")}
          labelKey="adminContent.list.published"
        />
        <button
          type="button"
          onClick={() => setEditor({ mode: "create" })}
          className="tap-target ml-auto inline-flex items-center gap-1.5 rounded-xl bg-primary px-3 py-2 text-xs font-semibold text-primaryFg"
        >
          <Plus size={14} aria-hidden="true" />
          {t("adminContent.new.article")}
        </button>
      </FilterBar>

      <DataTable
        columns={columns}
        rows={rows}
        getRowId={(row) => row.id}
        loading={query.isLoading}
        error={query.error}
        onRetry={() => void query.refetch()}
        emptyKey="adminContent.empty.articles"
        emptyIcon={BookOpen}
        onRowClick={(row) => setEditor({ mode: "edit", article: row })}
        sort={sort}
        onSortChange={setSort}
        captionKey="adminContent.tab.articles"
      />
    </div>
  );
}
