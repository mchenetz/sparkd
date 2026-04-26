import { Check } from "lucide-react";
import { useState } from "react";

import { RecipeDraft } from "../hooks/useAdvisor";
import { useSaveRecipe } from "../hooks/useRecipes";
import { Card, Pill } from "./Card";

export default function RecipeDraftPane({ draft }: { draft: RecipeDraft }) {
  const save = useSaveRecipe();
  const [saved, setSaved] = useState(false);
  return (
    <Card ai style={{ marginTop: 16 }}>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 14,
        }}
      >
        <div>
          <Pill tone="ai">draft recipe</Pill>
          <h3 style={{ marginTop: 6 }}>{draft.name}</h3>
          <code
            style={{
              fontSize: 12,
              color: "var(--fg-muted)",
            }}
          >
            {draft.model}
          </code>
        </div>
        <button
          className="ai"
          disabled={saved || save.isPending}
          onClick={() =>
            save.mutate(
              {
                name: draft.name,
                model: draft.model,
                args: draft.args,
                env: draft.env,
                mods: [],
              },
              { onSuccess: () => setSaved(true) },
            )
          }
        >
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <Check size={14} /> {saved ? "saved" : "accept & save"}
          </span>
        </button>
      </div>

      {draft.description && (
        <p style={{ color: "var(--fg-secondary)", fontSize: 13, marginBottom: 16 }}>
          {draft.description}
        </p>
      )}

      <div
        style={{
          background: "var(--bg-overlay)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-sm)",
          padding: "12px 16px",
          fontFamily: "var(--font-mono)",
          fontSize: 12,
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "4px 24px",
          }}
        >
          {Object.entries(draft.args).map(([k, v]) => (
            <div key={k} style={{ display: "contents" }}>
              <div style={{ color: "var(--accent-ai)" }}>{k}</div>
              <div style={{ color: "var(--fg-primary)", textAlign: "right" }}>{v}</div>
            </div>
          ))}
        </div>
      </div>

      {draft.rationale && (
        <div
          style={{
            marginTop: 16,
            padding: "12px 16px",
            borderLeft: "2px solid var(--accent-ai)",
            background: "rgba(255,119,51,0.04)",
            color: "var(--fg-secondary)",
            fontStyle: "italic",
            fontSize: 13,
          }}
        >
          {draft.rationale}
        </div>
      )}
    </Card>
  );
}
