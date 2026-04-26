import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export type ProviderDef = {
  id: string;
  label: string;
  family: "anthropic" | "openai_compat" | string;
  requires_key: boolean;
  default_base_url: string | null;
  base_url_editable: boolean;
  models: string[];
  notes: string;
  has_key: boolean;
};

export type ProvidersResponse = {
  active_provider: string;
  configured: string[];
  providers: ProviderDef[];
};

export type AdvisorConfigResponse = {
  active_provider: string;
  providers: Record<string, { model: string; base_url: string | null }>;
};

export type PutConfigBody = {
  provider: string;
  model: string;
  base_url?: string | null;
  api_key?: string;
  set_active?: boolean;
};

export function useProviders() {
  return useQuery({
    queryKey: ["advisor", "providers"],
    queryFn: () => api.get<ProvidersResponse>("/advisor/providers"),
  });
}

export function useAdvisorConfig() {
  return useQuery({
    queryKey: ["advisor", "config"],
    queryFn: () => api.get<AdvisorConfigResponse>("/advisor/config"),
  });
}

export function usePutAdvisorConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PutConfigBody) =>
      api.put<{
        ok: boolean;
        active_provider: string;
        active_model: string;
      }>("/advisor/config", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["advisor", "providers"] });
      qc.invalidateQueries({ queryKey: ["advisor", "config"] });
      qc.invalidateQueries({ queryKey: ["advisor", "status"] });
    },
  });
}
