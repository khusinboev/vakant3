import { useCallback, useState } from "react";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";

import useToast from "../../../hooks/useToast";
import { useT } from "../../../i18n/useT";
import type { TranslationKey, TranslationVars } from "../../../i18n";
import { confirmAction } from "../../../api/admin";
import { closeConfirm, requestConfirm } from "./useConfirm";
import { haptic } from "./useMainButton";

export type ConfirmedMutationOptions<TBody, TResult> = {
  /** Server-side action name, e.g. `"users.balance"` (must match the route). */
  action: string;
  /** Which keys of `params` go into the token hash — the endpoint's param_keys. */
  paramKeys: string[];
  /** Performs the request. The token must be sent as `X-Confirm-Token`. */
  mutationFn: (body: TBody, token: string) => Promise<TResult>;
  /** Query keys invalidated on success (prefix match, e.g. `["admin","users"]`). */
  invalidate?: QueryKey[];
  titleKey?: TranslationKey;
  descriptionKey?: TranslationKey;
  confirmLabelKey?: TranslationKey;
  danger?: boolean;
  /** Toasted on success. */
  successKey?: TranslationKey;
  onSuccess?: (result: TResult) => void;
  onError?: (error: unknown) => void;
};

export type ConfirmedMutation<TBody, TResult> = {
  /**
   * Ask for confirmation, mint the token, run the request.
   * `params` feeds the confirm token (only `paramKeys` are sent) and the
   * dialog description; `body` is the request payload (defaults to `params`).
   * Resolves `undefined` when the user cancelled or the request failed.
   */
  run: (
    params: Record<string, unknown>,
    body?: TBody,
    descriptionVars?: TranslationVars,
  ) => Promise<TResult | undefined>;
  isPending: boolean;
};

function pick(params: Record<string, unknown>, keys: string[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const key of keys) out[key] = params[key];
  return out;
}

/**
 * The confirm-token flow in one hook (CONTRACT_P0 `require_confirmation`):
 * dialog -> `POST /admin/confirm` -> the real request with the token header.
 *
 *   const ban = useConfirmedMutation({
 *     action: "users.ban", paramKeys: ["user_id"], danger: true,
 *     titleKey: "adminUsers.ban.confirmTitle",
 *     invalidate: [["admin", "users"]],
 *     mutationFn: (body, token) => banUser(body, token),
 *   });
 *   ban.run({ user_id: id }, { user_id: id, banned: true });
 */
export function useConfirmedMutation<TBody = Record<string, unknown>, TResult = unknown>(
  options: ConfirmedMutationOptions<TBody, TResult>,
): ConfirmedMutation<TBody, TResult> {
  const toast = useToast();
  const t = useT();
  const queryClient = useQueryClient();
  const [isPending, setIsPending] = useState(false);

  const {
    action,
    paramKeys,
    mutationFn,
    invalidate,
    titleKey = "admin.confirm.title",
    descriptionKey,
    confirmLabelKey = "admin.confirm.confirm",
    danger,
    successKey,
    onSuccess,
    onError,
  } = options;

  const run = useCallback(
    async (
      params: Record<string, unknown>,
      body?: TBody,
      descriptionVars?: TranslationVars,
    ): Promise<TResult | undefined> => {
      const ok = await requestConfirm({
        titleKey,
        descriptionKey,
        descriptionVars,
        confirmLabelKey,
        danger,
      });
      if (!ok) return undefined;

      setIsPending(true);
      try {
        const token = await confirmAction(action, pick(params, paramKeys));
        const result = await mutationFn((body ?? params) as TBody, token);
        for (const key of invalidate ?? []) {
          void queryClient.invalidateQueries({ queryKey: key });
        }
        haptic("success");
        if (successKey) toast.success(t(successKey));
        onSuccess?.(result);
        return result;
      } catch (error) {
        haptic("error");
        toast.apiError(error);
        onError?.(error);
        return undefined;
      } finally {
        setIsPending(false);
        closeConfirm();
      }
    },
    [
      action,
      paramKeys,
      mutationFn,
      invalidate,
      titleKey,
      descriptionKey,
      confirmLabelKey,
      danger,
      successKey,
      onSuccess,
      onError,
      queryClient,
      toast,
      t,
    ],
  );

  return { run, isPending };
}

export default useConfirmedMutation;
