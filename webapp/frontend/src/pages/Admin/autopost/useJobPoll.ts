import { useQuery } from "@tanstack/react-query";

import { getBotJob } from "../../../api/admin";
import type { BotJob } from "../../../api/adminTypes";

const TERMINAL: BotJob["status"][] = ["done", "failed"];
const POLL_MS = 1_500;

/**
 * Polls `GET /admin/jobs/{id}` while the job is still queued/running and
 * stops the moment it reaches a terminal state. `jobId === null` disables
 * the query entirely (nothing posted yet).
 */
export function useJobPoll(jobId: number | null) {
  return useQuery<BotJob>({
    queryKey: ["admin", "jobs", jobId],
    queryFn: () => getBotJob(jobId as number),
    enabled: jobId !== null,
    retry: false,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && TERMINAL.includes(status) ? false : POLL_MS;
    },
  });
}

export default useJobPoll;
