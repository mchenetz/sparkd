import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import AdvisorChat from "../components/AdvisorChat";
import RecipeDraftPane from "../components/RecipeDraftPane";
import { useBoxes } from "../hooks/useBoxes";
import {
  RecipeDraft,
  useCreateAdvisorSession,
  useOptimizeRecipe,
} from "../hooks/useAdvisor";
import { useRecipes } from "../hooks/useRecipes";

export default function OptimizePage() {
  const [params] = useSearchParams();
  const recipes = useRecipes();
  const boxes = useBoxes();
  const [recipe, setRecipe] = useState(params.get("recipe") ?? "");
  const [boxId, setBoxId] = useState("");
  const [goals, setGoals] = useState("throughput");
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<RecipeDraft | null>(null);
  const create = useCreateAdvisorSession();
  const opt = useOptimizeRecipe();
  const busy = create.isPending || opt.isPending;
  return (
    <div>
      <h1>Optimize recipe</h1>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <select value={recipe} onChange={(e) => setRecipe(e.target.value)}>
          <option value="">-- recipe --</option>
          {(recipes.data ?? []).map((r) => (
            <option key={r.name} value={r.name}>
              {r.name}
            </option>
          ))}
        </select>
        <select value={boxId} onChange={(e) => setBoxId(e.target.value)}>
          <option value="">-- box --</option>
          {(boxes.data ?? []).map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <input
          value={goals}
          onChange={(e) => setGoals(e.target.value)}
          placeholder="comma-separated goals"
        />
        <button
          disabled={!recipe || !boxId || busy}
          onClick={async () => {
            setText("");
            setDraft(null);
            const r = await create.mutateAsync({
              kind: "optimize",
              target_box_id: boxId,
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
          optimize
        </button>
      </div>
      <AdvisorChat text={text} loading={busy} />
      {draft && <RecipeDraftPane draft={draft} />}
    </div>
  );
}
