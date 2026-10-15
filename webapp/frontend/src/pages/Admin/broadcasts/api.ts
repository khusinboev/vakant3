/**
 * Two local fetchers the shared client in `src/api/admin.ts` cannot provide:
 *
 * 1. `createBroadcastWithToken` — `createBroadcast()` mints its own confirm
 *    token internally, which would bypass the global confirm dialog. The page
 *    drives the flow through `useConfirmedMutation`, so it needs a variant
 *    that *accepts* the token instead of minting one.
 * 2. `uploadMediaWithProgress` — `uploadBroadcastMedia()` has no progress
 *    callback, and a 20 MB upload over a phone connection needs a bar.
 * 3. Pause / resume / the stage-B detail shape (error kinds, retry state) —
 *    page-local so the shared `adminTypes.ts` stays untouched.
 *
 * Everything else (list, preview, queue) is imported straight from
 * `src/api/admin.ts`.
 */
import client from "../../../api/client";
import type {
  Broadcast,
  BroadcastCreateBody,
  BroadcastDetail,
  BroadcastStatus,
  BroadcastTargetError,
  UploadResult,
} from "../../../api/adminTypes";

/** `broadcast_targets.error_kind` (`broadcast_worker.ERROR_KINDS`). */
export type BroadcastErrorKind =
  | "blocked"
  | "deactivated"
  | "chat_not_found"
  | "bad_request"
  | "flood"
  | "network"
  | "other";

export const ERROR_KINDS: BroadcastErrorKind[] = [
  "blocked",
  "deactivated",
  "chat_not_found",
  "bad_request",
  "flood",
  "network",
  "other",
];

/** `broadcast_worker.broadcast_breakdown()["retry"]`. */
export type BroadcastRetryState = {
  /** Recipients waiting for their next attempt. */
  scheduled: number;
  /** Epoch seconds of the earliest one, or null. */
  next_attempt_at: number | null;
  /** Recipients that needed more than one send. */
  retried: number;
  /** Sends beyond the first, summed. */
  extra_attempts: number;
};

/** `GET /admin/broadcasts/{id}` since stage B. */
export type BroadcastDetailFull = Omit<BroadcastDetail, "errors"> & {
  errors: (BroadcastTargetError & { error_kind: BroadcastErrorKind | null; attempts: number })[];
  error_kinds: Partial<Record<BroadcastErrorKind, number>>;
  retry: BroadcastRetryState;
  content_failed: number;
};

/** `error` the worker writes when the early abort stops a job. */
export const CONTENT_REJECTED = "content_rejected";

export async function getBroadcastDetail(id: number): Promise<BroadcastDetailFull> {
  const { data } = await client.get<BroadcastDetailFull>(`/admin/broadcasts/${id}`);
  return data;
}

export type BroadcastStateResult = { id: number; status: BroadcastStatus };

/**
 * `POST /api/admin/broadcasts/{id}/pause|resume`. The server needs no confirm
 * token for these (like `/cancel`); the page still asks through the shared,
 * history-backed confirm dialog, whose flow mints one — sent, and ignored.
 */
export async function setBroadcastStateWithToken(
  id: number,
  action: "pause" | "resume",
  token: string,
): Promise<BroadcastStateResult> {
  const { data } = await client.post<BroadcastStateResult>(
    `/admin/broadcasts/${id}/${action}`,
    undefined,
    { headers: { "X-Confirm-Token": token } },
  );
  return data;
}

export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

/** Mirrors `webapp/core/uploads.py:ALLOWED_TYPES` (the server sniffs magic bytes). */
export const ACCEPTED_MIME = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "video/mp4",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
] as const;

export const ACCEPT_ATTRIBUTE = ".jpg,.jpeg,.png,.webp,.mp4,.pdf,.docx";

const EXTENSIONS = /\.(jpe?g|png|webp|mp4|pdf|docx)$/i;

/** Cheap client-side gate; the server still decides by magic bytes. */
export function isAcceptedFile(file: File): boolean {
  if ((ACCEPTED_MIME as readonly string[]).includes(file.type)) return true;
  // Some browsers report an empty type for .docx / .webp — fall back to the name.
  return file.type === "" && EXTENSIONS.test(file.name);
}

/** `POST /api/admin/broadcasts` with a confirm token minted by the caller. */
export async function createBroadcastWithToken(
  body: BroadcastCreateBody,
  token: string,
): Promise<Broadcast> {
  const { data } = await client.post<Broadcast>("/admin/broadcasts", body, {
    headers: { "X-Confirm-Token": token },
  });
  return data;
}

/**
 * `POST /api/admin/broadcasts/{id}/queue` with a caller-minted token.
 *
 * `broadcast_id` is repeated in the body on purpose: the server binds the
 * confirmation token to JSON body fields, so that is where the id it is
 * confirming has to live (`webapp/routers/admin_broadcasts.py` rejects a body
 * whose id does not match the path).
 */
export async function queueBroadcastWithToken(
  id: number,
  token: string,
): Promise<{ id: number; status: string; total: number }> {
  const { data } = await client.post<{ id: number; status: string; total: number }>(
    `/admin/broadcasts/${id}/queue`,
    { broadcast_id: id },
    { headers: { "X-Confirm-Token": token } },
  );
  return data;
}

/** `POST /api/admin/broadcasts/{id}/cancel` with a caller-minted token. */
export async function cancelBroadcastWithToken(
  id: number,
  token: string,
): Promise<{ id: number; status: string }> {
  const { data } = await client.post<{ id: number; status: string }>(
    `/admin/broadcasts/${id}/cancel`,
    undefined,
    { headers: { "X-Confirm-Token": token } },
  );
  return data;
}

/** `POST /api/admin/uploads` (multipart) reporting 0..100 while it streams. */
export async function uploadMediaWithProgress(
  file: File,
  onProgress: (percent: number) => void,
): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<UploadResult>("/admin/uploads", form, {
    onUploadProgress: (event) => {
      if (!event.total) return;
      onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
    },
  });
  return data;
}
