import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export function useHFTokenStatus() {
  return useQuery({
    queryKey: ["hf", "token"],
    queryFn: () => api.get<{ configured: boolean }>("/hf/token"),
  });
}

export function useSaveHFToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (token: string) =>
      api.put<{ ok: boolean }>("/hf/token", { token }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hf", "token"] });
      qc.invalidateQueries({ queryKey: ["hf", "search"] });
      qc.invalidateQueries({ queryKey: ["hf", "model"] });
    },
  });
}

export function useClearHFToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<void>("/hf/token"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hf", "token"] });
      qc.invalidateQueries({ queryKey: ["hf", "search"] });
      qc.invalidateQueries({ queryKey: ["hf", "model"] });
    },
  });
}
