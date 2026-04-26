import { Check } from "lucide-react";
import { useState } from "react";

import { ModDraft } from "../hooks/useAdvisor";
import { useSaveMod } from "../hooks/useMods";
import { Card, Pill } from "./Card";

export default function ModDraftPane({ draft }: { draft: ModDraft }) {
  const save = useSaveMod();
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
          <Pill tone="ai">draft mod</Pill>
          <h3 style={{ marginTop: 6 }}>{draft.name}</h3>
          <div style={{ fontSize: 12, color: "var(--fg-muted)" }}>
            targets:{" "}
            {draft.target_models.length > 0 ? (
              draft.target_models.map((t) => (
                <code key={t} style={{ marginRight: 8 }}>
                  {t}
                </code>
              ))
            ) : (
              <span style={{ fontStyle: "italic" }}>any</span>
            )}
          </div>
        </div>
        <button
          className="ai"
          disabled={saved || save.isPending}
          onClick={() =>
            save.mutate(
              {
                name: draft.name,
                target_models: draft.target_models,
                description: draft.description,
                files: draft.files,
                enabled: true,
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
        <p style={{ color: "var(--fg-secondary)", fontSize: 13, marginBottom: 12 }}>
          {draft.description}
        </p>
      )}

      <div style={{ display: "grid", gap: 8 }}>
        {Object.entries(draft.files).map(([f, c]) => (
          <details key={f} style={{ borderRadius: "var(--radius-sm)", overflow: "hidden" }}>
            <summary
              style={{
                cursor: "pointer",
                padding: "8px 12px",
                background: "var(--bg-elev-2)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-sm)",
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                color: "var(--fg-primary)",
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <span style={{ color: "var(--accent-ai)" }}>▸</span>
              {f}
              <span style={{ color: "var(--fg-faint)", fontSize: 10.5 }}>
                {c.split("\n").length} lines
              </span>
            </summary>
            <pre
              style={{
                margin: 0,
                padding: "12px 16px",
                background: "var(--bg-overlay)",
                border: "1px solid var(--border-subtle)",
                borderTop: "none",
                borderRadius: "0 0 var(--radius-sm) var(--radius-sm)",
                fontFamily: "var(--font-mono)",
                fontSize: 11.5,
                color: "var(--fg-secondary)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                maxHeight: 320,
                overflow: "auto",
              }}
            >
              {c}
            </pre>
          </details>
        ))}
      </div>

      {draft.rationale && (
        <div
          style={{
            marginTop: 14,
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
