import { useEffect, useMemo } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { create } from "zustand";

import parseApiError from "../lib/parseApiError";
import { useT } from "../i18n/useT";
import type { TranslationKey } from "../i18n";

export type ToastKind = "success" | "error" | "info";

export type Toast = {
  id: number;
  message: string;
  kind: ToastKind;
  duration: number;
};

type ToastState = {
  toasts: Toast[];
  push: (message: string, kind?: ToastKind, duration?: number) => number;
  dismiss: (id: number) => void;
  clear: () => void;
};

let nextId = 1;

/** Store-backed so `useToast()` works anywhere without a context provider. */
const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (message, kind = "info", duration = 3500) => {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts, { id, message, kind, duration }] }));
    return id;
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  clear: () => set({ toasts: [] }),
}));

export type ToastApi = {
  show: (message: string, kind?: ToastKind, duration?: number) => number;
  success: (message: string) => number;
  error: (message: string) => number;
  info: (message: string) => number;
  /** Translate an axios/API error through `parseApiError` and show it. */
  apiError: (error: unknown) => number;
  dismiss: (id: number) => void;
};

/**
 * Toast API. Render `<ToastHost />` once (it lives in App).
 *
 *   const toast = useToast();
 *   toast.success(t("wallet.activated"));
 *   toast.apiError(err);   // parses the code and translates it
 */
export function useToast(): ToastApi {
  const push = useToastStore((s) => s.push);
  const dismiss = useToastStore((s) => s.dismiss);
  const t = useT();

  // Stable across renders (it only changes with the language), so it is safe
  // to list in a useEffect dependency array.
  return useMemo(
    () => ({
      show: push,
      success: (message: string) => push(message, "success"),
      error: (message: string) => push(message, "error"),
      info: (message: string) => push(message, "info"),
      apiError: (error: unknown) => {
        const parsed = parseApiError(error);
        const key = `error.${parsed.code}` as TranslationKey;
        let text = t(key, parsed.params as Record<string, string | number>);
        if (text === key) text = parsed.message || t("error.UNKNOWN");
        return push(text, "error", 5000);
      },
      dismiss,
    }),
    [push, dismiss, t],
  );
}

const KIND_STYLES: Record<ToastKind, string> = {
  success: "border-success/40 bg-success/10 text-success",
  error: "border-danger/40 bg-danger/10 text-danger",
  info: "border-border bg-surface text-text",
};

const KIND_ICONS: Record<ToastKind, typeof Info> = {
  success: CheckCircle2,
  error: AlertTriangle,
  info: Info,
};

function ToastItem({ toast }: { toast: Toast }) {
  const dismiss = useToastStore((s) => s.dismiss);
  const Icon = KIND_ICONS[toast.kind];

  useEffect(() => {
    if (toast.duration <= 0) return;
    const timer = setTimeout(() => dismiss(toast.id), toast.duration);
    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, dismiss]);

  return (
    <div
      role="status"
      className={`toast-enter pointer-events-auto flex w-full items-start gap-2 rounded-2xl border px-3 py-2.5 text-sm shadow-lg backdrop-blur ${KIND_STYLES[toast.kind]}`}
    >
      <Icon size={16} className="mt-0.5 shrink-0" />
      <span className="min-w-0 flex-1 whitespace-pre-wrap break-words">{toast.message}</span>
      <button
        type="button"
        aria-label="close"
        className="shrink-0 rounded-full p-0.5 opacity-70"
        onClick={() => dismiss(toast.id)}
      >
        <X size={14} />
      </button>
    </div>
  );
}

/** Mount once near the app root. Renders into a portal above everything. */
export function ToastHost() {
  const toasts = useToastStore((s) => s.toasts);
  if (typeof document === "undefined" || toasts.length === 0) return null;

  return createPortal(
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 top-0 z-[100] mx-auto flex w-full max-w-md flex-col gap-2 px-4 pt-[calc(0.75rem+var(--tg-content-safe-area-top))]"
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>,
    document.body,
  );
}

export default useToast;
