import { create } from "zustand";

import type { TranslationKey, TranslationVars } from "../../../i18n";

/**
 * The admin panel has exactly one confirmation dialog, mounted by
 * `AdminLayout` (`<ConfirmDialogHost/>`). Anything that needs a confirmation
 * calls `requestConfirm(...)` and awaits a boolean — no per-page dialog state,
 * which is what `useConfirmedMutation` needs to keep its `{run, isPending}`
 * surface.
 */
export type ConfirmRequest = {
  titleKey: TranslationKey;
  descriptionKey?: TranslationKey;
  descriptionVars?: TranslationVars;
  confirmLabelKey?: TranslationKey;
  danger?: boolean;
};

type ConfirmState = {
  open: boolean;
  loading: boolean;
  request: ConfirmRequest | null;
  resolve: ((ok: boolean) => void) | null;
};

export const useConfirmStore = create<ConfirmState>(() => ({
  open: false,
  loading: false,
  request: null,
  resolve: null,
}));

/** Open the dialog; resolves `true` on confirm, `false` on cancel/close. */
export function requestConfirm(request: ConfirmRequest): Promise<boolean> {
  // A second request while one is open cancels the first: never leave a
  // pending promise behind.
  useConfirmStore.getState().resolve?.(false);
  return new Promise<boolean>((resolve) => {
    useConfirmStore.setState({ open: true, loading: false, request, resolve });
  });
}

/** Answer the open dialog. The host wires this to its buttons. */
export function settleConfirm(ok: boolean): void {
  const { resolve } = useConfirmStore.getState();
  if (ok) {
    // Keep the dialog up in a busy state until the caller closes it.
    useConfirmStore.setState({ loading: true, resolve: null });
  } else {
    useConfirmStore.setState({ open: false, loading: false, request: null, resolve: null });
  }
  resolve?.(ok);
}

/** Tear the dialog down once the confirmed work finished (or failed). */
export function closeConfirm(): void {
  useConfirmStore.getState().resolve?.(false);
  useConfirmStore.setState({ open: false, loading: false, request: null, resolve: null });
}
