import HistoryCard from "../autopost/HistoryCard";
import PostNowCard from "../autopost/PostNowCard";
import ScheduleCard from "../autopost/ScheduleCard";
import StatusHeader from "../autopost/StatusHeader";

/**
 * Auto-post control room: read-only settings summary (edit on Settings),
 * today's schedule slots, a manual "post now" with confirmation + job
 * polling, and the full post history (CONTRACT_P12.md §m010).
 */
export default function AutoPostPage() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-4">
        <StatusHeader />
        <ScheduleCard />
      </div>
      <div className="space-y-4">
        <PostNowCard />
      </div>
      <div className="lg:col-span-2">
        <HistoryCard />
      </div>
    </div>
  );
}
