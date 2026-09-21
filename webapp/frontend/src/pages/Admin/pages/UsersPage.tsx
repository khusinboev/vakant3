import { useEffect, useMemo, useState } from "react";
import { Users } from "lucide-react";

import { adminKeys, listAdminUsers } from "../../../api/admin";
import type { AdminUserListItem, AdminUsersQuery } from "../../../api/adminTypes";
import StyledSelect from "../../../components/ui/StyledSelect";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import { useRegions } from "../../../hooks/useStaticList";
import DataTable, { type Column, type SortState } from "../components/DataTable";
import FilterBar from "../components/FilterBar";
import useCursorQuery from "../hooks/useCursorQuery";
import UserStatusBadges from "../users/UserBadges";
import UserDetail from "../users/UserDetail";
import UserDrawer from "../users/UserDrawer";
import { dayEnd, dayStart, displayName, langLabelKey, usernameLine } from "../users/format";

const PAGE_SIZE = 30;

const PRO_OPTIONS = [
  { value: "yes", labelKey: "adminUsers.filter.proYes" },
  { value: "no", labelKey: "adminUsers.filter.proNo" },
] as const;

const LANG_OPTIONS = [
  { value: "uz", labelKey: "adminUsers.lang.uz" },
  { value: "ru", labelKey: "adminUsers.lang.ru" },
  { value: "en", labelKey: "adminUsers.lang.en" },
] as const;

type SortField = NonNullable<AdminUsersQuery["sort"]>;

const SORT_COLUMN: Record<string, SortField> = {
  date: "date",
  balance: "balance",
  last_seen: "last_seen",
};

/**
 * The Users page: filter, list, inspect, act.
 *
 * It also replaces the old "Quick actions" tab — balance top-ups, the resume
 * export counter and the account reset all live in the per-user drawer now,
 * where the admin can see who they are acting on.
 */
export default function UsersPage() {
  const t = useT();
  const { formatMoney, formatDate } = useLocale();

  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [pro, setPro] = useState("");
  const [banned, setBanned] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [lang, setLang] = useState("");
  const [region, setRegion] = useState("");
  const [range, setRange] = useState({ from: "", to: "" });
  const [sort, setSort] = useState<SortState>({ key: "date", direction: "desc" });
  const [selected, setSelected] = useState<AdminUserListItem | null>(null);

  const regions = useRegions();

  // A search box that fires a request per keystroke turns a 10 k-row table
  // into a denial of service against our own API.
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 350);
    return () => window.clearTimeout(timer);
  }, [search]);

  const query = useMemo<AdminUsersQuery>(() => {
    const built: AdminUsersQuery = { limit: PAGE_SIZE };
    if (debouncedSearch) built.q = debouncedSearch;
    if (pro) built.pro = pro === "yes";
    if (banned) built.banned = true;
    if (blocked) built.blocked = true;
    if (lang) built.lang = lang;
    if (region) built.region = region;
    const from = dayStart(range.from);
    const to = dayEnd(range.to);
    if (from !== undefined) built.from = from;
    if (to !== undefined) built.to = to;
    built.sort = SORT_COLUMN[sort?.key ?? "date"] ?? "date";
    return built;
  }, [debouncedSearch, pro, banned, blocked, lang, region, range.from, range.to, sort]);

  const users = useCursorQuery<AdminUserListItem>(
    adminKeys.users(query),
    (cursor) => listAdminUsers({ ...query, cursor: cursor ?? undefined }),
    { staleTime: 15_000 },
  );

  function resetFilters() {
    setSearch("");
    setDebouncedSearch("");
    setPro("");
    setBanned(false);
    setBlocked(false);
    setLang("");
    setRegion("");
    setRange({ from: "", to: "" });
    setSort({ key: "date", direction: "desc" });
  }

  const columns: Column<AdminUserListItem>[] = [
    {
      key: "user",
      labelKey: "adminUsers.col.user",
      render: (row) => (
        <span className="block min-w-0">
          <span className="block truncate font-medium text-text">{displayName(row)}</span>
          <span className="block truncate text-[11px] text-muted">{usernameLine(row)}</span>
        </span>
      ),
    },
    {
      key: "status",
      labelKey: "adminUsers.col.status",
      render: (row) => <UserStatusBadges user={row} />,
    },
    {
      key: "balance",
      labelKey: "adminUsers.col.balance",
      align: "right",
      sortKey: "balance",
      render: (row) => formatMoney(row.balance),
    },
    {
      key: "lang",
      labelKey: "adminUsers.col.lang",
      hideOnCard: true,
      render: (row) => {
        const key = langLabelKey(row.lang);
        return key ? t(key) : (row.lang ?? "—");
      },
    },
    {
      key: "region",
      labelKey: "adminUsers.col.region",
      hideOnCard: true,
      render: (row) => row.region ?? "—",
    },
    {
      key: "date",
      labelKey: "adminUsers.col.joined",
      sortKey: "date",
      hideOnCard: true,
      render: (row) => (row.date ? formatDate(row.date) : "—"),
    },
    {
      key: "last_seen_at",
      labelKey: "adminUsers.col.lastSeen",
      sortKey: "last_seen",
      hideOnCard: true,
      render: (row) => (row.last_seen_at ? formatDate(row.last_seen_at) : "—"),
    },
  ];

  return (
    <div className="space-y-4">
      <FilterBar onReset={resetFilters}>
        <FilterBar.Search
          value={search}
          onChange={setSearch}
          placeholderKey="adminUsers.filter.search"
        />
        <FilterBar.Select
          value={pro}
          onChange={setPro}
          options={[...PRO_OPTIONS]}
          allKey="admin.filter.all"
          labelKey="adminUsers.filter.pro"
          className="w-36"
        />
        <FilterBar.Select
          value={lang}
          onChange={setLang}
          options={[...LANG_OPTIONS]}
          allKey="admin.filter.all"
          labelKey="adminUsers.filter.lang"
          className="w-32"
        />
        <StyledSelect
          value={region}
          onChange={(event) => setRegion(event.target.value)}
          aria-label={t("adminUsers.filter.region")}
          className="w-44 py-2 text-sm"
        >
          <option value="">{t("adminUsers.filter.regionAll")}</option>
          {(regions.data ?? []).map((item) => (
            <option key={item.soato} value={item.soato}>
              {item.name}
            </option>
          ))}
        </StyledSelect>
        <FilterBar.Toggle value={banned} onChange={setBanned} labelKey="adminUsers.filter.banned" />
        <FilterBar.Toggle
          value={blocked}
          onChange={setBlocked}
          labelKey="adminUsers.filter.blocked"
        />
        <FilterBar.DateRange from={range.from} to={range.to} onChange={setRange} />
      </FilterBar>

      <DataTable
        columns={columns}
        rows={users.items}
        getRowId={(row) => row.user_id}
        loading={users.isLoading}
        error={users.error}
        onRetry={users.refetch}
        emptyKey="adminUsers.table.empty"
        emptyIcon={Users}
        captionKey="adminUsers.table.caption"
        onLoadMore={users.loadMore}
        hasMore={users.hasMore}
        loadingMore={users.isFetchingMore}
        total={users.total}
        onRowClick={setSelected}
        stickyHeader
        sort={sort}
        // The API sorts newest/highest first and takes no direction, so the
        // header only picks the field; the arrow always points down.
        onSortChange={(next) =>
          setSort(next ? { key: next.key, direction: "desc" } : { key: "date", direction: "desc" })
        }
        renderCard={(row) => (
          <div className="space-y-1.5">
            <div className="flex items-start justify-between gap-2">
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold text-text">
                  {displayName(row)}
                </span>
                <span className="block truncate text-[11px] text-muted">{usernameLine(row)}</span>
              </span>
              <span className="shrink-0 text-sm font-semibold text-text">
                {formatMoney(row.balance)}
              </span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <UserStatusBadges user={row} />
              <span className="shrink-0 text-[11px] text-muted">
                {row.date ? formatDate(row.date) : "—"}
              </span>
            </div>
          </div>
        )}
      />

      <UserDrawer
        open={selected !== null}
        onClose={() => setSelected(null)}
        title={selected ? displayName(selected) : t("adminUsers.detail.title")}
        subtitle={selected ? usernameLine(selected) : undefined}
      >
        {selected && <UserDetail fallbackUser={selected} />}
      </UserDrawer>
    </div>
  );
}
