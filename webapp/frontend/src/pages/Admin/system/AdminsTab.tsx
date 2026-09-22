import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, CheckCircle2, ShieldAlert, Trash2 } from "lucide-react";

import { addAdmin, adminKeys, listAdmins, removeAdmin, updateAdmin } from "../../../api/admin";
import type { AdminRow } from "../../../api/adminTypes";
import { useToast } from "../../../hooks/useToast";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import { isApiErrorCode } from "../../../lib/parseApiError";
import ErrorCard from "../components/ErrorCard";
import RoleGate from "../components/RoleGate";
import { ADMIN_ROLES, ROLE_LABEL_KEY, type AdminRole } from "../hooks/useAdminRole";
import { closeConfirm, requestConfirm } from "../hooks/useConfirm";
import { useHistorySheet } from "../hooks/useHistorySheet";
import { Button, EmptyState, IconButton, List, Sheet, Skeleton, StatusChip, TONE_CLASS, type Tone } from "../ui";

/** Shared with `SystemPage`'s header primary — same name keeps both in sync. */
export const ADMINS_ADD_SHEET = "system.admins.add";

const ROLE_TONE: Record<AdminRole, Tone> = {
  owner: "primary",
  admin: "info",
  moderator: "warning",
  viewer: "neutral",
};

const INPUT_CLS =
  "h-9 w-full rounded-xl border border-border bg-surface px-2.5 text-[13px] text-text placeholder:text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

function AdminListItem({
  row,
  pending,
  onRoleChange,
  onDisable,
  onEnable,
  onRemove,
}: {
  row: AdminRow;
  pending: boolean;
  onRoleChange: (role: AdminRole) => void;
  onDisable: () => void;
  onEnable: () => void;
  onRemove: () => void;
}) {
  const t = useT();
  const { formatDateTime } = useLocale();

  return (
    <li className="flex min-h-[56px] items-center gap-2 px-3 py-2">
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-medium text-text">
          {row.first_name || row.username || row.user_id}
        </p>
        <p className="truncate text-[11px] text-muted">
          #{row.user_id} · {formatDateTime(row.added_at)}
        </p>
      </div>

      <StatusChip
        status={row.disabled ? "disabled" : "active"}
        labelKey={row.disabled ? "admin.status.off" : "admin.status.on"}
      />

      <select
        value={row.role}
        disabled={pending}
        aria-label={t("adminSystem.admins.role")}
        onChange={(event) => onRoleChange(event.target.value as AdminRole)}
        className={`h-6 shrink-0 rounded-full border px-2 text-[11px] font-semibold disabled:opacity-50 ${TONE_CLASS[ROLE_TONE[row.role]]}`}
      >
        {ADMIN_ROLES.map((role) => (
          <option key={role} value={role}>
            {t(ROLE_LABEL_KEY[role])}
          </option>
        ))}
      </select>

      <IconButton
        size="sm"
        variant="ghost"
        icon={row.disabled ? CheckCircle2 : Ban}
        ariaLabel={t(row.disabled ? "adminSystem.admins.enable" : "adminSystem.admins.disable")}
        disabled={pending}
        onClick={row.disabled ? onEnable : onDisable}
      />
      <IconButton
        size="sm"
        variant="ghost"
        icon={Trash2}
        ariaLabel={t("adminSystem.admins.remove")}
        disabled={pending}
        onClick={onRemove}
        className="text-danger hover:bg-danger/10"
      />
    </li>
  );
}

function AdminsRoster() {
  const t = useT();
  const toast = useToast();
  const queryClient = useQueryClient();
  const sheet = useHistorySheet(ADMINS_ADD_SHEET);

  const [telegramId, setTelegramId] = useState("");
  const [newRole, setNewRole] = useState<AdminRole>("admin");
  const [idError, setIdError] = useState<string | null>(null);
  const [pendingUserId, setPendingUserId] = useState<number | null>(null);

  const list = useQuery({
    queryKey: adminKeys.admins(),
    queryFn: listAdmins,
    retry: false,
  });

  const invalidate = () => void queryClient.invalidateQueries({ queryKey: adminKeys.admins() });

  const addMutation = useMutation({
    mutationFn: () => addAdmin({ user_id: Number(telegramId), role: newRole }),
    onSuccess: () => {
      toast.success(t("adminSystem.admins.addSuccess"));
      setTelegramId("");
      setNewRole("admin");
      sheet.close();
      invalidate();
    },
    onError: (error) => {
      if (isApiErrorCode(error, "ADMIN_EXISTS")) toast.error(t("adminSystem.admins.errorExists"));
      else toast.apiError(error);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (vars: { userId: number; body: { role?: AdminRole; disabled?: boolean } }) =>
      updateAdmin(vars.userId, vars.body),
    onMutate: (vars) => setPendingUserId(vars.userId),
    onSuccess: () => {
      toast.success(t("adminSystem.admins.updated"));
      invalidate();
    },
    onError: (error) => toast.apiError(error),
    onSettled: () => setPendingUserId(null),
  });

  const removeMutation = useMutation({
    mutationFn: (userId: number) => removeAdmin(userId),
    onMutate: (userId) => setPendingUserId(userId),
    onSuccess: () => {
      toast.success(t("adminSystem.admins.removeSuccess"));
      invalidate();
    },
    onError: (error) => {
      if (isApiErrorCode(error, "CANNOT_REMOVE_LAST_OWNER")) toast.error(t("adminSystem.admins.errorLastOwner"));
      else toast.apiError(error);
    },
    onSettled: () => setPendingUserId(null),
  });

  const handleAdd = () => {
    const id = Number(telegramId);
    if (!telegramId.trim() || !Number.isInteger(id) || id <= 0) {
      setIdError(t("adminSystem.admins.invalidId"));
      return;
    }
    setIdError(null);
    addMutation.mutate();
  };

  const nameOf = (row: AdminRow) => row.first_name || row.username || String(row.user_id);

  const handleDisable = async (row: AdminRow) => {
    const ok = await requestConfirm({
      titleKey: "adminSystem.admins.disableConfirmTitle",
      descriptionKey: "adminSystem.admins.disableConfirmDesc",
      descriptionVars: { name: nameOf(row), id: row.user_id },
      danger: true,
    });
    if (!ok) return;
    try {
      await updateMutation.mutateAsync({ userId: row.user_id, body: { disabled: true } });
    } catch {
      // toasted by the mutation's onError
    } finally {
      closeConfirm();
    }
  };

  const handleRemove = async (row: AdminRow) => {
    const ok = await requestConfirm({
      titleKey: "adminSystem.admins.removeConfirmTitle",
      descriptionKey: "adminSystem.admins.removeConfirmDesc",
      descriptionVars: { name: nameOf(row), id: row.user_id },
      danger: true,
    });
    if (!ok) return;
    try {
      await removeMutation.mutateAsync(row.user_id);
    } catch {
      // toasted by the mutation's onError
    } finally {
      closeConfirm();
    }
  };

  const items = list.data?.items ?? [];

  return (
    <div className="space-y-3">
      {list.isLoading && <Skeleton rows={4} />}
      {list.isError && <ErrorCard error={list.error} onRetry={() => void list.refetch()} />}
      {!list.isLoading && !list.isError && (
        items.length === 0 ? (
          <EmptyState icon={ShieldAlert} labelKey="admin.table.empty" />
        ) : (
          <List>
            {items.map((row) => (
              <AdminListItem
                key={row.user_id}
                row={row}
                pending={pendingUserId === row.user_id}
                onRoleChange={(role) => updateMutation.mutate({ userId: row.user_id, body: { role } })}
                onDisable={() => void handleDisable(row)}
                onEnable={() => updateMutation.mutate({ userId: row.user_id, body: { disabled: false } })}
                onRemove={() => void handleRemove(row)}
              />
            ))}
          </List>
        )
      )}

      <Sheet
        name={ADMINS_ADD_SHEET}
        titleKey="adminSystem.admins.addTitle"
        footer={
          <Button
            size="md"
            full
            variant="primary"
            labelKey="adminSystem.admins.addSubmit"
            loading={addMutation.isPending}
            onClick={handleAdd}
          />
        }
      >
        <div className="space-y-3">
          <label className="block">
            <span className="mb-1 block text-[11px] font-semibold text-muted">
              {t("adminSystem.admins.telegramId")}
            </span>
            <input
              type="text"
              inputMode="numeric"
              value={telegramId}
              onChange={(event) => {
                setTelegramId(event.target.value.replace(/[^\d]/g, ""));
                setIdError(null);
              }}
              placeholder="123456789"
              className={INPUT_CLS}
            />
            {idError && <span className="mt-1 block text-[11px] text-danger">{idError}</span>}
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] font-semibold text-muted">{t("adminSystem.admins.role")}</span>
            <select
              value={newRole}
              onChange={(event) => setNewRole(event.target.value as AdminRole)}
              className={INPUT_CLS}
            >
              {ADMIN_ROLES.map((role) => (
                <option key={role} value={role}>
                  {t(ROLE_LABEL_KEY[role])}
                </option>
              ))}
            </select>
          </label>
        </div>
      </Sheet>
    </div>
  );
}

/** Admins management — owner only; everyone else sees why they can't get in. */
export default function AdminsTab() {
  return (
    <RoleGate
      min="owner"
      fallback={
        <EmptyState
          icon={ShieldAlert}
          labelKey="adminSystem.admins.ownerOnlyTitle"
          descriptionKey="adminSystem.admins.ownerOnlyDesc"
        />
      }
    >
      <AdminsRoster />
    </RoleGate>
  );
}
