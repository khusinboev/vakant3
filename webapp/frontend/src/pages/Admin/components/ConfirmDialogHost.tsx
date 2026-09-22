import { useEffect, useRef } from "react";

import { useHistorySheet } from "../hooks/useHistorySheet";
import { closeConfirm, settleConfirm, useConfirmStore } from "../hooks/useConfirm";
import ConfirmDialog from "./ConfirmDialog";

const SHEET = "admin.confirm";

/**
 * Mounted once by `AdminShell`. Every `useConfirmedMutation` in the panel
 * drives this single dialog, so pages need no dialog state of their own — and
 * the dialog is a history entry, so back / Esc / the Telegram BackButton
 * cancel it instead of leaving the page (spec §1.1).
 */
export default function ConfirmDialogHost() {
  const open = useConfirmStore((s) => s.open);
  const loading = useConfirmStore((s) => s.loading);
  const request = useConfirmStore((s) => s.request);
  const sheet = useHistorySheet(SHEET);
  const pushed = useRef(false);

  useEffect(() => {
    if (open && sheet.open) {
      pushed.current = true;
      return;
    }
    if (open && !sheet.open) {
      if (pushed.current) {
        // The entry was popped (back / Esc / backdrop): treat it as a cancel.
        pushed.current = false;
        closeConfirm();
      } else {
        pushed.current = true;
        sheet.openSheet();
      }
      return;
    }
    if (!open && sheet.open && pushed.current) {
      pushed.current = false;
      sheet.close();
    }
    // `sheet` is recreated per render; only its `open` flag matters here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, sheet.open]);

  if (!request) return null;

  return (
    <ConfirmDialog
      open={open && sheet.open}
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
