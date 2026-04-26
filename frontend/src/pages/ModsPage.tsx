import { Plus, Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import AdvisorChat from "../components/AdvisorChat";
import { Card, EmptyState, Pill } from "../components/Card";
import ModDraftPane from "../components/ModDraftPane";
import PageHeader from "../components/PageHeader";
import SetupGate from "../components/SetupGate";
import UpstreamSync from "../components/UpstreamSync";
import {
  ModDraft,
  useCreateAdvisorSession,
  useProposeMod,
} from "../hooks/useAdvisor";
import { useDeleteMod, useMods } from "../hooks/useMods";
import { useSyncUpstreamMods } from "../hooks/useUpstream";

export default function ModsPage() {
  const mods = useMods();
  const del = useDeleteMod();
  const sync = useSyncUpstreamMods();
  const create = useCreateAdvisorSession();
  const propose = useProposeMod();
  const [hfId, setHfId] = useState("");
  const [errLog, setErrLog] = useState("");
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<ModDraft | null>(null);
  const busy = create.isPending || propose.isPending;
  const list = mods.data ?? [];
  return (
    <>
      <PageHeader
        eyebrow="Compatibility"
        title={
          <>
            Mods <em style={{ color: "var(--fg-muted)" }}>& patches</em>
          </>
        }
        subtitle="Per-model fixes (patches, hooks) applied alongside a recipe. Click a mod to edit; sync the upstream catalog or have Claude propose a fix from an error log."
        actions={
          <Link to="/mods/new" style={{ borderBottom: "none" }}>
            <button className="primary">
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Plus size={14} /> new mod
              </span>
            </button>
          </Link>
        }
      />

      <div style={{ display: "grid", gap: 24 }}>
        <UpstreamSync label="mods" sync={sync} />

        <div>
          <h4 style={{ marginBottom: 12 }}>installed</h4>
          <Card pad={0}>
            {list.length === 0 ? (
              <EmptyState
                title="No mods saved yet"
                hint="Sync upstream above, or use the AI panel below to author one from an error log."
              />
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>name</th>
                    <th>targets</th>
                    <th>files</th>
                    <th>enabled</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((m) => (
                    <tr key={m.name}>
                      <td>
                        <Link
                          to={`/mods/${encodeURIComponent(m.name)}`}
                          style={{ borderBottom: "none", color: "var(--fg-primary)" }}
                        >
                          <div>
                            <span style={{ fontWeight: 500 }}>{m.name}</span>
                            {m.description && (
                              <div
                                style={{ color: "var(--fg-muted)", fontSize: 12 }}
                              >
                                {m.description}
                              </div>
                            )}
                          </div>
                        </Link>
                      </td>
                      <td>
                        {m.target_models.length > 0 ? (
                          m.target_models.map((t) => (
                            <code
                              key={t}
                              style={{ color: "var(--fg-secondary)", marginRight: 8 }}
                            >
                              {t}
                            </code>
                          ))
                        ) : (
                          <span style={{ color: "var(--fg-faint)" }}>any</span>
                        )}
                      </td>
                      <td>
                        <code style={{ color: "var(--fg-muted)" }}>
                          {Object.keys(m.files).length}
                        </code>
                      </td>
                      <td>
                        <Pill tone={m.enabled ? "healthy" : "neutral"}>
                          {m.enabled ? "on" : "off"}
                        </Pill>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          className="ghost"
                          onClick={() => del.mutate(m.name)}
                          title="delete"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>

        <div>
          <h4 style={{ marginBottom: 12 }}>propose new mod (AI)</h4>
          <SetupGate>
            <Card ai>
              <div style={{ display: "grid", gap: 10 }}>
                <input
                  className="mono"
                  placeholder="huggingface/model-id"
                  value={hfId}
                  onChange={(e) => setHfId(e.target.value)}
                />
                <textarea
                  value={errLog}
                  onChange={(e) => setErrLog(e.target.value)}
                  placeholder="Paste the error log, traceback, or describe the failure in detail."
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    minHeight: 120,
                    resize: "vertical",
                  }}
                />
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <button
                    className="ai"
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
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <Sparkles size={14} /> propose
                    </span>
                  </button>
                </div>
              </div>
            </Card>
            <AdvisorChat text={text} loading={busy} />
            {draft && <ModDraftPane draft={draft} />}
          </SetupGate>
        </div>
      </div>
    </>
  );
}
