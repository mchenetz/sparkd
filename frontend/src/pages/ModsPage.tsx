import { useState } from "react";

import AdvisorChat from "../components/AdvisorChat";
import ModDraftPane from "../components/ModDraftPane";
import {
  ModDraft,
  useCreateAdvisorSession,
  useProposeMod,
} from "../hooks/useAdvisor";
import { useDeleteMod, useMods } from "../hooks/useMods";

export default function ModsPage() {
  const mods = useMods();
  const del = useDeleteMod();
  const create = useCreateAdvisorSession();
  const propose = useProposeMod();
  const [hfId, setHfId] = useState("");
  const [errLog, setErrLog] = useState("");
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<ModDraft | null>(null);
  const busy = create.isPending || propose.isPending;
  return (
    <div>
      <h1>Mods</h1>
      <h2>Existing</h2>
      <ul>
        {(mods.data ?? []).map((m) => (
          <li key={m.name}>
            <code>{m.name}</code> — {m.description}{" "}
            <button onClick={() => del.mutate(m.name)}>delete</button>
          </li>
        ))}
      </ul>
      <h2>Propose new mod (AI)</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
        <input
          placeholder="huggingface/model-id"
          value={hfId}
          onChange={(e) => setHfId(e.target.value)}
          style={{ minWidth: 280 }}
        />
      </div>
      <textarea
        value={errLog}
        onChange={(e) => setErrLog(e.target.value)}
        placeholder="paste error log or failure description"
        style={{ width: "100%", height: 120 }}
      />
      <div style={{ marginTop: 8 }}>
        <button
          disabled={!hfId || !errLog || busy}
          onClick={async () => {
            setText("");
            setDraft(null);
            const r = await create.mutateAsync({
              kind: "mod",
              hf_model_id: hfId,
            });
            const out = await propose.mutateAsync({
              sid: r.id,
              error_log: errLog,
            });
            setText(out.text);
            setDraft(out.draft);
          }}
        >
          propose
        </button>
      </div>
      <AdvisorChat text={text} loading={busy} />
      {draft && <ModDraftPane draft={draft} />}
    </div>
  );
}
