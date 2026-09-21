import parseApiError from "../../../lib/parseApiError";
import type { TFunction } from "../../../i18n";

export type ContentFormErrors = Record<string, string>;

export type ContentErrorResult = {
  /** Keyed `"id"`, `"category_id"` or `"<field>.<lang>"` (e.g. `"title.ru"`). */
  fieldErrors: ContentFormErrors;
  /** Set when the error has nowhere to live inline (e.g. deleting a category in use). */
  toastMessage?: string;
  /** `true` when neither of the above applied — caller should fall back to `toast.apiError`. */
  unmapped: boolean;
};

/**
 * Maps the `admin_content.py` error codes (CONTENT_EXISTS, CONTENT_IN_USE,
 * VALIDATION_ERROR{field}, CONTENT_NOT_FOUND) onto inline form errors. These
 * codes are not in the shared `error.*` i18n namespace (owned by another
 * agent), so the messages live under `adminContent.error.*` instead.
 */
export function mapContentError(error: unknown, t: TFunction): ContentErrorResult {
  const parsed = parseApiError(error);

  if (parsed.code === "VALIDATION_ERROR" && typeof parsed.params.field === "string" && parsed.params.field) {
    return { fieldErrors: { [parsed.params.field]: t("adminContent.error.validation") }, unmapped: false };
  }
  if (parsed.code === "CONTENT_EXISTS") {
    return { fieldErrors: { id: t("adminContent.error.exists") }, unmapped: false };
  }
  if (parsed.code === "CONTENT_IN_USE") {
    return { fieldErrors: {}, toastMessage: t("adminContent.error.inUse"), unmapped: false };
  }
  if (parsed.code === "CONTENT_NOT_FOUND") {
    return { fieldErrors: {}, toastMessage: t("adminContent.error.notFound"), unmapped: false };
  }
  return { fieldErrors: {}, unmapped: true };
}
