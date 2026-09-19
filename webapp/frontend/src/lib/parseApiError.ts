/**
 * Normalizes anything axios can throw into one shape.
 *
 * The backend contract (CONTRACT.md) is `detail = {"code": "<UPPER_SNAKE>", ...params}`,
 * but FastAPI validation errors keep their default list shape and older/unhandled
 * paths may still return a plain string — all three are handled here.
 */
export type ApiError = {
  /** UPPER_SNAKE code, e.g. "PRO_REQUIRED". "UNKNOWN" when nothing usable was found. */
  code: string;
  /** Extra fields carried alongside the code, e.g. {limit: 5, current: 5}. */
  params: Record<string, unknown>;
  /** HTTP status, or 0 for network/offline failures. */
  status: number;
  /** Raw server message when the API returned prose. Prefer a translated code. */
  message: string;
};

type AxiosLike = {
  response?: { status?: number; data?: unknown };
  message?: string;
  code?: string;
};

const STATUS_CODE_FALLBACK: Record<number, string> = {
  401: "AUTH_REQUIRED",
  403: "PRO_REQUIRED",
  404: "NOT_FOUND",
  413: "PAYLOAD_TOO_LARGE",
  422: "VALIDATION_ERROR",
  429: "RATE_LIMITED",
  502: "UPSTREAM_ERROR",
  503: "UPSTREAM_ERROR",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseApiError(error: unknown): ApiError {
  const err = (error ?? {}) as AxiosLike;
  const status = Number(err.response?.status ?? 0);

  // No response at all → offline / DNS / CORS / timeout.
  if (!err.response) {
    return {
      code: "NETWORK_ERROR",
      params: {},
      status: 0,
      message: String(err.message ?? ""),
    };
  }

  const data = err.response.data;
  const detail = isRecord(data) ? data.detail : data;

  // 1. Contract shape: {"code": "...", ...params}
  if (isRecord(detail) && typeof detail.code === "string") {
    const { code, ...params } = detail;
    return { code, params, status, message: String(params.message ?? "") };
  }

  // 2. FastAPI 422: detail is a list of validation issues.
  if (Array.isArray(detail)) {
    const first = detail.find(isRecord);
    const loc = first && Array.isArray(first.loc) ? first.loc : [];
    return {
      code: "VALIDATION_ERROR",
      params: { field: String(loc[loc.length - 1] ?? "") },
      status,
      message: first && typeof first.msg === "string" ? first.msg : "",
    };
  }

  // 3. Legacy prose detail.
  const message = typeof detail === "string" ? detail : String(err.message ?? "");
  return {
    code: STATUS_CODE_FALLBACK[status] ?? "UNKNOWN",
    params: {},
    status,
    message,
  };
}

/** `true` when the error carries this code — the common branching shorthand. */
export function isApiErrorCode(error: unknown, code: string): boolean {
  return parseApiError(error).code === code;
}

export default parseApiError;
