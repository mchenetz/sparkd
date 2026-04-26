import { ChevronLeft, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Card, EmptyState, Pill } from "../components/Card";
import CodeEditor from "../components/CodeEditor";
import KeyValueEditor from "../components/KeyValueEditor";
import ModPicker from "../components/ModPicker";
import PageHeader from "../components/PageHeader";
import RecipeAIAssist from "../components/RecipeAIAssist";
import RecipeDiffView from "../components/RecipeDiffView";
import Tabs from "../components/Tabs";
import {
  Recipe,
  useDeleteRecipe,
  useRecipe,
  useRecipeRaw,
  useSaveRecipe,
  useUpdateRecipe,
  useUpdateRecipeRaw,
} from "../hooks/useRecipes";

const EMPTY: Recipe = {
  name: "",
  model: "",
  description: "",
  args: {},
  env: {},
  mods: [],
};

export default function RecipeDetailPage() {
  const params = useParams<{ name: string }>();
  const isNew = params.name === "new";
  const name = isNew ? null : params.name ?? null;
  const navigate = useNavigate();
  const detail = useRecipe(name);
  const raw = useRecipeRaw(name);
  const save = useSaveRecipe();
  const update = useUpdateRecipe();
  const updateRaw = useUpdateRecipeRaw();
  const del = useDeleteRecipe();

  const [tab, setTab] = useState<"form" | "yaml" | "diff">("form");
  const [draft, setDraft] = useState<Recipe>(EMPTY);
  const [yamlDraft, setYamlDraft] = useState<string>("");
  const [dirty, setDirty] = useState(false);
  const [pendingDraft, setPendingDraft] = useState<
    import("../hooks/useAdvisor").RecipeDraft | null
  >(null);

  useEffect(() => {
    if (isNew) {
      setDraft(EMPTY);
      return;
    }
    if (detail.data) {
      setDraft(detail.data);
      setDirty(false);
    }
  }, [isNew, detail.data]);

  useEffect(() => {
    if (raw.data) setYamlDraft(raw.data.yaml);
  }, [raw.data]);

  const flagCount = useMemo(() => Object.keys(draft.args).length, [draft.args]);

  if (!isNew && detail.isLoading) return <div>loading…</div>;
  if (!isNew && detail.error)
    return <div style={{ color: "var(--signal-danger)" }}>{String(detail.error)}</div>;

  const setField = <K extends keyof Recipe>(k: K, v: Recipe[K]) => {
    setDraft((d) => ({ ...d, [k]: v }));
    setDirty(true);
  };

  const onFormSave = async () => {
    if (!draft.name || !draft.model) return;
    if (isNew) {
      await save.mutateAsync(draft);
      navigate(`/recipes/${encodeURIComponent(draft.name)}`);
    } else {
      await update.mutateAsync(draft);
      setDirty(false);
    }
  };

  const onYamlSave = async () => {
    if (!name) return;
    await updateRaw.mutateAsync({ name, yaml: yamlDraft });
  };

  return (
    <>
      <PageHeader
        eyebrow={
          <Link to="/recipes" style={{ borderBottom: "none" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <ChevronLeft size={12} /> Recipes
            </span>
          </Link>
        }
        title={
          isNew ? (
            <em style={{ color: "var(--fg-muted)" }}>new recipe</em>
          ) : (
            <>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 28 }}>
                {draft.name}
              </span>
            </>
          )
        }
        subtitle={
          isNew
            ? "Define a recipe by hand or use AI assist to fill it from a Hugging Face model id."
            : draft.model && (
                <code style={{ color: "var(--fg-secondary)" }}>{draft.model}</code>
              )
        }
        actions={
          !isNew && (
            <button
              className="danger"
              onClick={async () => {
                if (!name) return;
                if (!confirm(`delete recipe ${name}?`)) return;
                await del.mutateAsync(name);
                navigate("/recipes");
              }}
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Trash2 size={13} /> delete
              </span>
            </button>
          )
        }
      />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 24 }}>
        <div>
          <Tabs
            active={tab}
            onChange={(id) => setTab(id as "form" | "yaml" | "diff")}
            tabs={[
              { id: "form", label: "Form" },
              { id: "yaml", label: "YAML" },
              ...(pendingDraft
                ? [
                    {
                      id: "diff",
                      label: (
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            color: "var(--accent-ai)",
                          }}
                        >
                          Diff
                          <span
                            style={{
                              padding: "1px 6px",
                              borderRadius: 999,
                              background: "rgba(255,119,51,0.18)",
                              fontSize: 10,
                              fontFamily: "var(--font-mono)",
                            }}
                          >
                            AI
                          </span>
                        </span>
                      ),
                    },
                  ]
                : []),
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
                    placeholder="llama-8b-fp8"
                  />
                </Field>
                <Field label="model" hint="huggingface model id">
                  <input
                    className="mono"
                    value={draft.model}
                    onChange={(e) => setField("model", e.target.value)}
                    placeholder="meta-llama/Llama-3.1-8B-Instruct"
                  />
                </Field>
                <Field label="description">
                  <input
                    value={draft.description ?? ""}
                    onChange={(e) => setField("description", e.target.value)}
                    placeholder="optional human-readable summary"
                  />
                </Field>
                <Field
                  label="args"
                  hint={`vLLM CLI flags · ${flagCount} configured`}
                >
                  <KeyValueEditor
                    value={draft.args}
                    onChange={(v) => setField("args", v)}
                    keyPlaceholder="--tensor-parallel-size"
                    valuePlaceholder="2"
                    monoKey
                  />
                </Field>
                <Field label="env" hint="environment variables">
                  <KeyValueEditor
                    value={draft.env}
                    onChange={(v) => setField("env", v)}
                    keyPlaceholder="VLLM_FOO"
                    valuePlaceholder="1"
                    monoKey
                  />
                </Field>
                <Field label="mods" hint="patches/hooks attached at launch">
                  <ModPicker
                    selected={draft.mods}
                    onChange={(v) => setField("mods", v)}
                  />
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
                  alignItems: "center",
                }}
              >
                {dirty && (
                  <Pill tone="warn">unsaved</Pill>
                )}
                <button
                  className="primary"
                  disabled={!draft.name || !draft.model || save.isPending || update.isPending}
                  onClick={onFormSave}
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <Save size={13} /> {isNew ? "create" : "save"}
                  </span>
                </button>
              </div>
            </Card>
          )}

          {tab === "yaml" && (
            <Card>
              {isNew ? (
                <EmptyState
                  title="Create the recipe first"
                  hint="The YAML view is for editing an existing recipe verbatim. Save via the Form tab first, then come back."
                />
              ) : (
                <>
                  <div
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "var(--fg-muted)",
                      letterSpacing: "0.14em",
                      textTransform: "uppercase",
                      marginBottom: 8,
                    }}
                  >
                    raw yaml — pushed verbatim to the box on launch
                  </div>
                  <CodeEditor value={yamlDraft} onChange={setYamlDraft} height={520} />
                  <div
                    style={{
                      marginTop: 14,
                      display: "flex",
                      gap: 8,
                      justifyContent: "flex-end",
                    }}
                  >
                    <button
                      className="ghost"
                      onClick={() =>
                        raw.data && setYamlDraft(raw.data.yaml)
                      }
                    >
                      reset
                    </button>
                    <button
                      className="primary"
                      disabled={updateRaw.isPending}
                      onClick={onYamlSave}
                    >
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                        <Save size={13} /> save yaml
                      </span>
                    </button>
                  </div>
                  {updateRaw.error ? (
                    <div
                      style={{
                        marginTop: 12,
                        padding: "10px 14px",
                        background: "rgba(255,89,97,0.08)",
                        border: "1px solid rgba(255,89,97,0.3)",
                        borderRadius: "var(--radius-sm)",
                        color: "var(--signal-danger)",
                        fontFamily: "var(--font-mono)",
                        fontSize: 12,
                      }}
                    >
                      {updateRaw.error instanceof Error
                        ? updateRaw.error.message
                        : String(updateRaw.error)}
                    </div>
                  ) : null}
                </>
              )}
            </Card>
          )}

          {tab === "diff" && pendingDraft && (
            <RecipeDiffView
              base={draft}
              proposed={pendingDraft}
              onApply={async () => {
                const next: Recipe = {
                  ...draft,
                  model: pendingDraft.model || draft.model,
                  // Never let an empty AI description blank out the saved one.
                  description:
                    pendingDraft.description || draft.description || "",
                  args: pendingDraft.args ?? {},
                  env: pendingDraft.env ?? {},
                };
                setDraft(next);
                setPendingDraft(null);
                setTab("form");
                // Persist immediately so the recipes list refreshes. For brand
                // new recipes (no name yet) keep the form dirty so the user
                // can fill in name/model and then save.
                if (!isNew && next.name && next.model) {
                  await update.mutateAsync(next);
                  setDirty(false);
                } else {
                  setDirty(true);
                }
              }}
              onDiscard={() => {
                setPendingDraft(null);
                setTab("form");
              }}
            />
          )}
        </div>

        <aside style={{ display: "grid", gap: 16, alignContent: "start" }}>
          <RecipeAIAssist
            recipe={draft}
            onPendingDraft={(d) => {
              setPendingDraft(d);
              if (d) setTab("diff");
            }}
          />
          {!isNew && (
            <Card>
              <h4 style={{ marginBottom: 8 }}>quick actions</h4>
              <div style={{ display: "grid", gap: 6 }}>
                <Link
                  to={`/optimize?recipe=${encodeURIComponent(draft.name)}`}
                  style={{ borderBottom: "none" }}
                >
                  → open in Optimize
                </Link>
                <Link to="/launch" style={{ borderBottom: "none" }}>
                  → open in Launch
                </Link>
              </div>
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
        {hint && (
          <span style={{ fontSize: 11, color: "var(--fg-faint)" }}>· {hint}</span>
        )}
      </div>
      {children}
    </div>
  );
}
