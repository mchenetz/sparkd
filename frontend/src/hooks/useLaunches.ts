import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type Launch = {
  id: string;
  box_id: string;
  recipe_name: string;
  state: "starting" | "healthy" | "failed" | "stopped" | "interrupted";
  container_id: string | null;
  started_at: string;
  stopped_at: string | null;
};

export function useLaunches(boxId?: string) {
  return useQuery({
    queryKey: ["launches", boxId ?? null],
    queryFn: () => api.get<Launch[]>(`/launches${boxId ? `?box=${boxId}` : ""}`),
    refetchInterval: 5000,
  });
}

export function useCreateLaunch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { recipe: string; box_id: string; mods?: string[] }) =>
      api.post<Launch>("/launches", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["launches"] }),
  });
}

export function useStopLaunch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<Launch>(`/launches/${id}/stop`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["launches"] }),
  });
}
