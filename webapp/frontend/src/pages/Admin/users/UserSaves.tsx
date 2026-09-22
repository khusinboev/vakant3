import { Bookmark } from "lucide-react";

import { getUserSaves } from "../../../api/admin";
import ErrorCard from "../components/ErrorCard";
import LoadMore from "../components/LoadMore";
import useCursorQuery from "../hooks/useCursorQuery";
import { EmptyState, List, ListRow, Skeleton } from "../ui";

export type UserSavesProps = { userId: number };

/**
 * The user's saved vacancies. Lazy by construction: the accordion only mounts
 * an open section, so the second request per user fires when an admin asks.
 */
export default function UserSaves({ userId }: UserSavesProps) {
  const saves = useCursorQuery(
    ["admin", "users", "saves", userId],
    (cursor) => getUserSaves(userId, { cursor: cursor ?? undefined, limit: 20 }),
    { staleTime: 15_000 },
  );

  if (saves.error) return <ErrorCard error={saves.error} onRetry={saves.refetch} />;
  if (saves.isLoading) return <Skeleton rows={3} />;
  if (saves.items.length === 0) {
    return <EmptyState icon={Bookmark} labelKey="adminUsers.empty.saves" />;
  }

  return (
    <div>
      <List card={false}>
        {saves.items.map((item) => (
          <ListRow key={String(item.save_id)} title={<span className="font-mono">{item.uid}</span>} />
        ))}
      </List>
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
