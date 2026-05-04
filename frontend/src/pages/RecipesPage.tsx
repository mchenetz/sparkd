import { GitBranch, GitCompare, Plus, Trash2, Wrench, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Card, EmptyState, Pill } from "../components/Card";
import PageHeader from "../components/PageHeader";
import RecipeDiffModal from "../components/RecipeDiffModal";
import UpstreamSync from "../components/UpstreamSync";
import { useDeleteRecipe, useRecipes } from "../hooks/useRecipes";
import { useSyncUpstreamRecipes } from "../hooks/useUpstream";

export default function RecipesPage() {
  const { data } = useRecipes();
  const del = useDeleteRecipe();
  const sync = useSyncUpstreamRecipes();
  const recipes = data ?? [];

  // Selection for "compare two recipes". Using an array (not a Set) so
  // the order reflects the click order — first click = left side of
  // the diff (a), second click = right side (b). Cap at 2.
  const [selected, setSelected] = useState<string[]>([]);
  const [showDiff, setShowDiff] = useState(false);
  function toggleSelect(name: string) {
    setSelected((cur) => {
      if (cur.includes(name)) return cur.filter((n) => n !== name);
      if (cur.length >= 2) return [cur[1], name]; // bump oldest
      return [...cur, name];
    });
  }
  const a = recipes.find((r) => r.name === selected[0]);
  const b = recipes.find((r) => r.name === selected[1]);
  const canCompare = !!a && !!b;
  return (
    <>
      <PageHeader
        eyebrow="Library"
        title={
          <>
            Recipe <em style={{ color: "var(--fg-muted)" }}>library</em>
          </>
        }
        subtitle="Canonical vLLM serve configurations. Click a recipe to edit; per-box overrides merge on top when launching."
        actions={
          <div style={{ display: "flex", gap: 8 }}>
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
            <Link to="/recipes/new" style={{ borderBottom: "none" }}>
              <button className="primary">
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <Plus size={14} /> new recipe
                </span>
              </button>
            </Link>
          </div>
        }
      />

      <div style={{ display: "grid", gap: 24 }}>
        <UpstreamSync label="recipes" sync={sync} />

        {selected.length > 0 && (
          <Card pad={12}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                flexWrap: "wrap",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--fg-muted)",
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                }}
              >
                comparing:
              </span>
              {selected.map((name, i) => (
                <span
                  key={name}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <Pill tone={i === 0 ? "info" : "ai"}>{name}</Pill>
                </span>
              ))}
              {selected.length === 1 && (
                <span
                  style={{
                    fontSize: 12,
                    color: "var(--fg-faint)",
                    fontStyle: "italic",
                  }}
                >
                  pick one more recipe to compare
                </span>
              )}
              <div style={{ flex: 1 }} />
              <button
                className="primary"
                disabled={!canCompare}
                onClick={() => setShowDiff(true)}
              >
                <span
                  style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                >
                  <GitCompare size={13} /> compare diff
                </span>
              </button>
              <button
                className="ghost"
                onClick={() => setSelected([])}
                title="clear selection"
              >
                <X size={13} />
              </button>
            </div>
          </Card>
        )}

        <Card pad={0}>
          {recipes.length === 0 ? (
            <EmptyState
              title="No recipes saved yet"
              hint="Click 'new recipe' above, sync from upstream, or have the Advisor generate one."
            />
          ) : (
            <table>
              <thead>
                <tr>
                  <th style={{ width: 32 }}></th>
                  <th>recipe</th>
                  <th>model</th>
                  <th>flags</th>
                  <th>mods</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {recipes.map((r) => {
                  const flagCount = Object.keys(r.args).length;
                  const isSelected = selected.includes(r.name);
                  return (
                    <tr key={r.name}>
                      <td style={{ width: 32, textAlign: "center" }}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelect(r.name)}
                          aria-label={`select ${r.name} for diff`}
                          style={{ cursor: "pointer" }}
                        />
                      </td>
                      <td>
                        <Link
                          to={`/recipes/${encodeURIComponent(r.name)}`}
                          style={{ borderBottom: "none", color: "var(--fg-primary)" }}
                        >
                          <span style={{ fontWeight: 500 }}>{r.name}</span>
                        </Link>
                      </td>
                      <td>
                        <code style={{ color: "var(--fg-secondary)" }}>{r.model}</code>
                      </td>
                      <td>
                        <code style={{ color: "var(--fg-muted)" }}>
                          {flagCount} flag{flagCount === 1 ? "" : "s"}
                        </code>
                      </td>
                      <td>
                        {r.mods.length === 0 ? (
                          <span style={{ color: "var(--fg-faint)" }}>—</span>
                        ) : (
                          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                            {r.mods.map((m) => (
                              <Link
                                key={m}
                                to={`/mods/${encodeURIComponent(m)}`}
                                style={{ borderBottom: "none" }}
                              >
                                <Pill tone="ai">{m}</Pill>
                              </Link>
                            ))}
                          </div>
                        )}
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

      {showDiff && a && b && (
        <RecipeDiffModal a={a} b={b} onClose={() => setShowDiff(false)} />
      )}
    </>
  );
}
