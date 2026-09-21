import { useState } from "react";
import { Bookmark } from "lucide-react";

import { getUserSaves } from "../../../api/admin";
import { useT } from "../../../i18n/useT";
import EmptyState from "../components/EmptyState";
import ErrorCard from "../components/ErrorCard";
import LoadMore from "../components/LoadMore";
import useCursorQuery from "../hooks/useCursorQuery";

export type UserSavesProps = { userId: number };

/**
 * The user's saved vacancies. Lazy on purpose: the list is a second request
 * per user and most inspections never need it, so it only fires once the
 * admin asks for it.
 */
export default function UserSaves({ userId }: UserSavesProps) {
  const t = useT();
  const [enabled, setEnabled] = useState(false);

  const saves = useCursorQuery(
    ["admin", "users", "saves", userId],
    (cursor) => getUserSaves(userId, { cursor: cursor ?? undefined, limit: 20 }),
    { enabled },
  );

  if (!enabled) {
    return (
      <button
        type="button"
        onClick={() => setEnabled(true)}
        className="tap-target w-full rounded-xl border border-border bg-surface px-3 py-2 text-xs font-semibold text-text"
      >
        {t("adminUsers.saves.load")}
      </button>
    );
  }

  if (saves.error) return <ErrorCard error={saves.error} onRetry={saves.refetch} />;

  if (saves.isLoading) {
    return (
      <div className="space-y-2" aria-busy="true">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-8 animate-pulse rounded-lg bg-surfaceAlt" />
        ))}
      </div>
    );
  }

  if (saves.items.length === 0) {
    return <EmptyState icon={Bookmark} labelKey="adminUsers.empty.saves" />;
  }

  return (
    <div>
      <ul className="space-y-1">
        {saves.items.map((item) => (
          <li
            key={String(item.save_id)}
            className="rounded-lg border border-border bg-surface px-2.5 py-1.5 font-mono text-[11px] text-text"
          >
            {item.uid}
          </li>
        ))}
      </ul>
      <LoadMore
        onLoadMore={saves.loadMore}
        hasMore={saves.hasMore}
        loading={saves.isFetchingMore}
        total={saves.total}
        loaded={saves.items.length}
      />
    </div>
  );
}
