import { Navigate, useLocation } from "react-router-dom";

import ContentEditor from "../content/ContentEditor";
import ContentList from "../content/ContentList";
import { DEFAULT_CONTENT_KIND, contentPath, isContentKind } from "../content/kinds";

const BASE = "/admin/content";

/**
 * Law articles / HR tips / categories CRUD (CONTRACT_P12 m007).
 *
 * Every state is a URL: `/admin/content/:kind` is the list (the tabs navigate,
 * they hold no state), `/admin/content/:kind/new` and `/admin/content/:kind/:id`
 * are the editor — so one back press is always one level.
 */
export default function ContentPage() {
  const location = useLocation();
  const segments = location.pathname.slice(BASE.length).split("/").filter(Boolean);
  const [rawKind, rawId] = segments;

  if (!isContentKind(rawKind)) {
    return <Navigate to={contentPath(DEFAULT_CONTENT_KIND)} replace />;
  }

  if (rawId === "new") return <ContentEditor kind={rawKind} id={null} />;
  if (rawId) return <ContentEditor kind={rawKind} id={rawId} />;
  return <ContentList kind={rawKind} />;
}
