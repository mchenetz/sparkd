import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";

export type FleetMember = {
  box_id: string;
  box_name: string;
  role: "head" | "worker" | "standalone";
  connectivity: "online" | "offline" | "unknown";
  container_id: string | null;
  container_image: string | null;
};

export type FleetLaunch = {
  id: string;
  recipe_name: string;
  state:
    | "starting"
    | "healthy"
    | "paused"
    | "failed"
    | "stopped"
    | "interrupted";
  box_id: string;
  cluster_name: string | null;
  container_id: string | null;
  started_at: string;
  exit_info: {
    reason?: string;
    tail?: string[];
    captured_at?: string;
  } | null;
};

export type FleetCluster = {
  name: string;
  members: FleetMember[];
  active_launch: FleetLaunch | null;
};

export type FleetStandalone = {
  member: FleetMember;
  active_launch: FleetLaunch | null;
};

export type DriftContainer = {
  box_id: string;
  box_name: string;
  container_id: string;
  image: string;
  state: string;
};

export type FleetSnapshot = {
  clusters: FleetCluster[];
  standalones: FleetStandalone[];
  drift_external_containers: DriftContainer[];
  drift_orphan_launches: string[];
  captured_at: string;
};

/**
 * Cluster-aware view of the whole fleet — clusters first, standalones
 * second, drift last. Renders in one pass on the Status page; backed by
 * /api/status/fleet which reads the reconciler-maintained DB state plus
 * a single docker-ps per box.
 */
export function useFleetStatus() {
  return useQuery({
    queryKey: ["fleet-status"],
    queryFn: () => api.get<FleetSnapshot>("/status/fleet"),
    refetchInterval: 5000,
  });
}
