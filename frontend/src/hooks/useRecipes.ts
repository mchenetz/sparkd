import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type Recipe = {
  name: string;
  model: string;
  description?: string;
  args: Record<string, string>;
  env: Record<string, string>;
  mods: string[];
};

export function useRecipes(boxId?: string) {
  return useQuery({
    queryKey: ["recipes", boxId ?? null],
    queryFn: () => api.get<Recipe[]>(`/recipes${boxId ? `?box=${boxId}` : ""}`),
  });
}

export function useSaveRecipe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (r: Recipe) => api.post<Recipe>("/recipes", r),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recipes"] }),
  });
}

export function useDeleteRecipe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.delete<void>(`/recipes/${name}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recipes"] }),
  });
}
