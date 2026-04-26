import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type AdvisorSession = {
  id: string;
  kind: "recipe" | "optimize" | "mod";
  target_box_id: string | null;
  target_recipe_name: string | null;
  hf_model_id: string | null;
  messages: Array<{ role: string; content: string }>;
  input_tokens: number;
  output_tokens: number;
};

export type RecipeDraft = {
  name: string;
  model: string;
  args: Record<string, string>;
  env: Record<string, string>;
  description: string;
  rationale: string;
};

export type ModDraft = {
  name: string;
  target_models: string[];
  files: Record<string, string>;
  description: string;
  rationale: string;
};

export function useAdvisorStatus() {
  return useQuery({
    queryKey: ["advisor", "status"],
    queryFn: () => api.get<{ configured: boolean }>("/advisor/status"),
  });
}

export function useAdvisorSetup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { anthropic_api_key: string }) =>
      api.post<{ ok: boolean }>("/advisor/setup", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["advisor", "status"] }),
  });
}

export function useCreateAdvisorSession() {
  return useMutation({
    mutationFn: (body: {
      kind: "recipe" | "optimize" | "mod";
      target_box_id?: string | null;
      target_recipe_name?: string | null;
      hf_model_id?: string | null;
    }) => api.post<{ id: string }>("/advisor/sessions", body),
  });
}

export function useGenerateRecipe() {
  return useMutation({
    mutationFn: (sid: string) =>
      api.post<{ draft: RecipeDraft; text: string }>(
        `/advisor/sessions/${sid}/recipe`,
        {}
      ),
  });
}

export function useOptimizeRecipe() {
  return useMutation({
    mutationFn: ({ sid, goals }: { sid: string; goals: string[] }) =>
      api.post<{ draft: RecipeDraft; text: string }>(
        `/advisor/sessions/${sid}/optimize`,
        { goals }
      ),
  });
}

export function useProposeMod() {
  return useMutation({
    mutationFn: ({ sid, error_log }: { sid: string; error_log: string }) =>
      api.post<{ draft: ModDraft; text: string }>(
        `/advisor/sessions/${sid}/mod`,
        { error_log }
      ),
  });
}
