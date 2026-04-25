import { useEffect, useState } from "react";

import { openWS } from "../api/client";

export type BoxStatus = {
  box_id: string;
  connectivity: "online" | "offline" | "degraded";
  running_models: Array<{
    container_id: string;
    launch_id: string | null;
    recipe_name: string | null;
    vllm_model_id: string | null;
    healthy: boolean;
    source: "dashboard" | "external";
  }>;
  drift_missing_container: string[];
  captured_at: string;
};

export function useBoxStatus(boxId: string | null) {
  const [snap, setSnap] = useState<BoxStatus | null>(null);
  useEffect(() => {
    if (!boxId) return;
    const ws = openWS(`/ws/boxes/${boxId}/status`);
    ws.onmessage = (ev) => setSnap(JSON.parse(ev.data));
    return () => ws.close();
  }, [boxId]);
  return snap;
}
