import { Sparkles, Wand2 } from "lucide-react";
import { useState } from "react";

import {
  RecipeDraft,
  useAdvisorStatus,
  useCreateAdvisorSession,
  useGenerateRecipe,
  useOptimizeRecipe,
} from "../hooks/useAdvisor";
import { Recipe, useUpdateRecipe } from "../hooks/useRecipes";
import AdvisorChat from "./AdvisorChat";
import { Card, Pill } from "./Card";

export default function RecipeAIAssist({
  recipe,
  isNew = false,
  onPendingDraft,
}: {
  recipe: Recipe;
  /** True on /recipes/new — only then does 'fill from a HF model' make sense.
   *  On an existing recipe, hide it (would otherwise clobber the user's work)
   *  and show only 'optimize current recipe'. */
  isNew?: boolean;
  onPendingDraft: (draft: RecipeDraft | null) => void;
}) {
  const status = useAdvisorStatus();
  const update = useUpdateRecipe();
  const create = useCreateAdvisorSession();
  const gen = useGenerateRecipe();
  const opt = useOptimizeRecipe();
  const [hfId, setHfId] = useState(recipe.model);
  const [goal, setGoal] = useState("throughput");
  const [text, setText] = useState("");
  const busy = create.isPending || gen.isPending || opt.isPending;
  const configured = status.data?.configured ?? false;

  if (!configured) {
    return (
      <Card>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
          <Sparkles size={14} style={{ color: "var(--accent-ai)" }} />
          <h4 style={{ margin: 0 }}>AI assist</h4>
        </div>
        <p style={{ color: "var(--fg-muted)", fontSize: 12 }}>
          Configure your Anthropic API key on the{" "}
          <a href="/advisor">Advisor</a> page to enable AI-guided editing.
        </p>
      </Card>
    );
  }

  return (
    <Card ai>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <Sparkles size={14} style={{ color: "var(--accent-ai)" }} />
        <h4 style={{ margin: 0 }}>AI assist</h4>
        <Pill tone="ai">claude</Pill>
      </div>

      {isNew && (
        <div style={{ display: "grid", gap: 10, marginBottom: 12 }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-muted)",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
            }}
          >
            fill from a hugging face model
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <input
              className="mono"
              value={hfId}
              onChange={(e) => setHfId(e.target.value)}
              placeholder="meta-llama/Llama-3.1-8B-Instruct"
              style={{ flex: 1 }}
            />
            <button
              className="ai"
              disabled={!hfId || busy}
              onClick={async () => {
                setText("");
                const r = await create.mutateAsync({
                  kind: "recipe",
                  target_box_id: null,
                  hf_model_id: hfId,
                });
                const out = await gen.mutateAsync(r.id);
                setText(out.text);
                if (out.draft) {
                  onPendingDraft(out.draft);
                }
              }}
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Wand2 size={13} /> fill
              </span>
            </button>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gap: 10, marginBottom: 12 }}>
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--fg-muted)",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}
        >
          {isNew ? "optimize current recipe" : "tune this recipe"}
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <input
            className="mono"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="throughput, latency, ..."
            style={{ flex: 1 }}
          />
          <button
            className="ai"
            disabled={busy}
            onClick={async () => {
              setText("");
              // Persist current spec first so /optimize loads the current state.
              await update.mutateAsync(recipe);
              const r = await create.mutateAsync({
                kind: "optimize",
                target_box_id: null,
                target_recipe_name: recipe.name,
              });
              const out = await opt.mutateAsync({
                sid: r.id,
                goals: goal
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              });
              setText(out.text);
              if (out.draft) {
                onPendingDraft(out.draft);
              }
            }}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <Sparkles size={13} /> tune
            </span>
          </button>
        </div>
      </div>

      <AdvisorChat text={text} loading={busy} />
    </Card>
  );
}
