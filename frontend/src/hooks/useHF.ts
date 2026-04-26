import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";

export type HFModelInfo = {
  id: string;
  architecture: string;
  parameters_b: number;
  context_length: number;
  supported_dtypes: string[];
  license: string;
  pipeline_tag: string;
};

export type HFModelSummary = {
  id: string;
  downloads: number;
  likes: number;
  last_modified: string | null;
  pipeline_tag: string;
  library_name: string;
  tags: string[];
  private: boolean;
  gated: boolean | string;
};

export type HFSearchParams = {
  q?: string;
  pipeline_tag?: string;
  library?: string;
  sort?: string;
  direction?: number;
  limit?: number;
};

export function useHFModel(id: string | null) {
  return useQuery({
    queryKey: ["hf", "model", id],
    queryFn: () => api.get<HFModelInfo>(`/hf/models/${id}`),
    enabled: !!id,
  });
}

export function useHFSearch(params: HFSearchParams) {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  if (params.pipeline_tag) qs.set("pipeline_tag", params.pipeline_tag);
  if (params.library) qs.set("library", params.library);
  if (params.sort) qs.set("sort", params.sort);
  if (params.direction !== undefined) qs.set("direction", String(params.direction));
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  const key = qs.toString();
  return useQuery({
    queryKey: ["hf", "search", key],
    queryFn: () =>
      api.get<{ results: HFModelSummary[]; count: number }>(
        `/hf/search${key ? `?${key}` : ""}`,
      ),
    placeholderData: (prev) => prev,
  });
}
