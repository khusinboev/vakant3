/**
 * Logical hierarchy of the Mini App. Back goes UP this tree, it never replays
 * browsing history. `/app` is the only root: the other bottom-nav tabs
 * (profile, hub, admin) sit one level below it, so Back from a tab lands on Home.
 *
 * Pure and import-free on purpose: `scripts/nav-check.mjs` exercises it in node.
 */

export const HOME_PATH = "/app";

/** Static parents of the app screens. Admin paths are derived (see `adminParent`). */
const APP_PARENTS: Record<string, string> = {
  "/profile": HOME_PATH,
  "/hub": HOME_PATH,
  "/saves": "/profile",
  "/wallet": "/profile",
  "/referral": "/profile",
  "/hub/resume": "/hub",
  "/hub/laws": "/hub",
};

export function normalizePath(pathname: string): string {
  const trimmed = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  return trimmed || "/";
}

export function isAdminPath(pathname: string): boolean {
  const path = normalizePath(pathname);
  return path === "/admin" || path.startsWith("/admin/");
}

/**
 * `/admin` -> `/app`; `/admin/users/7/action/ban` -> `/admin/users/7`;
 * every other sub-page drops its last segment (`/admin/content/laws/5` ->
 * `/admin/content/laws` -> `/admin/content` -> `/admin`).
 */
function adminParent(path: string): string {
  if (path === "/admin") return HOME_PATH;
  const segments = path.split("/").filter(Boolean);
  const drop = segments.length >= 3 && segments[segments.length - 2] === "action" ? 2 : 1;
  const parent = segments.slice(0, segments.length - drop);
  return parent.length > 0 ? `/${parent.join("/")}` : "/admin";
}

/** A parent a screen was opened with (`navigate(to, { state: { navParent } })`). */
function overrideParent(state: unknown): string | null {
  const value = (state as { navParent?: unknown } | null)?.navParent;
  if (typeof value !== "string") return null;
  return value.startsWith("/") && !value.startsWith("//") ? normalizePath(value) : null;
}

/** The screen Back leads to, or `null` at the root (Home). */
export function parentOf(pathname: string, state?: unknown): string | null {
  const path = normalizePath(pathname);
  if (path === "/" || path === HOME_PATH) return null;
  const override = overrideParent(state);
  if (override && override !== path) return override;
  if (isAdminPath(path)) return adminParent(path);
  return APP_PARENTS[path] ?? HOME_PATH;
}
