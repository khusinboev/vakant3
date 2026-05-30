/**
 * Global back-button interceptor slot.
 * A page can register a callback that runs BEFORE the default navigate(-1).
 * If the callback returns true, the default navigation is suppressed.
 */
let _interceptor: (() => boolean) | null = null;

export function setBackInterceptor(fn: () => boolean) {
  _interceptor = fn;
}

export function clearBackInterceptor() {
  _interceptor = null;
}

export function runBackInterceptor(): boolean {
  return _interceptor ? _interceptor() : false;
}
