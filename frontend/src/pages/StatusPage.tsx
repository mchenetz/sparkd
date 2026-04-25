import { useState } from "react";

import { useBoxes } from "../hooks/useBoxes";
import { useBoxStatus } from "../hooks/useBoxStatus";

export default function StatusPage() {
  const { data: boxes } = useBoxes();
  const [boxId, setBoxId] = useState<string | null>(null);
  const snap = useBoxStatus(boxId);
  return (
    <div>
      <h1>Status</h1>
      <select value={boxId ?? ""} onChange={(e) => setBoxId(e.target.value || null)}>
        <option value="">-- box --</option>
        {(boxes ?? []).map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </select>
      {snap && (
        <div>
          <p>
            connectivity: <b>{snap.connectivity}</b>
          </p>
          <table>
            <thead>
              <tr>
                <th>container</th>
                <th>recipe</th>
                <th>model</th>
                <th>healthy</th>
                <th>source</th>
              </tr>
            </thead>
            <tbody>
              {snap.running_models.map((m) => (
                <tr key={m.container_id}>
                  <td>{m.container_id.slice(0, 12)}</td>
                  <td>{m.recipe_name ?? "—"}</td>
                  <td>{m.vllm_model_id ?? "—"}</td>
                  <td>{m.healthy ? "✓" : "✗"}</td>
                  <td>{m.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
