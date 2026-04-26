import { Play, Square } from "lucide-react";
import { useState } from "react";

import { Card, EmptyState, Pill } from "../components/Card";
import LiveLog from "../components/LiveLog";
import PageHeader from "../components/PageHeader";
import { useBoxes } from "../hooks/useBoxes";
import { Launch, useCreateLaunch, useLaunches, useStopLaunch } from "../hooks/useLaunches";
import { useRecipes } from "../hooks/useRecipes";

const TONE: Record<Launch["state"], "healthy" | "warn" | "danger" | "neutral"> = {
  starting: "warn",
  healthy: "healthy",
  failed: "danger",
  stopped: "neutral",
  interrupted: "neutral",
};

export default function LaunchPage() {
  const { data: boxes } = useBoxes();
  const { data: recipes } = useRecipes();
  const create = useCreateLaunch();
  const stop = useStopLaunch();
  const [box, setBox] = useState("");
  const [recipe, setRecipe] = useState("");
  const launches = useLaunches();
  return (
    <>
      <PageHeader
        eyebrow="Control"
        title={
          <>
            Launch <em style={{ color: "var(--fg-muted)" }}>recipe</em>
          </>
        }
        subtitle="Start a vLLM container on a registered box. Logs stream live; the status reconciler will move it to healthy once the OpenAI endpoint responds."
      />

      <Card style={{ marginBottom: 24 }}>
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--fg-muted)",
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            marginBottom: 12,
          }}
        >
          new launch
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr auto",
            gap: 8,
          }}
        >
          <select value={box} onChange={(e) => setBox(e.target.value)}>
            <option value="">— target box —</option>
            {(boxes ?? []).map((b) => (
              <option key={b.id} value={b.id}>
                {b.name} · {b.host}
              </option>
            ))}
          </select>
          <select value={recipe} onChange={(e) => setRecipe(e.target.value)}>
            <option value="">— recipe —</option>
            {(recipes ?? []).map((r) => (
              <option key={r.name} value={r.name}>
                {r.name}
              </option>
            ))}
          </select>
          <button
            className="primary"
            disabled={!box || !recipe || create.isPending}
            onClick={() => create.mutate({ recipe, box_id: box })}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <Play size={14} /> launch
            </span>
          </button>
        </div>
      </Card>

      <div style={{ display: "grid", gap: 16 }}>
        <h4 style={{ marginBottom: -4 }}>active launches</h4>
        {(launches.data ?? []).length === 0 ? (
          <EmptyState
            title="No active launches"
            hint="Pick a box and a recipe above to start one."
          />
        ) : (
          (launches.data ?? []).map((l) => (
            <Card key={l.id}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 16,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
                  <Pill tone={TONE[l.state]}>{l.state}</Pill>
                  <span style={{ fontWeight: 500 }}>{l.recipe_name}</span>
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "var(--fg-muted)",
                    }}
                  >
                    box={l.box_id.slice(0, 8)}
                  </span>
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "var(--fg-faint)",
                    }}
                  >
                    started {new Date(l.started_at).toLocaleTimeString()}
                  </span>
                </div>
                <button
                  className="danger"
                  onClick={() => stop.mutate(l.id)}
                  disabled={l.state === "stopped"}
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <Square size={12} /> stop
                  </span>
                </button>
              </div>
              <LiveLog launchId={l.id} />
            </Card>
          ))
        )}
      </div>
    </>
  );
}
