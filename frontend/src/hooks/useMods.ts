import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type Mod = {
  name: string;
  target_models: string[];
  description: string;
  files: Record<string, string>;
  enabled: boolean;
};

export function useMods() {
  return useQuery({ queryKey: ["mods"], queryFn: () => api.get<Mod[]>("/mods") });
}

export function useSaveMod() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (m: Mod) => api.post<Mod>("/mods", m),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mods"] }),
  });
}

export function useDeleteMod() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.delete<void>(`/mods/${name}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mods"] }),
  });
}
