import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type LaunchState =
  | "starting"
  | "healthy"
  | "paused"
  | "failed"
  | "stopped"
  | "interrupted";

export type Launch = {
  id: string;
  box_id: string;
  recipe_name: string;
  state: LaunchState;
  container_id: string | null;
  command: string;
  log_path: string | null;
  started_at: string;
  stopped_at: string | null;
};

export const ACTIVE_STATES: LaunchState[] = ["starting", "healthy", "paused"];

export function useLaunches(boxId?: string, opts?: { activeOnly?: boolean }) {
  const params = new URLSearchParams();
  if (boxId) params.set("box", boxId);
  if (opts?.activeOnly) params.set("active", "true");
  const qs = params.toString();
  return useQuery({
    queryKey: ["launches", boxId ?? null, opts?.activeOnly ?? false],
    queryFn: () => api.get<Launch[]>(`/launches${qs ? `?${qs}` : ""}`),
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

function action(verb: string) {
  return (id: string) => api.post<Launch>(`/launches/${id}/${verb}`);
}

export function useStopLaunch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: action("stop"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["launches"] }),
  });
}

export function usePauseLaunch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: action("pause"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["launches"] }),
  });
}

export function useUnpauseLaunch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: action("unpause"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["launches"] }),
  });
}

export function useRestartLaunch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: action("restart"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["launches"] }),
  });
}

export function useDeleteLaunch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/launches/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["launches"] }),
  });
}

export type InspectResult = {
  container_id?: string;
  inspect?: Record<string, unknown>;
  error?: string;
};

export function useLaunchInspect(id: string | null) {
  return useQuery({
    queryKey: ["launch", id, "inspect"],
    queryFn: () => api.get<InspectResult>(`/launches/${id}/inspect`),
    enabled: !!id,
  });
}
