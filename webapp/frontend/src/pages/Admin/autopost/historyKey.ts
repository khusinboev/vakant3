import type { QueryKey } from "@tanstack/react-query";

/** Prefix shared by `HistoryCard`'s query and `PostNowCard`'s post-job invalidation. */
export const AUTO_POST_HISTORY_KEY: QueryKey = ["admin", "auto-post-history"];
