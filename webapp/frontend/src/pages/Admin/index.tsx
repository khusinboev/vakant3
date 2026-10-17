import { Suspense, type ReactElement } from "react";
import { ShieldAlert } from "lucide-react";
import { Navigate, Route, Routes } from "react-router-dom";

import ErrorBoundary from "../../components/ErrorBoundary";
import { useT } from "../../i18n/useT";
import ErrorCard from "./components/ErrorCard";
import { ROLE_LABEL_KEY, roleAtLeast, useAdminRole, type AdminRole } from "./hooks/useAdminRole";
import AdminShell from "./layout/AdminShell";
import { ADMIN_ROUTES, type AdminPageEntry } from "./registry";
import EmptyState from "./ui/EmptyState";
import Skeleton from "./ui/Skeleton";

function PageFallback() {
  return <Skeleton rows={5} className="pt-2" />;
}

function RoleNotice({ min }: { min: AdminRole }) {
  const t = useT();
  return (
    <div
      role="alert"
      className="rounded-xl border border-warning/40 bg-warning/10 p-3 text-[13px] text-warning"
    >
      {t("admin.role.required", { role: t(ROLE_LABEL_KEY[min]) })}
    </div>
  );
}

function PageSlot({ entry, role }: { entry: AdminPageEntry; role: AdminRole | null }) {
  const Page = entry.component;
  if (!roleAtLeast(role, entry.minRole)) return <RoleNotice min={entry.minRole} />;
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageFallback />}>
        <Page />
      </Suspense>
    </ErrorBoundary>
  );
}

/**
 * Admin panel entry (v3).
 *
 * `App.tsx` mounts it at `/admin/*` **outside** the app `Layout`, so the panel
 * owns the whole viewport: one header, one bottom bar. The routes come from
 * `registry.ts` — a section, its detail view and its action sheets are all
 * real URLs, which is what makes back / Esc / the Telegram BackButton work.
 *
 * Role checks here are cosmetic — every endpoint re-checks with `require_role`.
 */
export default function Admin() {
  const { role, isLoading, error, refetch } = useAdminRole();

  if (isLoading) {
    return (
      <AdminShell role={null}>
        <Skeleton rows={6} />
      </AdminShell>
    );
  }

  if (error) {
    return (
      <AdminShell role={null}>
        <ErrorCard error={error} onRetry={refetch} />
      </AdminShell>
    );
  }

  if (!role) {
    return (
      <AdminShell role={null}>
        <EmptyState icon={ShieldAlert} labelKey="admin.accessDenied" />
      </AdminShell>
    );
  }

  const routes: ReactElement[] = [];
  for (const entry of ADMIN_ROUTES) {
    const element = <PageSlot entry={entry} role={role} />;
    routes.push(
      entry.path === "" ? (
        <Route key={entry.id} index element={element} />
      ) : (
        <Route key={entry.id} path={entry.path} element={element} />
      ),
    );
    for (const child of entry.children ?? []) {
      routes.push(
        <Route key={`${entry.id}/${child}`} path={`${entry.path}/${child}`} element={element} />,
      );
    }
  }

  return (
    <AdminShell role={role}>
      <Routes>
        {routes}
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Routes>
    </AdminShell>
  );
}
