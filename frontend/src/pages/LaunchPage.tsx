import { AlertCircle, Eye, Network, Pause, Play, RotateCcw, Square, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { formatApiError } from "../api/client";
import { Card, EmptyState, Pill } from "../components/Card";
import InspectModal from "../components/InspectModal";
import LaunchExitInfo from "../components/LaunchExitInfo";
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

  // Recipes are filtered by node count, gated by user-toggleable chips at
  // the top of the form. Each chip is a node count (e.g. 1, 2, 3) that
  // appears either in the recipe library or in the chosen target. The
  // default set of selected chips matches the target's size — single-box
  // target picks {1}, cluster of N picks {N}, no target picks all
  // available counts. Manual toggles stick until the target changes.
  const targetNodes = targetNodeCount(target, clustersData?.clusters ?? []);
  const allRecipes = recipes ?? [];

  // Chip universe: every node count present in recipes, plus the target's
  // own count (so the user always has a chip representing their target,
  // even when no recipe currently matches it).
  const recipeCountSet = new Set(allRecipes.map(recipeNodeCount));
  if (targetNodes !== null) recipeCountSet.add(targetNodes);
  const availableCounts = Array.from(recipeCountSet).sort((a, b) => a - b);

  // The chip row tracks two layers:
  //   - default selection, derived from the target (single-box → {1};
  //     cluster of N → {N}; no target → all available counts)
  //   - manual override, set when the user clicks any chip
  // When the target changes we drop the override so defaults reapply.
  const [manualOverride, setManualOverride] = useState<Set<number> | null>(
    null,
  );
  useEffect(() => {
    setManualOverride(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  const defaultSelection: Set<number> =
    targetNodes === null
      ? new Set(availableCounts)
      : new Set([targetNodes]);
  const selectedCounts = manualOverride ?? defaultSelection;

  function toggleCount(n: number) {
    setManualOverride((prev) => {
      const base = prev ?? defaultSelection;
      const next = new Set(base);
      if (next.has(n)) next.delete(n);
      else next.add(n);
      return next;
    });
  }

  const filteredRecipes = allRecipes.filter((r) =>
    selectedCounts.has(recipeNodeCount(r)),
  );

  // If the currently picked recipe stops fitting the chip selection, drop it.
  useEffect(() => {
    if (recipe && !filteredRecipes.some((r) => r.name === recipe)) {
      setRecipe("");
    }
  }, [recipe, filteredRecipes]);
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
        {availableCounts.length > 1 && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              flexWrap: "wrap",
              marginBottom: 10,
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--fg-faint)",
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              filter:
            </span>
            {availableCounts.map((n) => {
              const selected = selectedCounts.has(n);
              const count = allRecipes.filter(
                (r) => recipeNodeCount(r) === n,
              ).length;
              return (
                <button
                  key={n}
                  type="button"
                  onClick={() => toggleCount(n)}
                  style={{
                    padding: "3px 10px",
                    borderRadius: 999,
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    letterSpacing: "0.06em",
                    cursor: "pointer",
                    background: selected
                      ? "rgba(108,182,255,0.12)"
                      : "transparent",
                    border: `1px solid ${
                      selected
                        ? "var(--signal-info)"
                        : "var(--border-subtle)"
                    }`,
                    color: selected
                      ? "var(--signal-info)"
                      : "var(--fg-muted)",
                  }}
                >
                  {n}-node ({count})
                </button>
              );
            })}
          </div>
        )}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 8 }}>
          <TargetSelect value={target} onChange={setTarget} placeholder="— target —" />
          <select value={recipe} onChange={(e) => setRecipe(e.target.value)}>
            <option value="">
              {filteredRecipes.length === 0
                ? selectedCounts.size === 0
                  ? "— select a node-count filter —"
                  : "— no recipes match filter —"
                : "— recipe —"}
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
        {create.error && (
          <div
            style={{
              marginTop: 12,
              padding: "10px 12px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--signal-danger)",
              background: "rgba(255,89,97,0.08)",
              color: "var(--signal-danger)",
              fontSize: 12,
              display: "flex",
              alignItems: "flex-start",
              gap: 8,
            }}
          >
            <AlertCircle
              size={14}
              style={{ flexShrink: 0, marginTop: 1 }}
            />
            <div style={{ flex: 1 }}>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: "var(--signal-danger)",
                  marginBottom: 2,
                }}
              >
                launch failed
              </div>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  color: "var(--fg-secondary)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {formatApiError(create.error)}
              </div>
            </div>
            <button
              type="button"
              onClick={() => create.reset()}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--fg-muted)",
                cursor: "pointer",
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                padding: 0,
              }}
            >
              dismiss
            </button>
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
      <LaunchExitInfo exitInfo={launch.exit_info} />
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
      <LaunchExitInfo exitInfo={launch.exit_info} />
      {showLogs && <LiveLog launchId={launch.id} />}
    </Card>
  );
}
