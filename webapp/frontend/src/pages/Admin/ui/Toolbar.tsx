import type { ElementType, ReactNode } from "react";
import { MoreHorizontal } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { useHistorySheet } from "../hooks/useHistorySheet";
import { useIsDesktop } from "../hooks/useMediaQuery";
import Button, { IconButton } from "./Button";
import { SheetFrame } from "./Sheet";

export type ToolbarItem = {
  id: string;
  labelKey?: TranslationKey;
  label?: string;
  icon?: ElementType;
  onClick: () => void;
  danger?: boolean;
  disabled?: boolean;
  hidden?: boolean;
};

export type ToolbarProps = {
  items?: ToolbarItem[];
  /** Rendered before the items (a search box, a segmented control). */
  children?: ReactNode;
  /** How many items stay inline on a phone. Default 2. */
  max?: number;
  /** History-sheet name for the overflow menu. */
  name?: string;
  className?: string;
};

/**
 * A row of small actions that folds the extras into a ⋯ sheet on phones
 * (spec §3). Desktop shows everything inline.
 */
export default function Toolbar({
  items = [],
  children,
  max = 2,
  name = "toolbar",
  className = "",
}: ToolbarProps) {
  const t = useT();
  const isDesktop = useIsDesktop();
  const sheet = useHistorySheet(name);

  const visible = items.filter((item) => !item.hidden);
  const inline = isDesktop ? visible : visible.slice(0, max);
  const overflow = isDesktop ? [] : visible.slice(max);

  return (
    <div className={`flex items-center gap-1.5 ${className}`}>
      {children}
      {inline.map((item) => (
        <Button
          key={item.id}
          size="sm"
          variant={item.danger ? "danger" : "secondary"}
          icon={item.icon}
          labelKey={item.labelKey}
          disabled={item.disabled}
          onClick={item.onClick}
        >
          {item.label}
        </Button>
      ))}

      {overflow.length > 0 && (
        <>
          <IconButton
            icon={MoreHorizontal}
            ariaLabel={t("admin.toolbar.moreAria")}
            onClick={() => sheet.openSheet()}
          />
          <SheetFrame
            open={sheet.open}
            onClose={sheet.close}
            titleKey="admin.toolbar.more"
            size="auto"
          >
            <ul className="space-y-1">
              {overflow.map((item) => (
                <li key={item.id}>
                  <Button
                    full
                    size="md"
                    variant={item.danger ? "danger" : "secondary"}
                    icon={item.icon}
                    labelKey={item.labelKey}
                    disabled={item.disabled}
                    onClick={() => {
                      sheet.close();
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
        </>
      )}
    </div>
  );
}
