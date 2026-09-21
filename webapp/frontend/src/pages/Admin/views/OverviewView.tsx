import QueryState from "../components/QueryState";
import OverviewTab from "../tabs/OverviewTab";
import { useAdminState } from "../useAdminQueries";

/**
 * Dashboard placeholder: the existing Overview tab, unchanged, inside the new
 * shell. The Analytics page agent extends this with the `daily_stats` rollup.
 */
export default function OverviewView() {
  const state = useAdminState();
  return (
    <QueryState query={state} skeletonClassName="h-64">
      {(data) => <OverviewTab state={data} />}
    </QueryState>
  );
}
