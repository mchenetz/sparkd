import { KeyRound, Sparkles } from "lucide-react";
import { useState } from "react";

import AdvisorChat from "../components/AdvisorChat";
import { Card } from "../components/Card";
import PageHeader from "../components/PageHeader";
import RecipeDraftPane from "../components/RecipeDraftPane";
import { useBoxes } from "../hooks/useBoxes";
import {
  RecipeDraft,
  useAdvisorSetup,
  useAdvisorStatus,
  useCreateAdvisorSession,
  useGenerateRecipe,
} from "../hooks/useAdvisor";

function SetupGate({ children }: { children: React.ReactNode }) {
  const status = useAdvisorStatus();
  const setup = useAdvisorSetup();
  const [key, setKey] = useState("");
  if (status.isLoading) return <Card>connecting…</Card>;
  if (status.data?.configured) return <>{children}</>;
  return (
    <Card ai>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
        <KeyRound size={16} style={{ color: "var(--accent-ai)" }} />
        <h3>Connect to Anthropic</h3>
      </div>
      <p style={{ color: "var(--fg-secondary)", fontSize: 13, marginBottom: 14, maxWidth: 560 }}>
        sparkd uses Claude to translate Hugging Face models and box capabilities into vLLM
        recipes. Your key is stored in the OS keyring (Keychain / Secret Service / Credential
        Manager) — never in this repo or its database.
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input
          type="password"
          className="mono"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="sk-ant-..."
          style={{ flex: 1, maxWidth: 480 }}
        />
        <button
          className="ai"
          disabled={!key || setup.isPending}
          onClick={() => setup.mutate({ anthropic_api_key: key })}
        >
          save key
        </button>
      </div>
    </Card>
  );
}

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
        subtitle="Pick a target box and a Hugging Face model. Claude reads the model card and the box's nvidia-smi capabilities, then proposes a vLLM serve recipe with rationale."
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
              <option value="">— target box —</option>
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
              disabled={!boxId || !hfId || busy}
              onClick={async () => {
                setText("");
                setDraft(null);
                const r = await create.mutateAsync({
                  kind: "recipe",
                  target_box_id: boxId,
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
