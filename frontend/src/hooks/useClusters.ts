import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import { Box } from "./useBoxes";

export type Cluster = {
  name: string;
  box_count: number;
  boxes: Box[];
};

export function useClusters() {
  return useQuery({
    queryKey: ["clusters"],
    queryFn: () => api.get<{ clusters: Cluster[] }>("/clusters"),
  });
}
