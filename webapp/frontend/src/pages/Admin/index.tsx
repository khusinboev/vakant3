import { Suspense } from "react";
import { ShieldAlert } from "lucide-react";

import ErrorBoundary from "../../components/ErrorBoundary";
import { useT } from "../../i18n/useT";
import EmptyState from "./components/EmptyState";
import ErrorCard from "./components/ErrorCard";
import { ROLE_LABEL_KEY, roleAtLeast, useAdminRole } from "./hooks/useAdminRole";
import AdminLayout from "./layout/AdminLayout";
import { ADMIN_PAGES, DEFAULT_ADMIN_PAGE } from "./registry";
import { useAdminPageId } from "./routing";

function PageFallback() {
  const t = useT();
  return (
    <div className="flex h-40 items-center justify-center text-sm text-muted">
      {t("admin.shell.loading")}
    </div>
  );
}

/**
 * Admin panel entry.
 *
 * The page is picked from `registry.ts` by the URL (`routing.ts`), rendered
 * inside `AdminLayout` and lazily loaded, so each section is its own chunk.
 * Role checks here are cosmetic — every endpoint re-checks with `require_role`.
 */
export default function Admin() {
  const t = useT();
  const { role, isLoading, error, refetch } = useAdminRole();
  const pageId = useAdminPageId();

  if (isLoading) {
    return (
      <div className="space-y-3 py-4">
        <div className="h-16 animate-pulse rounded-2xl bg-surfaceAlt" />
        <div className="h-40 animate-pulse rounded-2xl bg-surfaceAlt" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-4">
        <ErrorCard error={error} onRetry={refetch} />
      </div>
    );
  }

  if (!role) {
    return (
      <div className="py-6">
        <EmptyState icon={ShieldAlert} labelKey="admin.accessDenied" />
      </div>
    );
  }

  const entry =
    ADMIN_PAGES.find((page) => page.id === pageId) ??
    ADMIN_PAGES.find((page) => page.id === DEFAULT_ADMIN_PAGE)!;
  const allowed = roleAtLeast(role, entry.minRole);
  const Page = entry.component;

  return (
    <AdminLayout title={t(entry.labelKey)} role={role} active={entry.id}>
      {allowed ? (
        <ErrorBoundary>
          <Suspense fallback={<PageFallback />}>
            <Page />
          </Suspense>
        </ErrorBoundary>
      ) : (
        <div
          role="alert"
          className="rounded-2xl border border-warning/40 bg-warning/10 p-4 text-sm text-warning"
        >
          {t("admin.role.required", { role: t(ROLE_LABEL_KEY[entry.minRole]) })}
        </div>
      )}
    </AdminLayout>
  );
}
