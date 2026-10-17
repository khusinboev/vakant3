import { lazy, type ComponentType, type ElementType, type LazyExoticComponent } from "react";
import {
  Activity,
  BarChart3,
  BookOpen,
  FileText,
  Grid3x3,
  LayoutDashboard,
  Megaphone,
  Radio,
  Send,
  Settings,
  Users,
  Wallet,
} from "lucide-react";

import type { TranslationKey } from "../../i18n";
import type { AdminRole } from "./hooks/useAdminRole";

export type AdminPageId =
  | "overview"
  | "analytics"
  | "resume"
  | "users"
  | "broadcasts"
  | "channels"
  | "autopost"
  | "content"
  | "finance"
  | "system"
  | "settings"
  | "more"
  | "kit";

export type AdminGroupId = "main" | "people" | "content" | "money" | "system";

export type AdminPageEntry = {
  id: AdminPageId;
  /** URL segment under `/admin` (`""` is the panel's index route). */
  path: string;
  labelKey: TranslationKey;
  icon: ElementType;
  /** Hidden from the nav and refused by the shell below this role. */
  minRole: AdminRole;
  group: AdminGroupId;
  component: LazyExoticComponent<ComponentType>;
  /**
   * Sub-routes rendered by the same page component, relative to `path`
   * (the page reads `useParams`), e.g. `":id"` or `":id/action/:action"`.
   */
  children?: string[];
  /** Kept out of the Rail and the More grid (shell-only pages). */
  hidden?: boolean;
  /** Only registered in `import.meta.env.DEV` (the UI kit page). */
  devOnly?: boolean;
};

/**
 * The single source of truth for the admin panel: the Rail, the More grid and
 * the nested `<Routes>` in `index.tsx` all read this array. Every page is its
 * own lazy chunk, so opening the panel pulls in neither recharts nor the
 * broadcast composer.
 *
 * Page agents own `pages/<Name>Page.tsx`; adding a page is one line here.
 */
export const ADMIN_PAGES: AdminPageEntry[] = [
  {
    id: "overview",
    path: "",
    labelKey: "admin.nav.overview",
    icon: LayoutDashboard,
    minRole: "viewer",
    group: "main",
    component: lazy(() => import("./views/OverviewView")),
  },
  {
    id: "analytics",
    path: "analytics",
    labelKey: "admin.nav.analytics",
    icon: BarChart3,
    minRole: "viewer",
    group: "main",
    component: lazy(() => import("./pages/AnalyticsPage")),
  },
  {
    id: "resume",
    path: "resume",
    labelKey: "admin.nav.resume",
    icon: FileText,
    minRole: "viewer",
    group: "main",
    component: lazy(() => import("./views/ResumeAnalyticsView")),
  },
  {
    id: "users",
    path: "users",
    labelKey: "admin.nav.users",
    icon: Users,
    minRole: "moderator",
    group: "people",
    children: [":id", ":id/action/:action"],
    component: lazy(() => import("./pages/UsersPage")),
  },
  {
    id: "broadcasts",
    path: "broadcasts",
    labelKey: "admin.nav.broadcasts",
    icon: Megaphone,
    minRole: "admin",
    group: "people",
    children: ["new", ":id"],
    component: lazy(() => import("./pages/BroadcastsPage")),
  },
  {
    id: "channels",
    path: "channels",
    labelKey: "admin.nav.channels",
    icon: Radio,
    minRole: "admin",
    group: "content",
    component: lazy(() => import("./pages/ChannelsPage")),
  },
  {
    id: "autopost",
    path: "autopost",
    labelKey: "admin.nav.autopost",
    icon: Send,
    minRole: "admin",
    group: "content",
    component: lazy(() => import("./pages/AutoPostPage")),
  },
  {
    id: "content",
    path: "content",
    labelKey: "admin.nav.content",
    icon: BookOpen,
    minRole: "admin",
    group: "content",
    children: [":kind", ":kind/new", ":kind/:id"],
    component: lazy(() => import("./pages/ContentPage")),
  },
  {
    id: "finance",
    path: "finance",
    labelKey: "admin.nav.finance",
    icon: Wallet,
    minRole: "viewer",
    group: "money",
    component: lazy(() => import("./pages/FinancePage")),
  },
  {
    id: "system",
    path: "system",
    labelKey: "admin.nav.system",
    icon: Activity,
    minRole: "viewer",
    group: "system",
    component: lazy(() => import("./pages/SystemPage")),
  },
  {
    id: "settings",
    path: "settings",
    labelKey: "admin.nav.settings",
    icon: Settings,
    minRole: "admin",
    group: "system",
    component: lazy(() => import("./views/SettingsView")),
  },
  {
    id: "more",
    path: "more",
    labelKey: "admin.more.title",
    icon: Grid3x3,
    minRole: "viewer",
    group: "system",
    hidden: true,
    component: lazy(() => import("./layout/MorePage")),
  },
  // Dev-only visual smoke page; the branch (and its chunk) is dropped in a
  // production build.
  ...(import.meta.env.DEV
    ? [
        {
          id: "kit" as const,
          path: "_kit",
          labelKey: "admin.title" as const,
          icon: Grid3x3,
          minRole: "viewer" as const,
          group: "system" as const,
          hidden: true,
          devOnly: true,
          component: lazy(() => import("./ui/KitPage")),
        },
      ]
    : []),
];

/** The pages this build actually registers (the kit page is dev-only). */
export const ADMIN_ROUTES: AdminPageEntry[] = ADMIN_PAGES.filter(
  (page) => !page.devOnly || import.meta.env.DEV,
);

export const ADMIN_GROUPS: { id: AdminGroupId; labelKey: TranslationKey }[] = [
  { id: "main", labelKey: "admin.nav.group.main" },
  { id: "people", labelKey: "admin.nav.group.people" },
  { id: "content", labelKey: "admin.nav.group.content" },
  { id: "money", labelKey: "admin.nav.group.money" },
  { id: "system", labelKey: "admin.nav.group.system" },
];

export const DEFAULT_ADMIN_PAGE: AdminPageId = "overview";

/** The three sections the mobile `AdminBar` shows next to "More". */
export const MOBILE_PRIMARY_PAGES: AdminPageId[] = ["overview", "users", "broadcasts"];

export function findAdminPage(id: string | null | undefined): AdminPageEntry | undefined {
  if (!id) return undefined;
  return ADMIN_PAGES.find((page) => page.id === id || (page.path !== "" && page.path === id));
}
