import { useMemo, useState } from "react";
import { Users } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { adminKeys, listAdminUsers } from "../../../api/admin";
import type { AdminUserListItem, AdminUsersQuery } from "../../../api/adminTypes";
import useToast from "../../../hooks/useToast";
import { regionName, useRegions } from "../../../hooks/useStaticList";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import ErrorCard from "../components/ErrorCard";
import LoadMore from "../components/LoadMore";
import useCursorQuery from "../hooks/useCursorQuery";
import {
  Button,
  EmptyState,
  FilterChips,
  List,
  ListRow,
  SearchBar,
  Sheet,
  Skeleton,
  StatusChip,
  useAdminFilters,
  useAdminHeader,
  useHistorySheet,
  useQueryState,
  type FilterDef,
} from "../ui";
import { dayEnd, dayStart, displayName, parseUserId, userDetailPath } from "./format";

const PAGE_SIZE = 30;
const OPEN_BY_ID = "users.openById";

const INPUT =
  "h-9 w-full rounded-xl border border-border bg-surface px-2.5 text-[13px] text-text placeholder:text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

/**
 * The list screen: one search row, one chip row, dense rows.
 *
 * Every filter — search, Pro, ban, blocked, language, region, signup range and
 * the sort field — lives in the URL (spec §2), so back undoes the last change
 * and a filtered list is a shareable link.
 */
export default function UsersListScreen() {
  const t = useT();
  const toast = useToast();
  const navigate = useNavigate();
  const { formatMoney, formatDate } = useLocale();

  const [search, setSearch] = useQueryState<string>("q", "", { replace: true });
  const regions = useRegions();
  const openById = useHistorySheet(OPEN_BY_ID);
  const [idDraft, setIdDraft] = useState("");

  const defs = useMemo<FilterDef[]>(
    () => [
      {
        key: "pro",
        labelKey: "adminUsers.filter.pro",
        type: "select",
        options: [
          { value: "1", labelKey: "adminUsers.filter.proYes" },
          { value: "0", labelKey: "adminUsers.filter.proNo" },
        ],
      },
      { key: "banned", labelKey: "adminUsers.filter.banned", type: "toggle" },
      { key: "blocked", labelKey: "adminUsers.filter.blocked", type: "toggle" },
      {
        key: "lang",
        labelKey: "adminUsers.filter.lang",
        type: "select",
        options: [
          { value: "uz", labelKey: "adminUsers.lang.uz" },
          { value: "ru", labelKey: "adminUsers.lang.ru" },
          { value: "en", labelKey: "adminUsers.lang.en" },
        ],
      },
      {
        key: "region",
        labelKey: "adminUsers.filter.region",
        type: "select",
        options: (regions.data ?? []).map((region) => ({
          value: region.soato,
          label: regionName(region),
        })),
      },
      { key: "joined", labelKey: "adminUsers.filter.joined", type: "date-range" },
      {
        key: "sort",
        labelKey: "adminUsers.filter.sort",
        type: "select",
        options: [
          { value: "date", labelKey: "adminUsers.sort.date" },
          { value: "balance", labelKey: "adminUsers.sort.balance" },
          { value: "last_seen", labelKey: "adminUsers.sort.lastSeen" },
        ],
      },
    ],
    [regions.data],
  );

  const filters = useAdminFilters(defs, "users.filters");
  const values = filters.values;

  const query = useMemo<AdminUsersQuery>(() => {
    const built: AdminUsersQuery = { limit: PAGE_SIZE };
    const q = search.trim();
    if (q) built.q = q;
    if (values.pro) built.pro = values.pro === "1";
    if (values.banned === "1") built.banned = true;
    if (values.blocked === "1") built.blocked = true;
    if (values.lang) built.lang = values.lang;
    if (values.region) built.region = values.region;
    const from = dayStart(values.joined_from);
    const to = dayEnd(values.joined_to);
    if (from !== undefined) built.from = from;
    if (to !== undefined) built.to = to;
    const sort = values.sort;
    built.sort = sort === "balance" || sort === "last_seen" ? sort : "date";
    return built;
  }, [search, values]);

  const users = useCursorQuery<AdminUserListItem>(
    adminKeys.users(query),
    (cursor) => listAdminUsers({ ...query, cursor: cursor ?? undefined }),
    { staleTime: 15_000 },
  );

  useAdminHeader({
    titleKey: "admin.nav.users",
    menu: [
      { labelKey: "adminUsers.openById", onClick: () => openById.openSheet() },
      {
        labelKey: "admin.filter.clear",
        onClick: () => filters.clear(),
        disabled: filters.activeCount === 0,
      },
    ],
  });

  function submitOpenById() {
    const userId = parseUserId(idDraft);
    if (userId === null) {
      toast.error(t("adminUsers.openById.invalid"));
      return;
    }
    setIdDraft("");
    // Replacing the sheet entry keeps the stack at list -> detail.
    navigate(userDetailPath(userId), { replace: true });
  }

  const rows = users.items;

  return (
    <div className="space-y-2">
      <SearchBar value={search} onChange={setSearch} placeholderKey="adminUsers.filter.search" />
      <FilterChips defs={defs} state={filters} />

      {users.error ? (
        <ErrorCard error={users.error} onRetry={users.refetch} />
      ) : users.isLoading ? (
        <Skeleton rows={6} />
      ) : rows.length === 0 ? (
        <EmptyState icon={Users} labelKey="adminUsers.table.empty" />
      ) : (
        <List ariaLabelKey="admin.nav.users">
          {rows.map((user) => (
            <ListRow
              key={user.user_id}
              to={userDetailPath(user.user_id)}
              title={displayName(user)}
              subtitle={`${user.user_id} · ${t(
                user.is_pro ? "adminUsers.badge.pro" : "adminUsers.badge.free",
              )} · ${formatMoney(user.balance)}`}
              trailing={
                user.banned ? (
                  <StatusChip status="banned" labelKey="adminUsers.badge.banned" />
                ) : user.blocked ? (
                  <StatusChip status="blocked" labelKey="adminUsers.badge.blocked" />
                ) : undefined
              }
              meta={user.last_seen_at ? formatDate(user.last_seen_at) : "—"}
            />
          ))}
        </List>
      )}

      <LoadMore
        onLoadMore={users.loadMore}
        hasMore={users.hasMore}
        loading={users.isFetchingMore}
        total={users.total}
        loaded={rows.length}
      />

      <Sheet name={OPEN_BY_ID} titleKey="adminUsers.openById">
        <div className="space-y-2">
          <label className="block">
            <span className="mb-1 block text-[11px] font-semibold text-muted">
              {t("adminUsers.openById.label")}
            </span>
            <input
              type="number"
              inputMode="numeric"
              className={INPUT}
              placeholder="123456789"
              value={idDraft}
              onChange={(event) => setIdDraft(event.target.value)}
            />
          </label>
          <Button
            size="md"
            full
            variant="primary"
            labelKey="adminUsers.openById.submit"
            disabled={!idDraft.trim()}
            onClick={submitOpenById}
          />
        </div>
      </Sheet>
    </div>
  );
}
