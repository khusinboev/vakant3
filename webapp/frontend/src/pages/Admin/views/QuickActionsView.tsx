import UsersTab from "../tabs/UsersTab";

/**
 * The old Users tab (add balance / inspect resume / reset user).
 * Stays reachable as "Quick actions" until the Users page agent folds it into
 * `pages/UsersPage.tsx`.
 */
export default function QuickActionsView() {
  return <UsersTab />;
}
