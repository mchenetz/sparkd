import { Plus, Trash2, Wrench } from "lucide-react";
import { useState } from "react";

import { Card, EmptyState, Pill } from "../components/Card";
import PageHeader from "../components/PageHeader";
import {
  Recipe,
  useDeleteRecipe,
  useRecipes,
  useSaveRecipe,
} from "../hooks/useRecipes";

export default function RecipesPage() {
  const { data } = useRecipes();
  const save = useSaveRecipe();
  const del = useDeleteRecipe();
  const [name, setName] = useState("");
  const [model, setModel] = useState("");
  const recipes = data ?? [];
  return (
    <>
      <PageHeader
        eyebrow="Library"
        title={
          <>
            Recipe <em style={{ color: "var(--fg-muted)" }}>library</em>
          </>
        }
        subtitle="Canonical vLLM serve configurations. Per-box overrides merge on top when launching."
      />

      <div style={{ display: "grid", gap: 24 }}>
        <Card>
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
            new recipe
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!name || !model) return;
              save.mutate({ name, model, args: {}, env: {}, mods: [] } as Recipe);
              setName("");
              setModel("");
            }}
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 2fr auto",
              gap: 8,
            }}
          >
            <input
              className="mono"
              placeholder="recipe slug (llama-8b-fp8)"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <input
              className="mono"
              placeholder="huggingface/model-id"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
            <button type="submit" className="primary" disabled={!name || !model}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Plus size={14} /> save
              </span>
            </button>
          </form>
        </Card>

        <Card pad={0}>
          {recipes.length === 0 ? (
            <EmptyState
              title="No recipes saved yet"
              hint="Add one by hand above, or have the Advisor generate one from a HF model."
            />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>recipe</th>
                  <th>model</th>
                  <th>flags</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {recipes.map((r) => {
                  const flagCount = Object.keys(r.args).length;
                  return (
                    <tr key={r.name}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <span style={{ fontWeight: 500 }}>{r.name}</span>
                          {r.mods.length > 0 && <Pill tone="ai">{r.mods.length} mod</Pill>}
                        </div>
                      </td>
                      <td>
                        <code style={{ color: "var(--fg-secondary)" }}>{r.model}</code>
                      </td>
                      <td>
                        <code style={{ color: "var(--fg-muted)" }}>
                          {flagCount} flag{flagCount === 1 ? "" : "s"}
                        </code>
                      </td>
                      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                        <a
                          href={`/optimize?recipe=${encodeURIComponent(r.name)}`}
                          style={{ borderBottom: "none" }}
                        >
                          <button className="ghost" title="optimize with AI">
                            <span
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 4,
                                color: "var(--accent-ai)",
                              }}
                            >
                              <Wrench size={13} /> optimize
                            </span>
                          </button>
                        </a>
                        <button
                          className="ghost"
                          onClick={() => del.mutate(r.name)}
                          title="delete"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </>
  );
}
