/**
 * Error codes only the Users endpoints return, translated in the adminUsers
 * namespace (the shared `error.<CODE>` dictionary does not know them).
 */
import { useCallback } from "react";

import useToast from "../../../hooks/useToast";
import type { TFunction, TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { parseApiError } from "../../../lib/parseApiError";
import { ROLE_LABEL_KEY, type AdminRole } from "../hooks/useAdminRole";

const USER_ERROR_KEY: Record<string, TranslationKey> = {
  CANNOT_TARGET_ADMIN: "adminUsers.error.CANNOT_TARGET_ADMIN",
  IDEMPOTENCY_CONFLICT: "adminUsers.error.IDEMPOTENCY_CONFLICT",
};

/** The translated text for a Users-only code, or `null` when the shared dictionary covers it. */
export function userErrorMessage(error: unknown, t: TFunction): string | null {
  const { code, params } = parseApiError(error);
  const key = USER_ERROR_KEY[code];
  if (!key) return null;
  const role = String(params.role ?? "") as AdminRole;
  const roleKey = ROLE_LABEL_KEY[role];
  return t(key, { role: roleKey ? t(roleKey) : role });
}

/**
 * Rethrow `error` with its Users-only translation as `detail.message`.
 *
 * For `useConfirmedMutation`, which toasts through the shared
 * `apiErrorMessage`: that falls back to `detail.message` for a code the
 * shared dictionary lacks, so the toast shows this text.
 */
export function localizeUserError(error: unknown, t: TFunction): never {
  const message = userErrorMessage(error, t);
  const response = (error as { response?: { data?: { detail?: unknown } } })?.response;
  const detail = response?.data?.detail;
  if (message && detail && typeof detail === "object") {
    (detail as Record<string, unknown>).message = message;
  }
  throw error;
}

/** `toast.apiError`, but with the Users-only codes translated. */
export function useUserErrorToast(): (error: unknown) => void {
  const t = useT();
  const toast = useToast();
  return useCallback(
    (error: unknown) => {
      const message = userErrorMessage(error, t);
      if (message) toast.error(message);
      else toast.apiError(error);
    },
    [t, toast],
  );
}
