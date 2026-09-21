import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

export type SystemTabId = "health" | "admins" | "audit" | "errors";

function isSystemTabId(value: string | null): value is SystemTabId {
  return value === "health" || value === "admins" || value === "audit" || value === "errors";
}

/** Sub-tab state travels in `?tab=` so a link to a specific sub-tab is shareable. */
export function useSystemTab(): [SystemTabId, (id: SystemTabId) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab");
  const tab: SystemTabId = isSystemTabId(raw) ? raw : "health";

  const setTab = useCallback(
    (id: SystemTabId) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("tab", id);
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  return [tab, setTab];
}

export default useSystemTab;
