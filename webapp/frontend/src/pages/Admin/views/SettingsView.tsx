import QueryState from "../components/QueryState";
import SettingsTab from "../tabs/SettingsTab";
import { useAdminHeader } from "../ui";
import { useAdminState } from "../useAdminQueries";
import type { AdminState } from "../types";

/** `/admin/settings` — `webapp_admin_settings` editor. `version` drives the optimistic-lock guard. */
export default function SettingsView() {
  useAdminHeader({ titleKey: "admin.nav.settings" });
  const state = useAdminState();
  return (
    <QueryState query={state} skeletonClassName="h-64">
      {(data) => (
        <SettingsTab
          state={data}
          version={(data as AdminState & { version?: number }).version}
          onReload={() => void state.refetch()}
        />
      )}
    </QueryState>
  );
}
