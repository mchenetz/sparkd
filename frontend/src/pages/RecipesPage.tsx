import { CloudDownload, GitBranch, Plus, Trash2, Wrench } from "lucide-react";
import { useState } from "react";

import { Card, EmptyState, Pill } from "../components/Card";
import PageHeader from "../components/PageHeader";
import {
  Recipe,
  useDeleteRecipe,
  useRecipes,
  useSaveRecipe,
} from "../hooks/useRecipes";
import { UpstreamSyncResult, useSyncUpstream } from "../hooks/useUpstream";

const DEFAULT_REPO = "eugr/spark-vllm-docker";
const DEFAULT_BRANCH = "main";

function UpstreamSummary({ result }: { result: UpstreamSyncResult }) {
  const total = result.imported.length + result.skipped.length + result.errors.length;
  if (total === 0) return null;
  return (
    <div
      style={{
        marginTop: 14,
        padding: "12px 14px",
        background: "var(--bg-overlay)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-sm)",
        fontFamily: "var(--font-mono)",
        fontSize: 12,
        display: "grid",
        gap: 6,
      }}
    >
      <div style={{ display: "flex", gap: 14, color: "var(--fg-muted)" }}>
        <span>
          <span style={{ color: "var(--signal-healthy)" }}>
            {result.imported.length}
          </span>{" "}
          imported
        </span>
        <span>
          <span style={{ color: "var(--fg-secondary)" }}>{result.skipped.length}</span>{" "}
          skipped
        </span>
        <span>
          <span style={{ color: "var(--signal-danger)" }}>{result.errors.length}</span>{" "}
          errors
        </span>
        <span style={{ flex: 1 }} />
        <span style={{ color: "var(--fg-faint)" }}>
          {result.repo}@{result.branch}
        </span>
      </div>
      {result.imported.length > 0 && (
        <details>
          <summary
            style={{
              cursor: "pointer",
              color: "var(--signal-healthy)",
            }}
          >
            imported
          </summary>
          <div style={{ paddingLeft: 14, color: "var(--fg-secondary)" }}>
            {result.imported.map((n) => (
              <div key={n}>+ {n}</div>
            ))}
          </div>
        </details>
      )}
      {result.skipped.length > 0 && (
        <details>
          <summary style={{ cursor: "pointer", color: "var(--fg-secondary)" }}>
            skipped (use force to overwrite)
          </summary>
          <div style={{ paddingLeft: 14, color: "var(--fg-muted)" }}>
            {result.skipped.map((n) => (
              <div key={n}>= {n}</div>
            ))}
          </div>
        </details>
      )}
      {result.errors.length > 0 && (
        <details open>
          <summary style={{ cursor: "pointer", color: "var(--signal-danger)" }}>
            errors
          </summary>
          <div style={{ paddingLeft: 14, color: "var(--signal-danger)" }}>
            {result.errors.map((e) => (
              <div key={e.name}>
                ! {e.name}: {e.message}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function UpstreamSync() {
  const [repo, setRepo] = useState(DEFAULT_REPO);
  const [branch, setBranch] = useState(DEFAULT_BRANCH);
  const [force, setForce] = useState(false);
  const [open, setOpen] = useState(false);
  const sync = useSyncUpstream();
  return (
    <Card>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-muted)",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              marginBottom: 4,
            }}
          >
            upstream sync
          </div>
          <div style={{ fontSize: 13, color: "var(--fg-secondary)" }}>
            Pull recipes from{" "}
            <code style={{ color: "var(--fg-primary)" }}>{repo}</code>
            <span style={{ color: "var(--fg-faint)" }}>@</span>
            <code style={{ color: "var(--fg-primary)" }}>{branch}</code>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="ghost" onClick={() => setOpen((o) => !o)}>
            {open ? "hide" : "configure"}
          </button>
          <button
            className="primary"
            disabled={sync.isPending}
            onClick={() => sync.mutate({ repo, branch, force })}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <CloudDownload size={14} />
              {sync.isPending ? "syncing…" : "sync"}
            </span>
          </button>
        </div>
      </div>
      {open && (
        <div
          style={{
            marginTop: 14,
            display: "grid",
            gridTemplateColumns: "2fr 1fr auto",
            gap: 8,
            alignItems: "center",
          }}
        >
          <input
            className="mono"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder="owner/repo"
          />
          <input
            className="mono"
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
            placeholder="branch"
          />
          <label
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              color: "var(--fg-secondary)",
            }}
          >
            <input
              type="checkbox"
              checked={force}
              onChange={(e) => setForce(e.target.checked)}
            />
            overwrite existing
          </label>
        </div>
      )}
      {sync.data && <UpstreamSummary result={sync.data} />}
      {sync.error && (
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
          {String(sync.error)}
        </div>
      )}
    </Card>
  );
}

export default function RecipesPage() {
  const { data } = useRecipes();
  const save = useSaveRecipe();
  const del = useDeleteRecipe();
  const [name, setName] = useState("");
  const [model, setModel] = useState("");
  const recipes = data ?? [];
  return (
    <>
      <PageHeader
        eyebrow="Library"
        title={
          <>
            Recipe <em style={{ color: "var(--fg-muted)" }}>library</em>
          </>
        }
        subtitle="Canonical vLLM serve configurations. Per-box overrides merge on top when launching."
        actions={
          <a
            href="https://github.com/eugr/spark-vllm-docker"
            target="_blank"
            rel="noreferrer"
            style={{ borderBottom: "none" }}
            title="upstream repo"
          >
            <button className="ghost">
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <GitBranch size={14} /> upstream
              </span>
            </button>
          </a>
        }
      />

      <div style={{ display: "grid", gap: 24 }}>
        <UpstreamSync />

        <Card>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-muted)",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              marginBottom: 12,
            }}
          >
            new recipe
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!name || !model) return;
              save.mutate({ name, model, args: {}, env: {}, mods: [] } as Recipe);
              setName("");
              setModel("");
            }}
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 2fr auto",
              gap: 8,
            }}
          >
            <input
              className="mono"
              placeholder="recipe slug (llama-8b-fp8)"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <input
              className="mono"
              placeholder="huggingface/model-id"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
            <button type="submit" className="primary" disabled={!name || !model}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Plus size={14} /> save
              </span>
            </button>
          </form>
        </Card>

        <Card pad={0}>
          {recipes.length === 0 ? (
            <EmptyState
              title="No recipes saved yet"
              hint="Add one above, sync from upstream, or have the Advisor generate one."
            />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>recipe</th>
                  <th>model</th>
                  <th>flags</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {recipes.map((r) => {
                  const flagCount = Object.keys(r.args).length;
                  return (
                    <tr key={r.name}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <span style={{ fontWeight: 500 }}>{r.name}</span>
                          {r.mods.length > 0 && <Pill tone="ai">{r.mods.length} mod</Pill>}
                        </div>
                      </td>
                      <td>
                        <code style={{ color: "var(--fg-secondary)" }}>{r.model}</code>
                      </td>
                      <td>
                        <code style={{ color: "var(--fg-muted)" }}>
                          {flagCount} flag{flagCount === 1 ? "" : "s"}
                        </code>
                      </td>
                      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                        <a
                          href={`/optimize?recipe=${encodeURIComponent(r.name)}`}
                          style={{ borderBottom: "none" }}
                        >
                          <button className="ghost" title="optimize with AI">
                            <span
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 4,
                                color: "var(--accent-ai)",
                              }}
                            >
                              <Wrench size={13} /> optimize
                            </span>
                          </button>
                        </a>
                        <button
                          className="ghost"
                          onClick={() => del.mutate(r.name)}
                          title="delete"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </>
  );
}
