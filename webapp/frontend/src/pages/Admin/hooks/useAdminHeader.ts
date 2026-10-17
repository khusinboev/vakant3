import { useEffect, useSyncExternalStore, type ElementType } from "react";

import type { TranslationKey } from "../../../i18n";

export type AdminMenuItem = {
  /** Preferred: a translation key. `label` is for values that are already text. */
  labelKey?: TranslationKey;
  label?: string;
  icon?: ElementType;
  onClick: () => void;
  danger?: boolean;
  disabled?: boolean;
  /** Kept out of the menu entirely (role checks, state-dependent actions). */
  hidden?: boolean;
};

export type AdminPrimaryAction = {
  labelKey?: TranslationKey;
  label?: string;
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  icon?: ElementType;
};

export type AdminHeaderConfig = {
  /** Already translated title; `titleKey` is translated by the shell. */
  title?: string;
  titleKey?: TranslationKey;
  /**
   * `true` (default) — ‹ runs `useAdminBack().back()`.
   * A function — ‹ runs it instead (unsaved-changes guards).
   */
  back?: boolean | (() => void);
  /** The one primary action of the screen (MainButton on mobile). */
  primary?: AdminPrimaryAction;
  /** Everything else, behind the ⋯ menu. */
  menu?: AdminMenuItem[];
};

// The live config is a ref, not state: the click handlers change identity on
// every render of the page, but the header only needs to *re-render* when
// something visible changes. `version` is that signal.
const current: { config: AdminHeaderConfig | null } = { config: null };
let version = 0;
const listeners = new Set<() => void>();

function publish(): void {
  version += 1;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function signatureOf(config: AdminHeaderConfig): string {
  return JSON.stringify([
    config.title ?? null,
    config.titleKey ?? null,
    typeof config.back === "function" ? "fn" : (config.back ?? true),
    config.primary
      ? [
          config.primary.labelKey ?? null,
          config.primary.label ?? null,
          Boolean(config.primary.disabled),
          Boolean(config.primary.loading),
          Boolean(config.primary.icon),
        ]
      : null,
    (config.menu ?? []).map((item) => [
      item.labelKey ?? null,
      item.label ?? null,
      Boolean(item.danger),
      Boolean(item.disabled),
      Boolean(item.hidden),
      Boolean(item.icon),
    ]),
  ]);
}

/**
 * How a page declares its header. Call it once, near the top of the component:
 *
 *   useAdminHeader({
 *     title: user?.name ?? "",
 *     primary: { labelKey: "adminUsers.save", onClick: save, loading: save.isPending },
 *     menu: [{ labelKey: "adminUsers.ban", onClick: ban, danger: true }],
 *   });
 *
 * The title falls back to the registry label, ‹ is always rendered, and on a
 * phone inside Telegram `primary` becomes the native MainButton.
 */
export function useAdminHeader(config: AdminHeaderConfig): void {
  const signature = signatureOf(config);

  // Handlers must always be the latest ones, even between re-renders that do
  // not change the signature.
  current.config = config;

  useEffect(() => {
    current.config = config;
    publish();
    return () => {
      if (current.config === config) current.config = null;
      publish();
    };
    // `config` is intentionally not a dependency: only visible changes republish.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);
}

/** Read side, for `AdminShell` only. */
export function useAdminHeaderConfig(): AdminHeaderConfig | null {
  useSyncExternalStore(
    subscribe,
    () => version,
    () => version,
  );
  return current.config;
}

export default useAdminHeader;
