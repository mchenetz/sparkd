import { ChevronLeft, Plus, Save, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Card, EmptyState, Pill } from "../components/Card";
import CodeEditor from "../components/CodeEditor";
import PageHeader from "../components/PageHeader";
import StringListEditor from "../components/StringListEditor";
import Tabs from "../components/Tabs";
import { Mod, useDeleteMod, useMod, useSaveMod, useUpdateMod } from "../hooks/useMods";
import { useRecipes } from "../hooks/useRecipes";

const EMPTY: Mod = {
  name: "",
  target_models: [],
  description: "",
  files: {},
  enabled: true,
};

export default function ModDetailPage() {
  const { name: routeName } = useParams<{ name: string }>();
  const isNew = routeName === "new";
  const name = isNew ? null : routeName ?? null;
  const navigate = useNavigate();
  const detail = useMod(name);
  const recipes = useRecipes();
  const save = useSaveMod();
  const update = useUpdateMod();
  const del = useDeleteMod();

  const [tab, setTab] = useState<"form" | "files">("form");
  const [draft, setDraft] = useState<Mod>(EMPTY);
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [newFileName, setNewFileName] = useState("");

  useEffect(() => {
    if (isNew) {
      setDraft(EMPTY);
      setActiveFile(null);
      return;
    }
    if (detail.data) {
      setDraft(detail.data);
      const first = Object.keys(detail.data.files)[0] ?? null;
      setActiveFile(first);
    }
  }, [isNew, detail.data]);

  const usedBy = useMemo(() => {
    if (!routeName) return [];
    return (recipes.data ?? []).filter((r) => r.mods.includes(routeName));
  }, [recipes.data, routeName]);

  if (!isNew && detail.isLoading) return <div>loading…</div>;
  if (!isNew && detail.error)
    return <div style={{ color: "var(--signal-danger)" }}>{String(detail.error)}</div>;

  const setField = <K extends keyof Mod>(k: K, v: Mod[K]) => {
    setDraft((d) => ({ ...d, [k]: v }));
  };

  const onSave = async () => {
    if (!draft.name) return;
    if (isNew) {
      await save.mutateAsync(draft);
      navigate(`/mods/${encodeURIComponent(draft.name)}`);
    } else {
      await update.mutateAsync(draft);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow={
          <Link to="/mods" style={{ borderBottom: "none" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <ChevronLeft size={12} /> Mods
            </span>
          </Link>
        }
        title={
          isNew ? (
            <em style={{ color: "var(--fg-muted)" }}>new mod</em>
          ) : (
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 28 }}>
              {draft.name}
            </span>
          )
        }
        subtitle={draft.description || undefined}
        actions={
          !isNew && (
            <button
              className="danger"
              onClick={async () => {
                if (!name) return;
                if (!confirm(`delete mod ${name}?`)) return;
                await del.mutateAsync(name);
                navigate("/mods");
              }}
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Trash2 size={13} /> delete
              </span>
            </button>
          )
        }
      />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 24 }}>
        <div>
          <Tabs
            active={tab}
            onChange={(id) => setTab(id as "form" | "files")}
            tabs={[
              { id: "form", label: "Form" },
              {
                id: "files",
                label: (
                  <>
                    Files
                    <span
                      style={{
                        marginLeft: 6,
                        color: "var(--fg-faint)",
                        fontSize: 11,
                      }}
                    >
                      {Object.keys(draft.files).length}
                    </span>
                  </>
                ),
              },
            ]}
          />

          {tab === "form" && (
            <Card>
              <div style={{ display: "grid", gap: 18 }}>
                <Field label="name">
                  <input
                    className="mono"
                    value={draft.name}
                    disabled={!isNew}
                    onChange={(e) => setField("name", e.target.value)}
                    placeholder="fix-some-model"
                  />
                </Field>
                <Field label="description">
                  <input
                    value={draft.description}
                    onChange={(e) => setField("description", e.target.value)}
                    placeholder="what does this mod fix?"
                  />
                </Field>
                <Field label="targets" hint="hf model ids this mod applies to">
                  <StringListEditor
                    value={draft.target_models}
                    onChange={(v) => setField("target_models", v)}
                    placeholder="org/model"
                    mono
                  />
                </Field>
                <Field label="enabled">
                  <label
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                      fontSize: 13,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={draft.enabled}
                      onChange={(e) => setField("enabled", e.target.checked)}
                    />
                    <span style={{ color: "var(--fg-secondary)" }}>
                      apply when launching matching recipes
                    </span>
                  </label>
                </Field>
              </div>
              <div
                style={{
                  marginTop: 24,
                  paddingTop: 18,
                  borderTop: "1px solid var(--border-subtle)",
                  display: "flex",
                  gap: 8,
                  justifyContent: "flex-end",
                }}
              >
                <button
                  className="primary"
                  disabled={!draft.name || save.isPending || update.isPending}
                  onClick={onSave}
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <Save size={13} /> {isNew ? "create" : "save"}
                  </span>
                </button>
              </div>
            </Card>
          )}

          {tab === "files" && (
            <Card pad={0}>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "200px 1fr",
                  minHeight: 480,
                }}
              >
                <div
                  style={{
                    borderRight: "1px solid var(--border-subtle)",
                    background: "var(--bg-elev-1)",
                    padding: 12,
                  }}
                >
                  <div
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10.5,
                      color: "var(--fg-muted)",
                      letterSpacing: "0.14em",
                      textTransform: "uppercase",
                      padding: "4px 8px 8px",
                    }}
                  >
                    files
                  </div>
                  <div style={{ display: "grid", gap: 2 }}>
                    {Object.keys(draft.files).map((f) => (
                      <button
                        key={f}
                        className="ghost"
                        onClick={() => setActiveFile(f)}
                        style={{
                          textAlign: "left",
                          padding: "6px 8px",
                          background:
                            activeFile === f ? "var(--bg-elev-3)" : "transparent",
                          color:
                            activeFile === f ? "var(--fg-primary)" : "var(--fg-secondary)",
                          fontFamily: "var(--font-mono)",
                          fontSize: 12,
                        }}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                  <div
                    style={{
                      marginTop: 12,
                      paddingTop: 12,
                      borderTop: "1px dashed var(--border-subtle)",
                      display: "flex",
                      gap: 4,
                    }}
                  >
                    <input
                      className="mono"
                      placeholder="new-file"
                      value={newFileName}
                      onChange={(e) => setNewFileName(e.target.value)}
                      style={{ flex: 1, fontSize: 11 }}
                    />
                    <button
                      className="ghost"
                      disabled={!newFileName || newFileName in draft.files}
                      onClick={() => {
                        if (!newFileName) return;
                        setField("files", { ...draft.files, [newFileName]: "" });
                        setActiveFile(newFileName);
                        setNewFileName("");
                      }}
                    >
                      <Plus size={12} />
                    </button>
                  </div>
                </div>

                <div style={{ padding: 12 }}>
                  {!activeFile ? (
                    <EmptyState title="No file selected" />
                  ) : (
                    <>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          marginBottom: 8,
                        }}
                      >
                        <code style={{ fontSize: 12, color: "var(--fg-secondary)" }}>
                          {activeFile}
                        </code>
                        <button
                          className="ghost"
                          title="remove file"
                          onClick={() => {
                            const next = { ...draft.files };
                            delete next[activeFile];
                            setField("files", next);
                            const remaining = Object.keys(next);
                            setActiveFile(remaining[0] ?? null);
                          }}
                        >
                          <X size={13} />
                        </button>
                      </div>
                      <CodeEditor
                        value={draft.files[activeFile] ?? ""}
                        onChange={(v) =>
                          setField("files", { ...draft.files, [activeFile]: v })
                        }
                        height={420}
                      />
                    </>
                  )}
                </div>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  padding: 12,
                  borderTop: "1px solid var(--border-subtle)",
                }}
              >
                <button
                  className="primary"
                  disabled={!draft.name || save.isPending || update.isPending}
                  onClick={onSave}
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <Save size={13} /> save
                  </span>
                </button>
              </div>
            </Card>
          )}
        </div>

        <aside style={{ display: "grid", gap: 16, alignContent: "start" }}>
          {!isNew && (
            <Card>
              <h4 style={{ marginBottom: 10 }}>used by</h4>
              {usedBy.length === 0 ? (
                <div style={{ color: "var(--fg-faint)", fontSize: 12, fontStyle: "italic" }}>
                  no recipe references this mod
                </div>
              ) : (
                <div style={{ display: "grid", gap: 6 }}>
                  {usedBy.map((r) => (
                    <Link
                      key={r.name}
                      to={`/recipes/${encodeURIComponent(r.name)}`}
                      style={{ borderBottom: "none" }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <Pill tone="info">recipe</Pill>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                          {r.name}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </Card>
          )}
        </aside>
      </div>
    </>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 6 }}>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--fg-muted)",
            letterSpacing: "0.16em",
            textTransform: "uppercase",
          }}
        >
          {label}
        </span>
        {hint && <span style={{ fontSize: 11, color: "var(--fg-faint)" }}>· {hint}</span>}
      </div>
      {children}
    </div>
  );
}
