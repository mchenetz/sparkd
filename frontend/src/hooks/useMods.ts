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

export function useMod(name: string | null) {
  return useQuery({
    queryKey: ["mod", name],
    queryFn: () => api.get<Mod>(`/mods/${name}`),
    enabled: !!name,
  });
}

export function useSaveMod() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (m: Mod) => api.post<Mod>("/mods", m),
    onSuccess: (m) => {
      qc.invalidateQueries({ queryKey: ["mods"] });
      qc.invalidateQueries({ queryKey: ["mod", m.name] });
    },
  });
}

export function useUpdateMod() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (m: Mod) => api.put<Mod>(`/mods/${m.name}`, m),
    onSuccess: (m) => {
      qc.invalidateQueries({ queryKey: ["mods"] });
      qc.invalidateQueries({ queryKey: ["mod", m.name] });
    },
  });
}

export function useDeleteMod() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.delete<void>(`/mods/${name}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mods"] }),
  });
}
