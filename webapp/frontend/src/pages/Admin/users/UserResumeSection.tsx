import { useQuery } from "@tanstack/react-query";

import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import ErrorCard from "../components/ErrorCard";
import type { ResumeUserInspect } from "../types";
import { KeyValue, List, ListRow, Skeleton, StatusChip } from "../ui";
import { getResumeInspect } from "./api";

export type UserResumeSectionProps = { userId: number; exports: number | undefined };

/**
 * The resume snapshot the old "Quick actions" tab looked up by id: state,
 * template, last update, profile preview and the latest resume events — now on
 * the user it belongs to, and only fetched when the section is opened.
 */
export default function UserResumeSection({ userId, exports }: UserResumeSectionProps) {
  const t = useT();
  const { formatNumber, formatDateTime } = useLocale();

  const inspect = useQuery<ResumeUserInspect>({
    queryKey: ["admin", "users", "resume", userId],
    queryFn: () => getResumeInspect(userId),
    retry: false,
    staleTime: 30_000,
  });

  if (inspect.isPending) return <Skeleton rows={3} />;
  if (inspect.isError) {
    return <ErrorCard error={inspect.error} onRetry={() => void inspect.refetch()} />;
  }

  const data = inspect.data;
  const preview = Object.entries(data?.profile_preview ?? {});

  return (
    <div className="space-y-2">
      <StatusChip
        status={data?.has_resume ? "done" : "draft"}
        labelKey={data?.has_resume ? "adminUsers.resume.yes" : "adminUsers.resume.no"}
      />
      <KeyValue
        rows={[
          {
            labelKey: "adminUsers.counts.resumeExports",
            value: formatNumber(exports ?? 0),
          },
          {
            labelKey: "adminUsers.resume.template",
            value: data?.selected_template || "—",
            hidden: !data?.selected_template,
          },
          {
            labelKey: "adminUsers.resume.updated",
            value: data?.updated_at ? formatDateTime(data.updated_at) : "—",
          },
          ...preview.map(([key, value]) => ({
            label: key,
            value: typeof value === "number" ? formatNumber(value) : String(value),
          })),
        ]}
      />
      {data && data.recent_events.length > 0 && (
        <List card={false} ariaLabelKey="adminUsers.detail.events">
          {data.recent_events.slice(0, 8).map((event, index) => (
            <ListRow
              key={`${event.event_name}-${event.created_at}-${index}`}
              title={
                <span className="font-mono">
                  {event.event_name}
                  {event.step ? ` · ${event.step}` : ""}
                </span>
              }
              meta={formatDateTime(event.created_at)}
            />
          ))}
        </List>
      )}
      {data && data.recent_events.length === 0 && (
        <p className="text-[11px] text-muted">{t("adminUsers.empty.events")}</p>
      )}
    </div>
  );
}
