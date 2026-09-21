import { useState } from "react";
import { BookOpen, FolderOpen, Lightbulb } from "lucide-react";

import { useT } from "../../../i18n/useT";
import type { TranslationKey } from "../../../i18n";
import ArticlesTab from "../content/ArticlesTab";
import CategoriesTab from "../content/CategoriesTab";
import TipsTab from "../content/TipsTab";
import { isContentDirty, setContentDirty } from "../content/dirtyGuard";
import { requestConfirm } from "../hooks/useConfirm";

type SubTab = "articles" | "tips" | "categories";

const TABS: { id: SubTab; labelKey: TranslationKey; icon: typeof BookOpen }[] = [
  { id: "articles", labelKey: "adminContent.tab.articles", icon: BookOpen },
  { id: "tips", labelKey: "adminContent.tab.tips", icon: Lightbulb },
  { id: "categories", labelKey: "adminContent.tab.categories", icon: FolderOpen },
];

/**
 * Law articles / HR tips / categories CRUD (CONTRACT_P12 m007). Each sub-tab
 * owns its own list <-> editor state; switching sub-tabs while an editor has
 * unsaved changes asks first (see `content/dirtyGuard.ts`).
 */
export default function ContentPage() {
  const t = useT();
  const [subTab, setSubTab] = useState<SubTab>("articles");

  const switchTab = async (next: SubTab) => {
    if (next === subTab) return;
    if (isContentDirty()) {
      const ok = await requestConfirm({
        titleKey: "adminContent.editor.discardTitle",
        descriptionKey: "adminContent.editor.discardDesc",
        confirmLabelKey: "adminContent.editor.discardConfirm",
        danger: true,
      });
      if (!ok) return;
      setContentDirty(false);
    }
    setSubTab(next);
  };

  return (
    <div className="space-y-4">
      <div role="tablist" aria-label={t("adminContent.tabs.aria")} className="flex gap-1 rounded-xl bg-surfaceAlt p-1">
        {TABS.map(({ id, labelKey, icon: Icon }) => {
          const active = id === subTab;
          return (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => void switchTab(id)}
              className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${
                active ? "bg-primary text-primaryFg" : "text-muted hover:text-text"
              }`}
            >
              <Icon size={14} aria-hidden="true" />
              {t(labelKey)}
            </button>
          );
        })}
      </div>

      {subTab === "articles" && <ArticlesTab />}
      {subTab === "tips" && <TipsTab />}
      {subTab === "categories" && <CategoriesTab />}
    </div>
  );
}
