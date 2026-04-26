import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type UpstreamSyncResult = {
  repo: string;
  branch: string;
  imported: string[];
  skipped: string[];
  errors: { name: string; message: string }[];
};

type Body = { repo?: string; branch?: string; force?: boolean };

export function useSyncUpstreamRecipes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Body) =>
      api.post<UpstreamSyncResult>("/recipes/sync-upstream", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recipes"] }),
  });
}

export function useSyncUpstreamMods() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Body) =>
      api.post<UpstreamSyncResult>("/mods/sync-upstream", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mods"] }),
  });
}
