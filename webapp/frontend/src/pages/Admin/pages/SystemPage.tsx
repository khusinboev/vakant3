import type { ComponentType } from "react";

import AdminsTab, { ADMINS_ADD_SHEET } from "../system/AdminsTab";
import AuditTab from "../system/AuditTab";
import ErrorsTab from "../system/ErrorsTab";
import HealthTab from "../system/HealthTab";
import { useAdminHeader } from "../hooks/useAdminHeader";
import { useAdminRole } from "../hooks/useAdminRole";
import { useHistorySheet } from "../hooks/useHistorySheet";
import { Tabs, useUrlTabs, type TabDef } from "../ui";

type SystemTabId = "health" | "admins" | "audit" | "errors";

const TAB_IDS: SystemTabId[] = ["health", "admins", "audit", "errors"];

function isSystemTabId(value: string): value is SystemTabId {
  return (TAB_IDS as string[]).includes(value);
}

const TABS: TabDef<SystemTabId>[] = [
  { id: "health", labelKey: "adminSystem.tab.health" },
  { id: "admins", labelKey: "adminSystem.tab.admins" },
  { id: "audit", labelKey: "adminSystem.tab.audit" },
  { id: "errors", labelKey: "adminSystem.tab.errors" },
];

const PANELS: Record<SystemTabId, ComponentType> = {
  health: HealthTab,
  admins: AdminsTab,
  audit: AuditTab,
  errors: ErrorsTab,
};

/**
 * System: DB/scheduler health (auto-refreshing), owner-only admins roster,
 * the audit log and the error log — four sub-tabs behind one page id so the
 * registry stays a single entry. Sub-tab state lives in `?tab=` (`useUrlTabs`).
 */
export default function SystemPage() {
  const [rawTab, setTab] = useUrlTabs<SystemTabId>("tab", "health");
  const tab: SystemTabId = isSystemTabId(rawTab) ? rawTab : "health";
  const { atLeast } = useAdminRole();
  const addAdminSheet = useHistorySheet(ADMINS_ADD_SHEET);
  const Panel = PANELS[tab];

  useAdminHeader({
    primary:
      tab === "admins" && atLeast("owner")
        ? { labelKey: "adminSystem.admins.addSubmit", onClick: () => addAdminSheet.openSheet() }
        : undefined,
  });

  return (
    <div className="space-y-3">
      <Tabs tabs={TABS} value={tab} onChange={setTab} ariaLabelKey="adminSystem.tab.aria" />
      <Panel />
    </div>
  );
}
