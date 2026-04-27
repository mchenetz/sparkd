import { Wrench } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import AdvisorChat from "../components/AdvisorChat";
import { Card } from "../components/Card";
import PageHeader from "../components/PageHeader";
import RecipeDraftPane from "../components/RecipeDraftPane";
import SetupGate from "../components/SetupGate";
import TargetSelect from "../components/TargetSelect";
import {
  RecipeDraft,
  useCreateAdvisorSession,
  useOptimizeRecipe,
} from "../hooks/useAdvisor";
import { useRecipes } from "../hooks/useRecipes";

export default function OptimizePage() {
  const [params] = useSearchParams();
  const recipes = useRecipes();
  const [recipe, setRecipe] = useState(params.get("recipe") ?? "");
  const [boxId, setBoxId] = useState("");
  const [goals, setGoals] = useState("throughput");
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<RecipeDraft | null>(null);
  const create = useCreateAdvisorSession();
  const opt = useOptimizeRecipe();
  const busy = create.isPending || opt.isPending;
  return (
    <>
      <PageHeader
        ai
        eyebrow="AI · Recipe Optimizer"
        title={
          <>
            Tune an existing <em style={{ color: "var(--accent-ai)" }}>recipe</em>
          </>
        }
        subtitle="Hand Claude an existing recipe and a goal — get a revised recipe with rationale for each change. Box is optional; defaults to canonical DGX Spark specs."
      />
      <SetupGate>
        <Card ai style={{ marginBottom: 16 }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--accent-ai)",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              marginBottom: 12,
            }}
          >
            inputs
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1.4fr auto",
              gap: 8,
            }}
          >
            <select value={recipe} onChange={(e) => setRecipe(e.target.value)}>
              <option value="">— recipe —</option>
              {(recipes.data ?? []).map((r) => (
                <option key={r.name} value={r.name}>
                  {r.name}
                </option>
              ))}
            </select>
            <TargetSelect value={boxId} onChange={setBoxId} allowDefault />
            <input
              className="mono"
              value={goals}
              onChange={(e) => setGoals(e.target.value)}
              placeholder="throughput, latency, ..."
            />
            <button
              className="ai"
              disabled={!recipe || busy}
              onClick={async () => {
                setText("");
                setDraft(null);
                const r = await create.mutateAsync({
                  kind: "optimize",
                  target_box_id: boxId || null,
                  target_recipe_name: recipe,
                });
                const out = await opt.mutateAsync({
                  sid: r.id,
                  goals: goals
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                });
                setText(out.text);
                setDraft(out.draft);
              }}
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Wrench size={14} /> optimize
              </span>
            </button>
          </div>
        </Card>
        <AdvisorChat text={text} loading={busy} />
        {draft && <RecipeDraftPane draft={draft} />}
      </SetupGate>
    </>
  );
}
