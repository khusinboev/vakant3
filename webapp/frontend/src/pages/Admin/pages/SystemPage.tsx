import AdminsTab from "../system/AdminsTab";
import AuditTab from "../system/AuditTab";
import ErrorsTab from "../system/ErrorsTab";
import HealthTab from "../system/HealthTab";
import SystemTabs from "../system/SystemTabs";
import { useSystemTab } from "../system/useSystemTab";

const PANELS = {
  health: HealthTab,
  admins: AdminsTab,
  audit: AuditTab,
  errors: ErrorsTab,
} as const;

/**
 * System: DB/scheduler health (auto-refreshing), owner-only admins roster,
 * the audit log and the error log — four sub-tabs behind one page id so the
 * sidebar/registry stay a single entry.
 */
export default function SystemPage() {
  const [tab, setTab] = useSystemTab();
  const Panel = PANELS[tab];

  return (
    <div className="space-y-4">
      <SystemTabs active={tab} onChange={setTab} />
      <div role="tabpanel" id={`system-panel-${tab}`} aria-labelledby={`system-tab-${tab}`}>
        <Panel />
      </div>
    </div>
  );
}
