import { Eye, Network, Pause, Play, RotateCcw, Square, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Card, EmptyState, Pill } from "../components/Card";
import InspectModal from "../components/InspectModal";
import LiveLog from "../components/LiveLog";
import PageHeader from "../components/PageHeader";
import TargetSelect from "../components/TargetSelect";
import { useClusters } from "../hooks/useClusters";
import {
  Launch,
  LaunchState,
  useCreateLaunch,
  useDeleteLaunch,
  useLaunches,
  usePauseLaunch,
  useRestartLaunch,
  useStopLaunch,
  useUnpauseLaunch,
} from "../hooks/useLaunches";
import { useRecipes } from "../hooks/useRecipes";
import { recipeNodeCount, targetNodeCount } from "../utils/recipeNodes";

const TONE: Record<LaunchState, "healthy" | "warn" | "danger" | "neutral" | "info"> = {
  starting: "warn",
  healthy: "healthy",
  paused: "info",
  failed: "danger",
  stopped: "neutral",
  interrupted: "neutral",
};

export default function LaunchPage() {
  const { data: recipes } = useRecipes();
  const { data: clustersData } = useClusters();
  const create = useCreateLaunch();
  const [target, setTarget] = useState("");
  const [recipe, setRecipe] = useState("");

  // Recipes are filtered by the target's node count. Single-box target → only
  // single-node recipes; cluster of N → only recipes whose tp*pp == N. With
  // no target chosen, show everything so the user can browse before picking.
  const targetNodes = targetNodeCount(target, clustersData?.clusters ?? []);
  const allRecipes = recipes ?? [];
  const filteredRecipes =
    targetNodes === null
      ? allRecipes
      : allRecipes.filter((r) => recipeNodeCount(r) === targetNodes);
  const hiddenCount = allRecipes.length - filteredRecipes.length;

  // If the user changes target after picking a recipe and that recipe no
  // longer fits, drop the selection so they can't accidentally launch it.
  useEffect(() => {
    if (
      recipe &&
      targetNodes !== null &&
      !filteredRecipes.some((r) => r.name === recipe)
    ) {
      setRecipe("");
    }
  }, [target, targetNodes, recipe, filteredRecipes]);
  const active = useLaunches(undefined, { activeOnly: true });
  const all = useLaunches(undefined, { activeOnly: false });
  const [showHistory, setShowHistory] = useState(false);
  const history = (all.data ?? []).filter(
    (l) => l.state === "stopped" || l.state === "failed" || l.state === "interrupted",
  );
  return (
    <>
      <PageHeader
        eyebrow="Control"
        title={
          <>
            Launch <em style={{ color: "var(--fg-muted)" }}>recipe</em>
          </>
        }
        subtitle="Start a vLLM container on a registered box. Logs stream live; status flips to healthy once the OpenAI endpoint responds."
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
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 8 }}>
          <TargetSelect value={target} onChange={setTarget} placeholder="— target —" />
          <select value={recipe} onChange={(e) => setRecipe(e.target.value)}>
            <option value="">
              {targetNodes === null
                ? "— recipe —"
                : filteredRecipes.length === 0
                  ? `— no recipes for ${targetNodes}-node target —`
                  : `— recipe (${targetNodes}-node) —`}
            </option>
            {filteredRecipes.map((r) => (
              <option key={r.name} value={r.name}>
                {r.name}
              </option>
            ))}
          </select>
          <button
            className="primary"
            disabled={!target || !recipe || create.isPending}
            onClick={() => create.mutate({ recipe, target })}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <Play size={14} /> launch
            </span>
          </button>
        </div>
        {targetNodes !== null && hiddenCount > 0 && (
          <div
            style={{
              marginTop: 10,
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-faint)",
            }}
          >
            {hiddenCount} recipe{hiddenCount === 1 ? "" : "s"} hidden — only
            recipes sized for {targetNodes} node
            {targetNodes === 1 ? "" : "s"} (tp×pp) are shown.
          </div>
        )}
      </Card>

      <div style={{ display: "grid", gap: 16 }}>
        <h4 style={{ marginBottom: -4 }}>active launches</h4>
        {(active.data ?? []).length === 0 ? (
          <EmptyState
            title="No active launches"
            hint="Pick a box and a recipe above to start one."
          />
        ) : (
          (active.data ?? []).map((l) => <ActiveLaunch key={l.id} launch={l} />)
        )}
      </div>

      <div style={{ marginTop: 32 }}>
        <button
          className="ghost"
          onClick={() => setShowHistory((v) => !v)}
          style={{ paddingLeft: 0, color: "var(--fg-muted)" }}
        >
          {showHistory ? "▾" : "▸"} history ({history.length})
        </button>
        {showHistory && (
          <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
            {history.length === 0 ? (
              <div style={{ color: "var(--fg-faint)", fontStyle: "italic" }}>
                no past launches
              </div>
            ) : (
              history.map((l) => <HistoryRow key={l.id} launch={l} />)
            )}
          </div>
        )}
      </div>
    </>
  );
}

function ActiveLaunch({ launch }: { launch: Launch }) {
  const stop = useStopLaunch();
  const pause = usePauseLaunch();
  const unpause = useUnpauseLaunch();
  const restart = useRestartLaunch();
  const [inspectOpen, setInspectOpen] = useState(false);
  const isPaused = launch.state === "paused";
  return (
    <Card>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <Pill tone={TONE[launch.state]}>{launch.state}</Pill>
          <span style={{ fontWeight: 500 }}>{launch.recipe_name}</span>
          {launch.cluster_name && (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <Network size={11} style={{ color: "var(--fg-muted)" }} />
              <Pill tone="info">{launch.cluster_name}</Pill>
            </span>
          )}
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-muted)",
            }}
          >
            box={launch.box_id.slice(0, 8)}
          </span>
          {launch.container_id && (
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--fg-muted)",
              }}
            >
              cid={launch.container_id.slice(0, 12)}
            </span>
          )}
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-faint)",
            }}
          >
            started {new Date(launch.started_at).toLocaleTimeString()}
          </span>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {isPaused ? (
            <button className="ghost" onClick={() => unpause.mutate(launch.id)}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Play size={13} /> unpause
              </span>
            </button>
          ) : (
            <button className="ghost" onClick={() => pause.mutate(launch.id)}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Pause size={13} /> pause
              </span>
            </button>
          )}
          <button className="ghost" onClick={() => restart.mutate(launch.id)}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <RotateCcw size={13} /> restart
            </span>
          </button>
          <button className="ghost" onClick={() => setInspectOpen(true)}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <Eye size={13} /> inspect
            </span>
          </button>
          <button className="danger" onClick={() => stop.mutate(launch.id)}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <Square size={12} /> stop
            </span>
          </button>
        </div>
      </div>
      <LiveLog launchId={launch.id} />
      {inspectOpen && (
        <InspectModal launchId={launch.id} onClose={() => setInspectOpen(false)} />
      )}
    </Card>
  );
}

function HistoryRow({ launch }: { launch: Launch }) {
  const del = useDeleteLaunch();
  const [showLogs, setShowLogs] = useState(false);
  return (
    <Card>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <Pill tone={TONE[launch.state]}>{launch.state}</Pill>
          <span style={{ fontWeight: 500 }}>{launch.recipe_name}</span>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-faint)",
            }}
          >
            {new Date(launch.started_at).toLocaleString()}
          </span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button className="ghost" onClick={() => setShowLogs((v) => !v)}>
            {showLogs ? "hide logs" : "logs"}
          </button>
          <button className="ghost" onClick={() => del.mutate(launch.id)}>
            <Trash2 size={13} />
          </button>
        </div>
      </div>
      {showLogs && <LiveLog launchId={launch.id} />}
    </Card>
  );
}
