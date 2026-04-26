import { Sparkles } from "lucide-react";
import { useState } from "react";

import AdvisorChat from "../components/AdvisorChat";
import { Card } from "../components/Card";
import HFBrowser from "../components/HFBrowser";
import HFModelDetail from "../components/HFModelDetail";
import PageHeader from "../components/PageHeader";
import RecipeDraftPane from "../components/RecipeDraftPane";
import SetupGate from "../components/SetupGate";
import { useBoxes } from "../hooks/useBoxes";
import {
  RecipeDraft,
  useCreateAdvisorSession,
  useGenerateRecipe,
} from "../hooks/useAdvisor";

export default function AdvisorPage() {
  const boxes = useBoxes();
  const [boxId, setBoxId] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<RecipeDraft | null>(null);
  const create = useCreateAdvisorSession();
  const gen = useGenerateRecipe();
  const busy = create.isPending || gen.isPending;
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
        subtitle="Search and filter the Hub, pick a model, then let Claude propose a vLLM serve recipe with rationale based on the model card and the target box's capabilities."
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
                  <select value={boxId} onChange={(e) => setBoxId(e.target.value)}>
                    <option value="">DGX Spark (default specs)</option>
                    {(boxes.data ?? []).map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                  <button
                    className="ai"
                    disabled={busy}
                    onClick={async () => {
                      setText("");
                      setDraft(null);
                      const r = await create.mutateAsync({
                        kind: "recipe",
                        target_box_id: boxId || null,
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
                      <Sparkles size={14} /> ask claude
                    </span>
                  </button>
                  <p
                    style={{
                      fontSize: 12,
                      color: "var(--fg-muted)",
                      marginTop: 4,
                    }}
                  >
                    Claude reads the model card, derives parameter/context/dtype
                    facts, and tunes vLLM flags for the target hardware.
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
