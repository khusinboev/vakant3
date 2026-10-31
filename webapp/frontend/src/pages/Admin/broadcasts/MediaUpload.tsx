import { useRef, useState } from "react";
import { FileText, Trash2, Upload } from "lucide-react";

import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import useToast from "../../../hooks/useToast";
import type { UploadResult } from "../../../api/adminTypes";
import { Button, IconButton, ProgressBar } from "../ui";
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
  // Not an overlay: the drag-hover highlight of the drop zone (spec §3 rule 3).
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
      {value ? (
        <div className="flex items-center gap-2 rounded-xl bg-surfaceAlt px-2.5 py-2">
          <FileText size={15} aria-hidden="true" className="shrink-0 text-primary" />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-medium text-text">{value.path}</span>
            <span className="block truncate text-[11px] text-muted">
              {value.mime} · {formatNumber(Math.round(value.size / 1024))} KB
            </span>
          </span>
          <Button
            size="sm"
            variant="secondary"
            labelKey="adminBroadcasts.media.replace"
            onClick={() => inputRef.current?.click()}
          />
          <IconButton
            icon={Trash2}
            variant="ghost"
            ariaLabel={t("adminBroadcasts.media.remove")}
            onClick={() => onChange(null)}
          />
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
          className={`flex flex-col items-center gap-1.5 rounded-xl border border-dashed p-3 text-center transition-colors ${
            dragging ? "border-primary bg-primary/5" : "border-border"
          }`}
        >
          <Upload size={16} className="text-muted" aria-hidden="true" />
          <p className="text-[13px] text-text">{t("adminBroadcasts.media.drop")}</p>
          <Button
            size="sm"
            variant="secondary"
            labelKey="adminBroadcasts.media.browse"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
          />
        </div>
      )}

      {busy && (
        <div className="space-y-1" aria-live="polite">
          <ProgressBar
            value={percent ?? 0}
            label={t("adminBroadcasts.media.uploading", { percent: percent ?? 0 })}
          />
          <p className="text-[11px] tabular-nums text-muted">
            {t("adminBroadcasts.media.uploading", { percent: percent ?? 0 })}
          </p>
        </div>
      )}

      <p className="text-[11px] text-muted">{t("adminBroadcasts.media.hint")}</p>

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
