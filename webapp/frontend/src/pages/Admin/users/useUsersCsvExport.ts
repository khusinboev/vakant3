import { useCallback, useState } from "react";

import { mintUsersExportLink } from "../../../api/admin";
import type { AdminUsersQuery } from "../../../api/adminTypes";
import useToast from "../../../hooks/useToast";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import { parseApiError } from "../../../lib/parseApiError";
import { useAuthStore } from "../../../store/auth";
import { haptic } from "../ui";
import { exportParams, fetchUsersCsv, usersCsvDownloadUrl } from "./api";

type DownloadFileParams = { url: string; file_name: string };

/** Bot API 8.0 `downloadFile`; not in the shared WebApp typings yet. */
type WebAppWithDownload = {
  isVersionAtLeast?: (version: string) => boolean;
  downloadFile?: (params: DownloadFileParams, callback?: (accepted: boolean) => void) => void;
};

function telegramDownloader(): WebAppWithDownload["downloadFile"] | null {
  const webApp = window.Telegram?.WebApp as WebAppWithDownload | undefined;
  if (!webApp?.downloadFile || !webApp.isVersionAtLeast?.("8.0")) return null;
  return webApp.downloadFile.bind(webApp);
}

function saveBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoked on the next tick: some WebViews start reading the URL after click().
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function fileName(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `users-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(
    now.getHours(),
  )}${pad(now.getMinutes())}.csv`;
}

/**
 * "Export CSV" for the Users list, with the list's current filters and sort.
 *
 * Inside Telegram (Bot API 8.0+) the file goes through
 * `Telegram.WebApp.downloadFile`, which needs a plain HTTPS URL: the panel
 * mints a 300 s link token over the filters (`POST /admin/users/export/link`)
 * and hands Telegram the single-use `/export/download.csv` link. Everywhere else
 * the authenticated client fetches the CSV as a Blob and an `<a download>`
 * saves it. The server allows 2 exports a minute; a 429 gets its own message.
 */
export function useUsersCsvExport(query: AdminUsersQuery): { run: () => void; isPending: boolean } {
  const t = useT();
  const toast = useToast();
  const { formatNumber } = useLocale();
  const [isPending, setIsPending] = useState(false);

  const run = useCallback(() => {
    if (isPending) return;
    setIsPending(true);
    const params = exportParams(query);
    const name = fileName();

    const work = async () => {
      const download = telegramDownloader();
      const actorId = useAuthStore.getState().user?.user_id;
      if (download && actorId) {
        const token = await mintUsersExportLink(params);
        download({ url: usersCsvDownloadUrl(params, actorId, token), file_name: name }, (accepted) => {
          if (accepted) haptic("success");
        });
        return;
      }
      const result = await fetchUsersCsv(params);
      saveBlob(result.blob, name);
      haptic("success");
      if (result.truncated) {
        toast.info(t("adminUsers.export.truncated", { count: formatNumber(result.rows) }));
      } else {
        toast.success(t("adminUsers.export.success", { count: formatNumber(result.rows) }));
      }
    };

    work()
      .catch((error: unknown) => {
        haptic("error");
        if (parseApiError(error).status === 429) toast.error(t("adminUsers.export.rateLimited"));
        else toast.apiError(error);
      })
      .finally(() => setIsPending(false));
  }, [isPending, query, t, toast, formatNumber]);

  return { run, isPending };
}

export default useUsersCsvExport;
