import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { ChevronLeft, MoreHorizontal } from "lucide-react";

import { useT } from "../../../i18n/useT";
import ConfirmDialogHost from "../components/ConfirmDialogHost";
import { useAdminBack } from "../hooks/useAdminBack";
import { useAdminHeaderConfig } from "../hooks/useAdminHeader";
import { useHistorySheet, hasOpenSheet } from "../hooks/useHistorySheet";
import { useIsDesktop } from "../hooks/useMediaQuery";
import { useMainButton } from "../hooks/useMainButton";
import type { AdminRole } from "../hooks/useAdminRole";
import { findAdminPage } from "../registry";
import { useAdminPageId } from "../routing";
import ActionBar from "../ui/ActionBar";
import Button, { IconButton } from "../ui/Button";
import { SheetFrame } from "../ui/Sheet";
import AdminBar from "./AdminBar";
import Rail, { readRailPinned } from "./Rail";
import { useLocation } from "react-router-dom";

const HEADER_MENU = "admin.headerMenu";
const BAR_HEIGHT = 44;

function isTyping(node: Element | null): boolean {
  if (!node) return false;
  const tag = node.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    (node as HTMLElement).isContentEditable
  );
}

export type AdminShellProps = {
  role: AdminRole | null;
  children: ReactNode;
};

/**
 * The panel's chrome: one 40px header, one 44px bottom bar on phones, a 56px
 * Rail from 1024px — 96px of chrome in total (spec §1.3), with the app's own
 * header and BottomNav switched off for `/admin/*` in App.tsx.
 *
 * Pages never draw an `<h1>`: they declare their header with
 * `useAdminHeader({ title, primary, menu })`, and on a phone inside Telegram
 * the shell turns `primary` into the native MainButton.
 */
export default function AdminShell({ role, children }: AdminShellProps) {
  const t = useT();
  const location = useLocation();
  const isDesktop = useIsDesktop();
  const { back } = useAdminBack();
  const config = useAdminHeaderConfig();
  const pageId = useAdminPageId();
  const entry = findAdminPage(pageId);
  const menuSheet = useHistorySheet(HEADER_MENU);
  const [railPinned, setRailPinned] = useState(readRailPinned);

  const declared = config?.title ?? (config?.titleKey ? t(config.titleKey) : "");
  const heading = declared || (entry ? t(entry.labelKey) : t("admin.title"));
  const primary = config?.primary;
  const menu = (config?.menu ?? []).filter((item) => !item.hidden);

  const goBack = () => {
    if (typeof config?.back === "function") config.back();
    else back();
  };

  // Esc = one level back, exactly like the Telegram BackButton. An open sheet
  // closes itself (it owns its own Esc), and typing is never interrupted.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (hasOpenSheet(location)) return;
      if (isTyping(document.activeElement)) return;
      goBack();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location, config?.back, back]);

  const { native } = useMainButton({
    text: primary?.label,
    textKey: primary?.labelKey,
    onClick: () => primary?.onClick(),
    enabled: !primary?.disabled,
    loading: primary?.loading,
    visible: Boolean(primary) && !isDesktop,
  });

  const railWidth = isDesktop ? (railPinned ? 220 : 56) : 0;

  return (
    <div
      className="admin-root min-h-[var(--app-viewport-height)] bg-bg text-text"
      style={
        {
          paddingLeft: railWidth ? `${railWidth}px` : undefined,
          "--admin-bar-h": isDesktop ? "0px" : `${BAR_HEIGHT}px`,
        } as CSSProperties
      }
    >
      {isDesktop && <Rail role={role} pinned={railPinned} onPinnedChange={setRailPinned} />}

      <header className="sticky top-0 z-20 flex h-10 items-center gap-1 border-b border-border bg-surface/95 px-1.5 backdrop-blur">
        <IconButton icon={ChevronLeft} ariaLabel={t("admin.shell.back")} onClick={goBack} />

        <h1 className="min-w-0 flex-1 truncate text-[15px] font-semibold leading-none">
          {heading}
        </h1>

        {isDesktop && primary && (
          <Button
            size="sm"
            variant="primary"
            labelKey={primary.labelKey}
            icon={primary.icon}
            disabled={primary.disabled}
            loading={primary.loading}
            onClick={primary.onClick}
          >
            {primary.label}
          </Button>
        )}

        {menu.length > 0 && (
          <IconButton
            icon={MoreHorizontal}
            ariaLabel={t("admin.shell.menu")}
            onClick={() => menuSheet.openSheet()}
          />
        )}
      </header>

      <main
        aria-label={t("admin.shell.content")}
        className="mx-auto max-w-[1100px] px-3 pt-2 pl-[calc(0.75rem+var(--tg-content-safe-area-left))] pr-[calc(0.75rem+var(--tg-content-safe-area-right))]"
        style={{ paddingBottom: "calc(var(--admin-bar-h, 0px) + var(--bottom-safe, 0px) + 12px)" }}
      >
        {children}

        {!isDesktop && primary && !native && (
          <ActionBar
            primary={{
              labelKey: primary.labelKey,
              label: primary.label,
              onClick: primary.onClick,
              disabled: primary.disabled,
              loading: primary.loading,
              icon: primary.icon,
            }}
          />
        )}
      </main>

      {!isDesktop && <AdminBar role={role} />}

      <SheetFrame
        open={menuSheet.open}
        onClose={menuSheet.close}
        titleKey="admin.shell.actions"
      >
        <ul className="space-y-1">
          {menu.map((item, index) => (
            <li key={item.labelKey ?? item.label ?? index}>
              <Button
                full
                size="md"
                variant={item.danger ? "danger" : "secondary"}
                icon={item.icon}
                labelKey={item.labelKey}
                disabled={item.disabled}
                onClick={() => {
                  menuSheet.close();
                  item.onClick();
                }}
                className="justify-start"
              >
                {item.label}
              </Button>
            </li>
          ))}
        </ul>
      </SheetFrame>

      <ConfirmDialogHost />
    </div>
  );
}
