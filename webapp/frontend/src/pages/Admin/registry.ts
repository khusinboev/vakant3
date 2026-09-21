import { lazy, type ComponentType, type ElementType, type LazyExoticComponent } from "react";
import {
  Activity,
  BarChart3,
  BookOpen,
  FileText,
  LayoutDashboard,
  Megaphone,
  Radio,
  Send,
  Settings,
  Users,
  Wallet,
  Zap,
} from "lucide-react";

import type { TranslationKey } from "../../i18n";
import type { AdminRole } from "./hooks/useAdminRole";

export type AdminPageId =
  | "overview"
  | "analytics"
  | "resume"
  | "users"
  | "quick"
  | "broadcasts"
  | "channels"
  | "autopost"
  | "content"
  | "finance"
  | "system"
  | "settings";

export type AdminGroupId = "main" | "people" | "content" | "money" | "system";

export type AdminPageEntry = {
  id: AdminPageId;
  /** URL segment (see `routing.ts`). */
  path: string;
  labelKey: TranslationKey;
  icon: ElementType;
  /** Hidden from the nav and refused by the shell below this role. */
  minRole: AdminRole;
  group: AdminGroupId;
  component: LazyExoticComponent<ComponentType>;
};

/**
 * The single source of truth for the admin panel's pages: the sidebar, the
 * mobile tabs and the router all read this array. Every page is a separate
 * lazy chunk, so opening the panel does not pull in recharts or the broadcast
 * composer.
 *
 * Page agents own their `pages/<Name>Page.tsx` file only — adding a page means
 * one line here.
 */
export const ADMIN_PAGES: AdminPageEntry[] = [
  {
    id: "overview",
    path: "overview",
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
    component: lazy(() => import("./pages/UsersPage")),
  },
  {
    id: "broadcasts",
    path: "broadcasts",
    labelKey: "admin.nav.broadcasts",
    icon: Megaphone,
    minRole: "admin",
    group: "people",
    component: lazy(() => import("./pages/BroadcastsPage")),
  },
  {
    id: "quick",
    path: "quick",
    labelKey: "admin.nav.quick",
    icon: Zap,
    minRole: "admin",
    group: "people",
    component: lazy(() => import("./views/QuickActionsView")),
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
];

export const ADMIN_GROUPS: { id: AdminGroupId; labelKey: TranslationKey }[] = [
  { id: "main", labelKey: "admin.nav.group.main" },
  { id: "people", labelKey: "admin.nav.group.people" },
  { id: "content", labelKey: "admin.nav.group.content" },
  { id: "money", labelKey: "admin.nav.group.money" },
  { id: "system", labelKey: "admin.nav.group.system" },
];

export const DEFAULT_ADMIN_PAGE: AdminPageId = "overview";

/** Shown directly in the mobile tab bar; everything else lives behind "More". */
export const MOBILE_PRIMARY_PAGES: AdminPageId[] = [
  "overview",
  "users",
  "broadcasts",
  "finance",
];

export function findAdminPage(id: string | null | undefined): AdminPageEntry | undefined {
  if (!id) return undefined;
  return ADMIN_PAGES.find((page) => page.id === id || page.path === id);
}
