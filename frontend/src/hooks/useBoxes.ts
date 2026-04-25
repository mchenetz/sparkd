import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type Box = {
  id: string;
  name: string;
  host: string;
  port: number;
  user: string;
  use_agent: boolean;
  repo_path: string;
  tags: Record<string, string>;
  created_at: string;
};

export function useBoxes() {
  return useQuery({ queryKey: ["boxes"], queryFn: () => api.get<Box[]>("/boxes") });
}

export function useCreateBox() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Box>) => api.post<Box>("/boxes", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["boxes"] }),
  });
}

export function useDeleteBox() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/boxes/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["boxes"] }),
  });
}
