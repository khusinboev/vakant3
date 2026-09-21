import { useRef, useState } from "react";
import { FileText, Trash2, Upload } from "lucide-react";

import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import useToast from "../../../hooks/useToast";
import type { UploadResult } from "../../../api/adminTypes";
import {
  ACCEPT_ATTRIBUTE,
  MAX_UPLOAD_BYTES,
  isAcceptedFile,
  uploadMediaWithProgress,
} from "./api";

export type MediaUploadProps = {
  value: UploadResult | null;
  onChange: (value: UploadResult | null) => void;
};

/**
 * Drag/drop or picker → `POST /api/admin/uploads` with a progress bar.
 *
 * Size and extension are checked here too, but only as a courtesy: the server
 * decides the real type from the file's magic bytes
 * (`webapp/core/uploads.py`), so a renamed file still gets rejected there.
 */
export default function MediaUpload({ value, onChange }: MediaUploadProps) {
  const t = useT();
  const { formatNumber } = useLocale();
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [percent, setPercent] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);

  const upload = async (file: File) => {
    if (file.size > MAX_UPLOAD_BYTES) {
      toast.error(t("adminBroadcasts.media.tooLarge"));
      return;
    }
    if (!isAcceptedFile(file)) {
      toast.error(t("adminBroadcasts.media.badType"));
      return;
    }
    setPercent(0);
    try {
      const result = await uploadMediaWithProgress(file, setPercent);
      onChange(result);
      toast.success(t("adminBroadcasts.media.uploaded"));
    } catch (error) {
      toast.apiError(error);
    } finally {
      setPercent(null);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const busy = percent !== null;

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-muted">{t("adminBroadcasts.media.label")}</p>

      {value ? (
        <div className="flex items-center gap-3 rounded-xl border border-border bg-surface p-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surfaceAlt text-primary">
            <FileText size={16} aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-text">{value.path}</p>
            <p className="text-xs text-muted">
              {value.mime} · {formatNumber(Math.round(value.size / 1024))} KB
            </p>
          </div>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium text-text hover:bg-surfaceAlt focus:outline-none focus:ring-2 focus:ring-primary/40"
          >
            {t("adminBroadcasts.media.replace")}
          </button>
          <button
            type="button"
            onClick={() => onChange(null)}
            aria-label={t("adminBroadcasts.media.remove")}
            className="rounded-lg p-1.5 text-muted hover:bg-surfaceAlt hover:text-danger focus:outline-none focus:ring-2 focus:ring-primary/40"
          >
            <Trash2 size={15} aria-hidden="true" />
          </button>
        </div>
      ) : (
        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            const file = event.dataTransfer.files?.[0];
            if (file) void upload(file);
          }}
          className={`rounded-xl border border-dashed p-5 text-center transition-colors ${
            dragging ? "border-primary bg-primary/5" : "border-border bg-surface"
          }`}
        >
          <Upload size={20} className="mx-auto text-muted" aria-hidden="true" />
          <p className="mt-2 text-sm text-text">{t("adminBroadcasts.media.drop")}</p>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={busy}
            className="mt-2 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-text hover:bg-surfaceAlt focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50"
          >
            {t("adminBroadcasts.media.browse")}
          </button>
        </div>
      )}

      {busy && (
        <div className="space-y-1" aria-live="polite">
          <div
            className="h-1.5 w-full overflow-hidden rounded-full bg-surfaceAlt"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent ?? 0}
          >
            <span
              className="block h-full bg-primary transition-[width]"
              style={{ width: `${percent ?? 0}%` }}
            />
          </div>
          <p className="text-xs text-muted">
            {t("adminBroadcasts.media.uploading", { percent: percent ?? 0 })}
          </p>
        </div>
      )}

      <p className="text-xs text-muted">{t("adminBroadcasts.media.hint")}</p>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_ATTRIBUTE}
        className="sr-only"
        aria-label={t("adminBroadcasts.media.browse")}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void upload(file);
        }}
      />
    </div>
  );
}
