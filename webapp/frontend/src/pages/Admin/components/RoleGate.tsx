import type { ReactNode } from "react";

import { useT } from "../../../i18n/useT";
import { ROLE_LABEL_KEY, useAdminRole, type AdminRole } from "../hooks/useAdminRole";

export type RoleGateProps = {
  /** Minimum role required to see (or use) the children. */
  min: AdminRole;
  children: ReactNode;
  /**
   * "hide"   — render `fallback` (nothing by default).
   * "disable"— render the children greyed out and non-interactive, with a
   *            tooltip naming the role that is missing.
   */
  mode?: "hide" | "disable";
  fallback?: ReactNode;
};

/**
 * Client-side role check. It is a courtesy, never a control: the API enforces
 * the same role on every route (`require_role`).
 */
export default function RoleGate({ min, children, mode = "hide", fallback = null }: RoleGateProps) {
  const t = useT();
  const { atLeast } = useAdminRole();
  if (atLeast(min)) return <>{children}</>;

  const tooltip = t("admin.role.required", { role: t(ROLE_LABEL_KEY[min]) });

  if (mode === "disable") {
    return (
      <div
        title={tooltip}
        aria-disabled="true"
        className="pointer-events-none select-none opacity-40"
      >
        {children}
      </div>
    );
  }

  return <>{fallback}</>;
}
