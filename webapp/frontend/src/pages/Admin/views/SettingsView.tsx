import QueryState from "../components/QueryState";
import SettingsTab from "../tabs/SettingsTab";
import { useAdminState } from "../useAdminQueries";

/** `webapp_admin_settings` editor — the existing Settings tab, unchanged. */
export default function SettingsView() {
  const state = useAdminState();
  return (
    <QueryState query={state} skeletonClassName="h-64">
      {(data) => <SettingsTab state={data} />}
    </QueryState>
  );
}
