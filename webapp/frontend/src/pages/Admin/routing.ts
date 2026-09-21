import { useLocation } from "react-router-dom";

import { DEFAULT_ADMIN_PAGE, findAdminPage, type AdminPageId } from "./registry";

export const ADMIN_BASE = "/admin";

/**
 * The panel's pages are sub-routes of `/admin`.
 *
 * `App.tsx` registers `<Route path="/admin" …>` (no trailing splat) and is
 * owned by another agent, so a path segment such as `/admin/users` would be
 * swallowed by the `*` catch-all and bounce to `/app`. Until that route becomes
 * `/admin/*`, the page id travels in the query string — `useAdminPageId`
 * already reads both forms, so flipping `PATH_ROUTING` to `true` is the only
 * change needed on this side.
 */
export const PATH_ROUTING = false;

export function adminPagePath(id: AdminPageId): string {
  return PATH_ROUTING ? `${ADMIN_BASE}/${id}` : `${ADMIN_BASE}?page=${id}`;
}

/** The page id from `/admin/<id>` or `/admin?page=<id>`, defaulted + validated. */
export function useAdminPageId(): AdminPageId {
  const location = useLocation();

  const segment = location.pathname.startsWith(`${ADMIN_BASE}/`)
    ? location.pathname.slice(ADMIN_BASE.length + 1).split("/")[0]
    : null;
  const fromPath = findAdminPage(segment);
  if (fromPath) return fromPath.id;

  const fromQuery = findAdminPage(new URLSearchParams(location.search).get("page"));
  return fromQuery ? fromQuery.id : DEFAULT_ADMIN_PAGE;
}
