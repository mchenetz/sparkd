import { Sparkles } from "lucide-react";
import { useState } from "react";

import AdvisorChat from "../components/AdvisorChat";
import { Card } from "../components/Card";
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
  const [hfId, setHfId] = useState("");
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
            Generate a <em style={{ color: "var(--accent-ai)" }}>recipe</em>
          </>
        }
        subtitle="Pick a Hugging Face model. Claude reads the model card and target hardware, then proposes a vLLM serve recipe with rationale. Box selection is optional — defaults to canonical DGX Spark specs."
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
              gridTemplateColumns: "1fr 1.5fr auto",
              gap: 8,
            }}
          >
            <select value={boxId} onChange={(e) => setBoxId(e.target.value)}>
              <option value="">DGX Spark (default specs)</option>
              {(boxes.data ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            <input
              className="mono"
              placeholder="meta-llama/Llama-3.1-8B-Instruct"
              value={hfId}
              onChange={(e) => setHfId(e.target.value)}
            />
            <button
              className="ai"
              disabled={!hfId || busy}
              onClick={async () => {
                setText("");
                setDraft(null);
                const r = await create.mutateAsync({
                  kind: "recipe",
                  target_box_id: boxId || null,
                  hf_model_id: hfId,
                });
                const out = await gen.mutateAsync(r.id);
                setText(out.text);
                setDraft(out.draft);
              }}
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Sparkles size={14} /> generate
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
