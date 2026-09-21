import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, CheckCircle2, ShieldAlert, Trash2, UserPlus } from "lucide-react";

import { addAdmin, adminKeys, listAdmins, removeAdmin, updateAdmin } from "../../../api/admin";
import type { AdminRow } from "../../../api/adminTypes";
import Field, { INPUT_CLS } from "../../../components/ui/Field";
import { useToast } from "../../../hooks/useToast";
import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import { isApiErrorCode } from "../../../lib/parseApiError";
import DataTable, { type Column } from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import RoleGate from "../components/RoleGate";
import StyledSelect from "../../../components/ui/StyledSelect";
import { closeConfirm, requestConfirm } from "../hooks/useConfirm";
import { ADMIN_ROLES, ROLE_LABEL_KEY, type AdminRole } from "../hooks/useAdminRole";

function AdminsRoster() {
  const t = useT();
  const toast = useToast();
  const { formatDateTime } = useLocale();
  const queryClient = useQueryClient();

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

  const handleRemove = async (row: AdminRow) => {
    const ok = await requestConfirm({
      titleKey: "adminSystem.admins.removeConfirmTitle",
      descriptionKey: "adminSystem.admins.removeConfirmDesc",
      descriptionVars: { id: row.user_id, name: row.first_name || row.username || String(row.user_id) },
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

  const columns: Column<AdminRow>[] = [
    {
      key: "user",
      labelKey: "adminSystem.admins.col.user",
      render: (row) => (
        <span className="flex flex-col">
          <span className="font-medium text-text">{row.first_name || row.username || row.user_id}</span>
          <span className="text-xs text-muted">{row.user_id}</span>
        </span>
      ),
    },
    {
      key: "role",
      labelKey: "adminSystem.admins.col.role",
      render: (row) => (
        <StyledSelect
          value={row.role}
          disabled={pendingUserId === row.user_id}
          aria-label={t("adminSystem.admins.col.role")}
          onChange={(event) =>
            updateMutation.mutate({ userId: row.user_id, body: { role: event.target.value as AdminRole } })
          }
          className="min-w-[8rem]"
        >
          {ADMIN_ROLES.map((role) => (
            <option key={role} value={role}>
              {t(ROLE_LABEL_KEY[role])}
            </option>
          ))}
        </StyledSelect>
      ),
    },
    {
      key: "addedBy",
      labelKey: "adminSystem.admins.col.addedBy",
      hideOnCard: true,
      render: (row) => (row.added_by ?? "—"),
    },
    {
      key: "addedAt",
      labelKey: "adminSystem.admins.col.addedAt",
      hideOnCard: true,
      render: (row) => formatDateTime(row.added_at),
    },
    {
      key: "status",
      labelKey: "adminSystem.admins.col.status",
      render: (row) => (
        <span
          className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${
            row.disabled ? "bg-danger/10 text-danger" : "bg-success/10 text-success"
          }`}
        >
          {t(row.disabled ? "admin.status.off" : "admin.status.on")}
        </span>
      ),
    },
    {
      key: "actions",
      labelKey: "adminSystem.admins.col.actions",
      align: "right",
      render: (row) => (
        <div className="flex items-center justify-end gap-1.5">
          <button
            type="button"
            disabled={pendingUserId === row.user_id}
            aria-label={t(row.disabled ? "adminSystem.admins.enable" : "adminSystem.admins.disable")}
            title={t(row.disabled ? "adminSystem.admins.enable" : "adminSystem.admins.disable")}
            onClick={() =>
              updateMutation.mutate({ userId: row.user_id, body: { disabled: !row.disabled } })
            }
            className="tap-target rounded-lg border border-border p-1.5 text-muted hover:text-text disabled:opacity-50"
          >
            {row.disabled ? <CheckCircle2 size={14} aria-hidden="true" /> : <Ban size={14} aria-hidden="true" />}
          </button>
          <button
            type="button"
            disabled={pendingUserId === row.user_id}
            aria-label={t("adminSystem.admins.remove")}
            title={t("adminSystem.admins.remove")}
            onClick={() => void handleRemove(row)}
            className="tap-target rounded-lg border border-danger/40 p-1.5 text-danger hover:bg-danger/10 disabled:opacity-50"
          >
            <Trash2 size={14} aria-hidden="true" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <section className="card space-y-3 p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text">
          <UserPlus size={15} aria-hidden="true" className="text-primary" />
          {t("adminSystem.admins.addTitle")}
        </h2>
        <div className="grid gap-3 sm:grid-cols-[1fr_10rem_auto]">
          <Field label={t("adminSystem.admins.telegramId")} error={idError ?? undefined}>
            <input
              type="text"
              inputMode="numeric"
              className={INPUT_CLS}
              value={telegramId}
              onChange={(event) => {
                setTelegramId(event.target.value.replace(/[^\d]/g, ""));
                setIdError(null);
              }}
              placeholder="123456789"
            />
          </Field>
          <Field label={t("adminSystem.admins.role")}>
            <StyledSelect
              value={newRole}
              onChange={(event) => setNewRole(event.target.value as AdminRole)}
            >
              {ADMIN_ROLES.map((role) => (
                <option key={role} value={role}>
                  {t(ROLE_LABEL_KEY[role])}
                </option>
              ))}
            </StyledSelect>
          </Field>
          <div className="flex items-end">
            <button
              type="button"
              disabled={addMutation.isPending}
              onClick={handleAdd}
              className="tap-target w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primaryFg disabled:opacity-60 sm:w-auto"
            >
              {t("adminSystem.admins.addSubmit")}
            </button>
          </div>
        </div>
      </section>

      <DataTable
        columns={columns}
        rows={list.data?.items ?? []}
        getRowId={(row) => row.user_id}
        loading={list.isLoading}
        error={list.error}
        onRetry={() => void list.refetch()}
        emptyKey="admin.table.empty"
        captionKey="adminSystem.admins.title"
      />
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
