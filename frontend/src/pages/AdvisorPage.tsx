import { Network, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import AdvisorChat from "../components/AdvisorChat";
import { Card, Pill } from "../components/Card";
import HFBrowser from "../components/HFBrowser";
import HFModelDetail from "../components/HFModelDetail";
import PageHeader from "../components/PageHeader";
import RecipeDraftPane from "../components/RecipeDraftPane";
import SetupGate from "../components/SetupGate";
import TargetSelect from "../components/TargetSelect";
import { useClusters } from "../hooks/useClusters";
import {
  RecipeDraft,
  useCreateAdvisorSession,
  useGenerateRecipe,
} from "../hooks/useAdvisor";

const CLUSTER_PREFIX = "cluster:";

export default function AdvisorPage() {
  const clusters = useClusters();
  const [params] = useSearchParams();
  const [target, setTarget] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<RecipeDraft | null>(null);
  const create = useCreateAdvisorSession();
  const gen = useGenerateRecipe();
  const busy = create.isPending || gen.isPending;

  // Pre-fill from `?cluster=alpha` so the Boxes page's "advise multi-node"
  // shortcut lands the user with the cluster preselected.
  useEffect(() => {
    const c = params.get("cluster");
    if (c) setTarget(`${CLUSTER_PREFIX}${c}`);
  }, [params]);

  const clusterList = clusters.data?.clusters ?? [];
  const isCluster = target.startsWith(CLUSTER_PREFIX);
  const activeCluster = isCluster
    ? clusterList.find((c) => c.name === target.slice(CLUSTER_PREFIX.length))
    : null;

  return (
    <>
      <PageHeader
        ai
        eyebrow="AI · Recipe Advisor"
        title={
          <>
            Browse Hugging Face,{" "}
            <em style={{ color: "var(--accent-ai)" }}>generate</em> a recipe
          </>
        }
        subtitle="Search and filter the Hub, pick a model, then let Claude propose a vLLM serve recipe based on the model card and the chosen single-box or multi-node target."
      />
      <SetupGate>
        <div style={{ display: "grid", gap: 16 }}>
          <HFBrowser selected={selected} onSelect={setSelected} />

          {selected && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <HFModelDetail id={selected} />
              <Card ai>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "var(--accent-ai)",
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                    marginBottom: 10,
                  }}
                >
                  generate recipe
                </div>
                <div style={{ display: "grid", gap: 10 }}>
                  <TargetSelect
                    value={target}
                    onChange={setTarget}
                    allowDefault
                    defaultLabel="DGX Spark (default specs)"
                  />

                  {activeCluster && (
                    <div
                      style={{
                        background: "var(--bg-overlay)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "var(--radius-sm)",
                        padding: "10px 12px",
                        fontSize: 12,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "baseline",
                          gap: 8,
                          marginBottom: 6,
                        }}
                      >
                        <Network
                          size={12}
                          style={{ color: "var(--fg-muted)" }}
                        />
                        <span style={{ fontWeight: 500 }}>
                          {activeCluster.name}
                        </span>
                        <Pill tone="info">
                          {activeCluster.box_count} node
                          {activeCluster.box_count === 1 ? "" : "s"}
                        </Pill>
                      </div>
                      <div
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 11,
                          color: "var(--fg-muted)",
                          display: "grid",
                          gap: 2,
                        }}
                      >
                        {activeCluster.boxes.map((b) => (
                          <div key={b.id}>
                            · {b.name}{" "}
                            <span style={{ color: "var(--fg-faint)" }}>
                              {b.host}:{b.port}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <button
                    className="ai"
                    disabled={busy}
                    onClick={async () => {
                      setText("");
                      setDraft(null);
                      const r = await create.mutateAsync({
                        kind: "recipe",
                        target_box_id: target || null,
                        hf_model_id: selected,
                      });
                      const out = await gen.mutateAsync(r.id);
                      setText(out.text);
                      setDraft(out.draft);
                    }}
                  >
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <Sparkles size={14} />{" "}
                      {isCluster ? "plan multi-node" : "ask claude"}
                    </span>
                  </button>
                  <p
                    style={{
                      fontSize: 12,
                      color: "var(--fg-muted)",
                      marginTop: 4,
                    }}
                  >
                    {isCluster
                      ? "Claude sees per-node capabilities + total GPU/VRAM and recommends a tensor/pipeline-parallel split, Ray cluster setup, and any NCCL/IB env vars needed for cross-node communication."
                      : "Claude reads the model card, derives parameter/context/dtype facts, and tunes vLLM flags for the target hardware."}
                  </p>
                </div>
              </Card>
            </div>
          )}

          <AdvisorChat text={text} loading={busy} />
          {draft && <RecipeDraftPane draft={draft} />}
        </div>
      </SetupGate>
    </>
  );
}
