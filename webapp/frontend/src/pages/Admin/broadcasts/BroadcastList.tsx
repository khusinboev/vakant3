import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Megaphone, Plus, RefreshCw } from "lucide-react";

import { adminKeys, listBroadcasts } from "../../../api/admin";
import type { Broadcast } from "../../../api/adminTypes";
import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import ErrorCard from "../components/ErrorCard";
import LoadMore from "../components/LoadMore";
import { useCursorQuery } from "../hooks/useCursorQuery";
import {
  Button,
  Chip,
  EmptyState,
  List,
  ListRow,
  ProgressBar,
  Skeleton,
  StatusDot,
  useAdminHeader,
} from "../ui";
import {
  ACTIVE_STATUSES,
  KIND_LABEL_KEY,
  firstLine,
  statusLabelKey,
  statusToneOf,
} from "./labels";
import { SEGMENT_LABEL_KEY, parseSegment } from "./segments";

const POLL_MS = 5000;
const NEW_PATH = "/admin/broadcasts/new";

/**
 * `/admin/broadcasts` — the jobs with live counters.
 *
 * It polls every 5 s only while something is queued or running: a finished job
 * never changes, and the panel is opened inside Telegram on phone data.
 */
export default function BroadcastList() {
  const t = useT();
  const navigate = useNavigate();
  const { formatDateTime, formatNumber } = useLocale();

  // Not an overlay: whether the 5 s poll is armed (spec §3 rule 3).
  const [poll, setPoll] = useState(false);
  const broadcasts = useCursorQuery<Broadcast>(
    adminKeys.broadcasts(),
    (cursor) => listBroadcasts({ limit: 20, cursor: cursor ?? undefined }),
    { refetchInterval: poll ? POLL_MS : false },
  );

  const items = broadcasts.items;
  const active = useMemo(() => items.some((row) => ACTIVE_STATUSES.has(row.status)), [items]);
  useEffect(() => setPoll(active), [active]);

  useAdminHeader({
    titleKey: "adminBroadcasts.title",
    primary: {
      labelKey: "adminBroadcasts.action.new",
      icon: Plus,
      onClick: () => navigate(NEW_PATH),
    },
    menu: [
      { labelKey: "adminBroadcasts.refresh", icon: RefreshCw, onClick: broadcasts.refetch },
    ],
  });

  if (broadcasts.error) {
    return <ErrorCard error={broadcasts.error} onRetry={broadcasts.refetch} />;
  }
  if (broadcasts.isLoading) return <Skeleton rows={6} />;

  if (items.length === 0) {
    return (
      <EmptyState
        icon={Megaphone}
        labelKey="adminBroadcasts.list.empty"
        action={
          <Button
            size="sm"
            variant="primary"
            icon={Plus}
            labelKey="adminBroadcasts.action.new"
            to={NEW_PATH}
          />
        }
      />
    );
  }

  return (
    <div className="space-y-2">
      {active && <Chip tone="info" labelKey="adminBroadcasts.live" />}

      <List ariaLabelKey="adminBroadcasts.list.caption">
        {items.map((row) => {
          const parsed = parseSegment(row.target?.segment ?? "all");
          const segmentText = parsed.value
            ? `${t(SEGMENT_LABEL_KEY[parsed.kind])}: ${parsed.value}`
            : t(SEGMENT_LABEL_KEY[parsed.kind]);
          const done = row.sent + row.failed + row.blocked;
          return (
            <ListRow
              key={row.id}
              to={`/admin/broadcasts/${row.id}`}
              leading={<StatusDot tone={statusToneOf(row.status)} status={row.status} />}
              title={firstLine(row.text) || t(KIND_LABEL_KEY[row.kind])}
              subtitle={`${t(statusLabelKey(row.status))} · ${segmentText}${
                row.created_at ? ` · ${formatDateTime(row.created_at)}` : ""
              }`}
              trailing={
                <span className="block w-16">
                  <ProgressBar
                    value={done}
                    max={row.total}
                    tone={statusToneOf(row.status)}
                    label={t("adminBroadcasts.progress.label", {
                      sent: formatNumber(row.sent),
                      total: formatNumber(row.total),
                    })}
                  />
                </span>
              }
              meta={`${formatNumber(row.sent)}/${formatNumber(row.total)}`}
            />
          );
        })}
      </List>

      <LoadMore
        onLoadMore={broadcasts.loadMore}
        hasMore={broadcasts.hasMore}
        loading={broadcasts.isFetchingMore}
        total={broadcasts.total}
        loaded={items.length}
      />
    </div>
  );
}
