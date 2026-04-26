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

export function useHFModel(id: string | null) {
  return useQuery({
    queryKey: ["hf", id],
    queryFn: () => api.get<HFModelInfo>(`/hf/models/${id}`),
    enabled: !!id,
  });
}
