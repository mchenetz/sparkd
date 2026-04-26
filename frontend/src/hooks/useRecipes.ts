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

export function useRecipe(name: string | null) {
  return useQuery({
    queryKey: ["recipe", name],
    queryFn: () => api.get<Recipe>(`/recipes/${name}`),
    enabled: !!name,
  });
}

export function useRecipeRaw(name: string | null) {
  return useQuery({
    queryKey: ["recipe-raw", name],
    queryFn: () =>
      api.get<{ name: string; yaml: string }>(`/recipes/${name}/raw`),
    enabled: !!name,
  });
}

export function useSaveRecipe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (r: Recipe) => api.post<Recipe>("/recipes", r),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["recipes"] });
      qc.invalidateQueries({ queryKey: ["recipe", r.name] });
      qc.invalidateQueries({ queryKey: ["recipe-raw", r.name] });
    },
  });
}

export function useUpdateRecipe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (r: Recipe) => api.put<Recipe>(`/recipes/${r.name}`, r),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["recipes"] });
      qc.invalidateQueries({ queryKey: ["recipe", r.name] });
      qc.invalidateQueries({ queryKey: ["recipe-raw", r.name] });
    },
  });
}

export function useUpdateRecipeRaw() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, yaml }: { name: string; yaml: string }) =>
      api.put<Recipe>(`/recipes/${name}/raw`, { yaml }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["recipes"] });
      qc.invalidateQueries({ queryKey: ["recipe", r.name] });
      qc.invalidateQueries({ queryKey: ["recipe-raw", r.name] });
    },
  });
}

export function useDeleteRecipe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.delete<void>(`/recipes/${name}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recipes"] }),
  });
}
