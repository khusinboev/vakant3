import { useRef, useState } from "react";
import { Check, ImageIcon, Loader2, Upload } from "lucide-react";

import useToast from "../../../hooks/useToast";
import { useT } from "../../../i18n/useT";
import { resizeToDataUrl } from "../lib/photo";

export type PhotoUploadProps = {
  /** Data URI, or "" when no photo is set. */
  value: string;
  onChange: (dataUrl: string) => void;
};

/** Picks a profile picture and stores it as a small JPEG data URI. */
export default function PhotoUpload({ value, onChange }: PhotoUploadProps) {
  const t = useT();
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const handleFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      onChange(await resizeToDataUrl(file));
    } catch {
      toast.error(t("resume.photo.error"));
    } finally {
      setUploading(false);
      // Reset so the same file can be picked again.
      event.target.value = "";
    }
  };

  return (
    <div className="rounded-2xl border border-warning/30 bg-warning/10 p-4">
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(event) => void handleFile(event)}
      />

      <div className="mb-3 flex items-center gap-2">
        <ImageIcon size={15} className="text-warning" />
        <p className="text-xs font-bold text-text">{t("resume.photo.title")}</p>
        <span className="ml-auto text-[9px] font-medium text-muted">({t("common.optional")})</span>
      </div>

      {value ? (
        <div className="flex items-center gap-3">
          <div className="h-16 w-16 shrink-0 overflow-hidden rounded-xl border-2 border-warning/40 bg-surface">
            <img
              src={value}
              alt={t("resume.photo.alt")}
              className="h-full w-full object-cover"
              onError={() => onChange("")}
            />
          </div>
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-1 text-[11px] font-semibold text-success">
              <Check size={11} /> {t("resume.photo.included")}
            </p>
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                className="rounded-lg bg-warning/20 px-2.5 py-1 text-[10px] font-semibold text-warning transition-colors"
                onClick={() => inputRef.current?.click()}
              >
                {t("resume.photo.replace")}
              </button>
              <button
                type="button"
                className="rounded-lg bg-danger/10 px-2.5 py-1 text-[10px] font-semibold text-danger transition-colors"
                onClick={() => onChange("")}
              >
                {t("resume.photo.remove")}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <button
          type="button"
          className="tap-target flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-warning/40 bg-surface/60 py-5 transition-colors hover:bg-surface disabled:opacity-60"
          disabled={uploading}
          onClick={() => inputRef.current?.click()}
        >
          {uploading ? (
            <Loader2 size={22} className="animate-spin text-warning" />
          ) : (
            <Upload size={22} className="text-warning" />
          )}
          <span className="text-xs font-semibold text-warning">
            {uploading ? t("resume.photo.uploading") : t("resume.photo.pick")}
          </span>
          <span className="text-[9px] text-muted">{t("resume.photo.formats")}</span>
        </button>
      )}
    </div>
  );
}
