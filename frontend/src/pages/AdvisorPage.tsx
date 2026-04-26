import { useState } from "react";

import AdvisorChat from "../components/AdvisorChat";
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
  if (status.isLoading) return <div>loading…</div>;
  if (status.data?.configured) return <>{children}</>;
  return (
    <div>
      <h2>Connect to Anthropic</h2>
      <p>Paste your Anthropic API key (stored in OS keyring).</p>
      <input
        type="password"
        value={key}
        onChange={(e) => setKey(e.target.value)}
        placeholder="sk-ant-..."
        style={{ width: 360 }}
      />{" "}
      <button
        disabled={!key}
        onClick={() => setup.mutate({ anthropic_api_key: key })}
      >
        save
      </button>
    </div>
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
    <SetupGate>
      <h1>Advisor — generate recipe</h1>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <select value={boxId} onChange={(e) => setBoxId(e.target.value)}>
          <option value="">-- target box --</option>
          {(boxes.data ?? []).map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <input
          placeholder="huggingface/model-id"
          value={hfId}
          onChange={(e) => setHfId(e.target.value)}
          style={{ minWidth: 280 }}
        />
        <button
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
          generate
        </button>
      </div>
      <AdvisorChat text={text} loading={busy} />
      {draft && <RecipeDraftPane draft={draft} />}
    </SetupGate>
  );
}
