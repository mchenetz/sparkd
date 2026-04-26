import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type RecipeVersionSummary = {
  id: number;
  name: string;
  version: number;
  source: "manual" | "raw" | "sync" | "ai" | "revert" | string;
  note: string | null;
  created_at: string;
};

export type RecipeVersionFull = RecipeVersionSummary & { yaml_text: string };

export function useRecipeVersions(name: string | null) {
  return useQuery({
    queryKey: ["recipe", name, "versions"],
    queryFn: () =>
      api.get<{ name: string; versions: RecipeVersionSummary[] }>(
        `/recipes/${name}/versions`,
      ),
    enabled: !!name,
  });
}

export function useRecipeVersion(name: string | null, version: number | null) {
  return useQuery({
    queryKey: ["recipe", name, "versions", version],
    queryFn: () =>
      api.get<RecipeVersionFull>(`/recipes/${name}/versions/${version}`),
    enabled: !!name && version !== null,
  });
}

export function useRevertRecipe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, version, note }: { name: string; version: number; note?: string }) =>
      api.post(`/recipes/${name}/revert/${version}`, note ? { note } : {}),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["recipes"] });
      qc.invalidateQueries({ queryKey: ["recipe", vars.name] });
      qc.invalidateQueries({ queryKey: ["recipe-raw", vars.name] });
      qc.invalidateQueries({ queryKey: ["recipe", vars.name, "versions"] });
    },
  });
}
