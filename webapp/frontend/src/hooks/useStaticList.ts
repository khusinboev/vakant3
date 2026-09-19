import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import client from "../api/client";

/** `GET /filters/regions` — `name` is localized, `name_uz` kept for compat. */
export type Region = {
  soato: string;
  name: string;
  name_uz: string;
};

/** `GET /filters/districts?region_soato=` — districts stay uz-only. */
export type District = {
  soato: string;
  name_uz: string;
};

/** `GET /filters/specs` — `key` is a stable snake key, `label` is localized. */
export type Spec = {
  id: string;
  key: string;
  label: string;
};

const ONE_DAY = 24 * 60 * 60 * 1000;

/**
 * Reference data that never changes within a session (regions, districts, specs).
 * Cached forever per language; the query key carries the params so a language
 * switch refetches (the axios client sends `Accept-Language`).
 */
export function useStaticList<T>(
  key: readonly unknown[],
  url: string,
  params?: Record<string, string | number>,
  enabled = true,
): UseQueryResult<T[]> {
  return useQuery<T[]>({
    queryKey: key,
    queryFn: async () => {
      const { data } = await client.get<T[]>(url, params ? { params } : undefined);
      return data;
    },
    enabled,
    staleTime: Infinity,
    gcTime: ONE_DAY,
    retry: 1,
  });
}

export function useRegions(): UseQueryResult<Region[]> {
  return useStaticList<Region>(["filters", "regions"], "/filters/regions");
}

export function useDistricts(regionSoato: string): UseQueryResult<District[]> {
  return useStaticList<District>(
    ["filters", "districts", regionSoato],
    "/filters/districts",
    { region_soato: regionSoato },
    Boolean(regionSoato),
  );
}

export function useSpecs(): UseQueryResult<Spec[]> {
  return useStaticList<Spec>(["filters", "specs"], "/filters/specs");
}

/** Display name of a region, tolerant of an API that only sent `name_uz`. */
export function regionName(region: Pick<Region, "name" | "name_uz">): string {
  return region.name || region.name_uz || "";
}

export default useStaticList;
