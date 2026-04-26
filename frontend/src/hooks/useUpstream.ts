import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type UpstreamSyncResult = {
  repo: string;
  branch: string;
  imported: string[];
  skipped: string[];
  errors: { name: string; message: string }[];
};

export function useSyncUpstream() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { repo?: string; branch?: string; force?: boolean }) =>
      api.post<UpstreamSyncResult>("/recipes/sync-upstream", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recipes"] }),
  });
}
