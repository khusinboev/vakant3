import { useLocation } from "react-router-dom";

import { DEFAULT_ADMIN_PAGE, findAdminPage, type AdminPageId } from "./registry";

export const ADMIN_BASE = "/admin";

/**
 * The panel's pages are real sub-routes of `/admin` (App.tsx registers
 * `/admin/*` and `index.tsx` renders the nested `<Routes>`), so every section,
 * detail view and editor is its own URL — which is what makes back, the
 * Telegram BackButton and a shared link all work.
 */
export const PATH_ROUTING = true;

export function adminPagePath(id: AdminPageId): string {
  const entry = findAdminPage(id);
  const path = entry?.path ?? id;
  return path ? `${ADMIN_BASE}/${path}` : ADMIN_BASE;
}

/** The active page id from `/admin/<segment>` (or a legacy `?page=` link). */
export function useAdminPageId(): AdminPageId {
  const location = useLocation();

  const segment = location.pathname.startsWith(`${ADMIN_BASE}/`)
    ? location.pathname.slice(ADMIN_BASE.length + 1).split("/")[0]
    : null;
  const fromPath = findAdminPage(segment);
  if (fromPath) return fromPath.id;
  if (segment) return DEFAULT_ADMIN_PAGE;

  const fromQuery = findAdminPage(new URLSearchParams(location.search).get("page"));
  return fromQuery ? fromQuery.id : DEFAULT_ADMIN_PAGE;
}
