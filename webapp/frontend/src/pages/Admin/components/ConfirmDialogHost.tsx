import ConfirmDialog from "./ConfirmDialog";
import { closeConfirm, settleConfirm, useConfirmStore } from "../hooks/useConfirm";

/**
 * Mounted once by `AdminLayout`. Every `useConfirmedMutation` in the panel
 * drives this single dialog, so pages need no dialog state of their own.
 */
export default function ConfirmDialogHost() {
  const open = useConfirmStore((s) => s.open);
  const loading = useConfirmStore((s) => s.loading);
  const request = useConfirmStore((s) => s.request);

  if (!open || !request) return null;

  return (
    <ConfirmDialog
      open={open}
      titleKey={request.titleKey}
      descriptionKey={request.descriptionKey}
      descriptionVars={request.descriptionVars}
      confirmLabelKey={request.confirmLabelKey}
      danger={request.danger}
      loading={loading}
      onConfirm={() => settleConfirm(true)}
      onClose={() => closeConfirm()}
    />
  );
}
