import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type Box = {
  id: string;
  name: string;
  host: string;
  port: number;
  user: string;
  use_agent: boolean;
  ssh_key_path?: string | null;
  repo_path: string;
  /** IP this box advertises on the cluster IB/eth fabric. Used as the -n
   * value for cluster launches; auto-detected from upstream's .env when
   * capabilities are refreshed. Editable on Box Detail. */
  cluster_ip?: string | null;
  tags: Record<string, string>;
  created_at: string;
};

export type BoxCapabilities = {
  gpu_count: number;
  gpu_model: string;
  vram_per_gpu_gb: number;
  cuda_version: string | null;
  ib_interface: string | null;
  captured_at: string;
};

export function useBoxes() {
  return useQuery({ queryKey: ["boxes"], queryFn: () => api.get<Box[]>("/boxes") });
}

export function useBox(id: string | null) {
  return useQuery({
    queryKey: ["box", id],
    queryFn: () => api.get<Box>(`/boxes/${id}`),
    enabled: !!id,
  });
}

export function useBoxCapabilities(id: string | null) {
  return useQuery({
    queryKey: ["box", id, "capabilities"],
    queryFn: () => api.get<BoxCapabilities>(`/boxes/${id}/capabilities`),
    enabled: !!id,
  });
}

export function useRefreshBoxCapabilities() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.get<BoxCapabilities>(`/boxes/${id}/capabilities?refresh=true`),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["box", id, "capabilities"] });
    },
  });
}

export function useCreateBox() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Box>) => api.post<Box>("/boxes", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["boxes"] }),
  });
}

export function useUpdateBox() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Box> }) =>
      api.put<Box>(`/boxes/${id}`, body),
    onSuccess: (b) => {
      qc.invalidateQueries({ queryKey: ["boxes"] });
      qc.invalidateQueries({ queryKey: ["box", b.id] });
    },
  });
}

export function useDeleteBox() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/boxes/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["boxes"] }),
  });
}

export function useTestBox() {
  return useMutation({
    mutationFn: (id: string) => api.post<{ ok: boolean }>(`/boxes/${id}/test`),
  });
}
