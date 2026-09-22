import { useCallback, useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";

export type QueryStateOptions = {
  /**
   * `false` (default) pushes, so "back" undoes the filter change.
   * Use `true` for values that change on every keystroke (search boxes).
   */
  replace?: boolean;
};

/**
 * A piece of page state that lives in the URL — the spec's rule that every
 * sub-state (tab, filter, sort) is a history entry.
 *
 *   const [tab, setTab] = useQueryState("tab", "health");
 *   const [q, setQ] = useQueryState("q", "", { replace: true });
 *
 * The default value is never written to the URL, so a pristine page has a
 * clean address.
 */
export function useQueryState<T extends string = string>(
  key: string,
  defaultValue: T,
  options: QueryStateOptions = {},
): [T, (value: T) => void] {
  const location = useLocation();
  const navigate = useNavigate();
  const replace = options.replace ?? false;

  const value = (new URLSearchParams(location.search).get(key) ?? defaultValue) as T;

  const setValue = useCallback(
    (next: T) => {
      const params = new URLSearchParams(location.search);
      if (!next || next === defaultValue) params.delete(key);
      else params.set(key, next);
      const search = params.toString();
      navigate(`${location.pathname}${search ? `?${search}` : ""}`, {
        replace,
        state: location.state,
      });
    },
    [defaultValue, key, location.pathname, location.search, location.state, navigate, replace],
  );

  return useMemo(() => [value, setValue], [value, setValue]);
}

export default useQueryState;
