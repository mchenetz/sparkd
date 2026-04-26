import { Radio } from "lucide-react";
import { useState } from "react";

import { Card, EmptyState, Pill } from "../components/Card";
import PageHeader from "../components/PageHeader";
import { useBoxes } from "../hooks/useBoxes";
import { useBoxStatus } from "../hooks/useBoxStatus";

export default function StatusPage() {
  const { data: boxes } = useBoxes();
  const [boxId, setBoxId] = useState<string | null>(null);
  const snap = useBoxStatus(boxId);
  return (
    <>
      <PageHeader
        eyebrow="Telemetry"
        title={
          <>
            Live <em style={{ color: "var(--fg-muted)" }}>status</em>
          </>
        }
        subtitle="Reconciled view of running containers vs. dashboard launch records, plus vLLM endpoint health."
      />

      <Card style={{ marginBottom: 24 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <span style={{ color: "var(--fg-muted)", fontSize: 12 }}>box:</span>
            <select
              value={boxId ?? ""}
              onChange={(e) => setBoxId(e.target.value || null)}
              style={{ minWidth: 220 }}
            >
              <option value="">— pick a box —</option>
              {(boxes ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
          {snap && (
            <Pill
              tone={
                snap.connectivity === "online"
                  ? "healthy"
                  : snap.connectivity === "degraded"
                  ? "warn"
                  : "danger"
              }
            >
              <Radio size={10} /> {snap.connectivity}
            </Pill>
          )}
        </div>
      </Card>

      {!boxId ? (
        <EmptyState title="Select a box to begin streaming status" />
      ) : !snap ? (
        <Card>
          <div style={{ color: "var(--fg-muted)" }}>
            <span
              style={{
                display: "inline-block",
                width: 8,
                height: 8,
                borderRadius: 999,
                background: "var(--signal-info)",
                marginRight: 8,
                animation: "pulse-dot 1.4s var(--ease-in-out) infinite",
              }}
            />
            connecting to <code>/ws/boxes/{boxId.slice(0, 8)}/status</code>…
          </div>
        </Card>
      ) : (
        <div style={{ display: "grid", gap: 16 }}>
          <Card pad={0}>
            <table>
              <thead>
                <tr>
                  <th>container</th>
                  <th>recipe</th>
                  <th>vllm model</th>
                  <th>health</th>
                  <th>source</th>
                </tr>
              </thead>
              <tbody>
                {snap.running_models.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ padding: 32, color: "var(--fg-muted)" }}>
                      no running containers
                    </td>
                  </tr>
                ) : (
                  snap.running_models.map((m) => (
                    <tr key={m.container_id}>
                      <td>
                        <code>{m.container_id.slice(0, 12)}</code>
                      </td>
                      <td>
                        {m.recipe_name ? (
                          <span>{m.recipe_name}</span>
                        ) : (
                          <span style={{ color: "var(--fg-faint)" }}>—</span>
                        )}
                      </td>
                      <td>
                        <code style={{ color: "var(--fg-secondary)" }}>
                          {m.vllm_model_id ?? "—"}
                        </code>
                      </td>
                      <td>
                        <Pill tone={m.healthy ? "healthy" : "warn"}>
                          {m.healthy ? "200" : "down"}
                        </Pill>
                      </td>
                      <td>
                        <Pill tone={m.source === "dashboard" ? "info" : "neutral"}>
                          {m.source}
                        </Pill>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </Card>

          {snap.drift_missing_container.length > 0 && (
            <Card>
              <h4 style={{ marginBottom: 10, color: "var(--signal-warn)" }}>
                drift detected
              </h4>
              <p style={{ color: "var(--fg-secondary)", fontSize: 13, marginBottom: 8 }}>
                Launch records exist with no matching container — they may have crashed
                or been cleaned up outside the dashboard.
              </p>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                {snap.drift_missing_container.map((id) => (
                  <div key={id} style={{ color: "var(--fg-muted)" }}>
                    · launch {id}
                  </div>
                ))}
              </div>
            </Card>
          )}

          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-faint)",
              textAlign: "right",
            }}
          >
            captured_at {new Date(snap.captured_at).toLocaleTimeString()}
          </div>
        </div>
      )}
    </>
  );
}
