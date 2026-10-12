import { useCallback } from "react";
import { useSearchParams } from "react-router";

/** Filters kept in the URL, so a filtered view can be reloaded or shared. */
export function useSearchState() {
  const [params, setParams] = useSearchParams();

  const get = useCallback((key: string) => params.get(key) ?? "", [params]);
  const getAll = useCallback((key: string) => params.getAll(key), [params]);
  const page = Number(params.get("page") ?? "1") || 1;

  const update = useCallback(
    (changes: Record<string, string | string[] | null>, keepPage = false) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(changes)) {
            next.delete(key);
            if (Array.isArray(value)) value.forEach((v) => next.append(key, v));
            else if (value) next.set(key, value);
          }
          if (!keepPage && !("page" in changes)) next.delete("page");
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  return { params, get, getAll, page, update };
}
