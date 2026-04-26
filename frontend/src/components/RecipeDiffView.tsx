import { Check, Copy, FilePlus2, X } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { RecipeDraft } from "../hooks/useAdvisor";
import { Recipe, useSaveRecipe } from "../hooks/useRecipes";
import { Card, Pill } from "./Card";

const SLUG_RE = /^[a-zA-Z0-9][a-zA-Z0-9_\-.]{0,63}$/;

type Status = "same" | "changed" | "added" | "removed";
const TONE: Record<Status, { bg: string; bar: string }> = {
  same: { bg: "transparent", bar: "transparent" },
  changed: { bg: "rgba(255,181,71,0.06)", bar: "var(--signal-warn)" },
  added: { bg: "rgba(77,255,166,0.06)", bar: "var(--signal-healthy)" },
  removed: { bg: "rgba(255,89,97,0.06)", bar: "var(--signal-danger)" },
};

export default function RecipeDiffView({
  base,
  proposed,
  onApply,
  onDiscard,
}: {
  base: Recipe;
  proposed: RecipeDraft;
  onApply: () => void;
  onDiscard: () => void;
}) {
  const save = useSaveRecipe();
  const navigate = useNavigate();
  const [creatingNew, setCreatingNew] = useState(false);
  const [newName, setNewName] = useState(`${base.name || "recipe"}-tuned`);
  const newSlugValid = SLUG_RE.test(newName);

  const proposedRecipe: Recipe = {
    name: newName || base.name,
    model: proposed.model || base.model,
    description: proposed.description ?? base.description ?? "",
    args: proposed.args ?? {},
    env: proposed.env ?? {},
    mods: base.mods,
  };

  return (
    <Card ai>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: 16,
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div>
          <Pill tone="ai">proposed change</Pill>
          <h3 style={{ marginTop: 6 }}>Diff</h3>
          <p style={{ color: "var(--fg-muted)", fontSize: 13, marginTop: 4 }}>
            Apply replaces matching fields in this recipe's form. Create new
            saves the proposed values as a separate recipe so you can keep
            both. Discard drops the suggestion.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="ghost" onClick={onDiscard} disabled={save.isPending}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <X size={13} /> discard
            </span>
          </button>
          <button className="ghost" onClick={onApply} disabled={save.isPending}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <Check size={13} /> apply to form
            </span>
          </button>
          <button
            className="ai"
            onClick={() => setCreatingNew((v) => !v)}
            disabled={save.isPending}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <FilePlus2 size={13} /> {creatingNew ? "cancel new" : "create new recipe"}
            </span>
          </button>
        </div>
      </div>

      {creatingNew && (
        <div
          style={{
            marginBottom: 16,
            padding: "12px 16px",
            background: "var(--bg-elev-2)",
            border: "1px solid rgba(255,119,51,0.25)",
            borderRadius: "var(--radius-sm)",
            display: "grid",
            gridTemplateColumns: "auto 1fr auto auto",
            gap: 10,
            alignItems: "center",
          }}
        >
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--fg-muted)",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
            }}
          >
            new recipe name
          </span>
          <div style={{ display: "flex", alignItems: "stretch", gap: 0 }}>
            <input
              autoFocus
              className="mono"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="my-recipe-tuned"
              style={{ flex: 1, borderTopRightRadius: 0, borderBottomRightRadius: 0 }}
            />
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                padding: "0 12px",
                background: "var(--bg-elev-3)",
                border: "1px solid var(--border-subtle)",
                borderLeft: "none",
                borderTopRightRadius: "var(--radius-sm)",
                borderBottomRightRadius: "var(--radius-sm)",
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                color: "var(--fg-muted)",
              }}
            >
              .yaml
            </span>
          </div>
          {!newSlugValid && newName && (
            <span
              style={{
                color: "var(--signal-danger)",
                fontFamily: "var(--font-mono)",
                fontSize: 11,
              }}
            >
              alphanumeric · _ - .  (no spaces)
            </span>
          )}
          {newSlugValid && <span />}
          <button
            className="primary"
            disabled={!newSlugValid || save.isPending}
            onClick={async () => {
              await save.mutateAsync({
                name: newName,
                model: proposedRecipe.model,
                description: proposedRecipe.description,
                args: proposedRecipe.args,
                env: proposedRecipe.env,
                mods: proposedRecipe.mods,
              });
              navigate(`/recipes/${encodeURIComponent(newName)}`);
            }}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <Copy size={13} /> save as new
            </span>
          </button>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Column title="current" subtitle={base.name} recipe={base} other={proposedRecipe} side="left" />
        <Column
          title="proposed"
          subtitle={creatingNew ? newName : base.name}
          recipe={proposedRecipe}
          other={base}
          side="right"
        />
      </div>

      {proposed.rationale && (
        <div
          style={{
            marginTop: 18,
            padding: "12px 16px",
            borderLeft: "2px solid var(--accent-ai)",
            background: "rgba(255,119,51,0.05)",
            color: "var(--fg-secondary)",
            fontStyle: "italic",
            fontSize: 13,
          }}
        >
          {proposed.rationale}
        </div>
      )}
    </Card>
  );
}

function classify(value: string, otherValue: string | undefined, side: "left" | "right"): Status {
  if (otherValue === undefined) return side === "right" ? "added" : "removed";
  if (value === otherValue) return "same";
  return "changed";
}

function Column({
  title,
  subtitle,
  recipe,
  other,
  side,
}: {
  title: string;
  subtitle: string;
  recipe: Recipe;
  other: Recipe;
  side: "left" | "right";
}) {
  const tone = title === "proposed" ? "ai" : "neutral";
  return (
    <div
      style={{
        background: "var(--bg-overlay)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-sm)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "10px 14px",
          background: "var(--bg-elev-2)",
          borderBottom: "1px solid var(--border-subtle)",
          display: "flex",
          alignItems: "baseline",
          gap: 10,
        }}
      >
        <Pill tone={tone}>{title}</Pill>
        <code style={{ fontSize: 12, color: "var(--fg-muted)" }}>{subtitle}</code>
      </div>
      <div style={{ padding: 12, display: "grid", gap: 12 }}>
        <ScalarRow
          label="model"
          value={recipe.model}
          status={classify(recipe.model, other.model, side)}
        />
        {(recipe.description || other.description) && (
          <ScalarRow
            label="description"
            value={recipe.description || ""}
            status={classify(
              recipe.description || "",
              other.description || "",
              side,
            )}
          />
        )}
        <DictBlock label="args" dict={recipe.args} other={other.args} side={side} />
        <DictBlock label="env" dict={recipe.env} other={other.env} side={side} />
        {recipe.mods.length > 0 && <ListBlock label="mods" items={recipe.mods} />}
      </div>
    </div>
  );
}

function ScalarRow({
  label,
  value,
  status,
}: {
  label: string;
  value: string;
  status: Status;
}) {
  const t = TONE[status];
  return (
    <div>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10.5,
          color: "var(--fg-muted)",
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 12.5,
          color: status === "same" ? "var(--fg-secondary)" : "var(--fg-primary)",
          padding: "6px 10px",
          background: t.bg,
          borderLeft: `2px solid ${t.bar}`,
          borderRadius: 2,
          wordBreak: "break-all",
        }}
      >
        {value || <span style={{ color: "var(--fg-faint)" }}>(empty)</span>}
      </div>
    </div>
  );
}

function DictBlock({
  label,
  dict,
  other,
  side,
}: {
  label: string;
  dict: Record<string, string>;
  other: Record<string, string>;
  side: "left" | "right";
}) {
  // Union of keys across both sides so the rows align between the columns.
  const keys = Array.from(new Set([...Object.keys(other), ...Object.keys(dict)])).sort();
  if (keys.length === 0) return null;
  return (
    <div>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10.5,
          color: "var(--fg-muted)",
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div style={{ display: "grid", gap: 2 }}>
        {keys.map((k) => {
          const present = k in dict;
          const v = present ? dict[k] : "";
          let status: Status;
          if (!present) {
            status = side === "left" ? "added" : "removed";
          } else if (!(k in other)) {
            status = side === "right" ? "added" : "removed";
          } else if (other[k] !== v) {
            status = "changed";
          } else {
            status = "same";
          }
          const t = TONE[status];
          return (
            <div
              key={k}
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                padding: "4px 10px",
                background: t.bg,
                borderLeft: `2px solid ${t.bar}`,
                borderRadius: 2,
                display: "grid",
                gridTemplateColumns: "minmax(0, auto) 1fr",
                gap: 8,
                color:
                  status === "same"
                    ? "var(--fg-secondary)"
                    : status === "removed" && !present
                    ? "var(--fg-faint)"
                    : "var(--fg-primary)",
                opacity: status === "removed" && !present ? 0.5 : 1,
                textDecoration:
                  status === "removed" && !present ? "line-through" : "none",
              }}
            >
              <span style={{ color: "var(--accent-ai)" }}>{k}</span>
              <span style={{ wordBreak: "break-all" }}>
                {present ? v || <em style={{ opacity: 0.6 }}>(empty)</em> : "—"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ListBlock({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10.5,
          color: "var(--fg-muted)",
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div style={{ display: "grid", gap: 2 }}>
        {items.map((it) => (
          <div
            key={it}
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              padding: "4px 10px",
              color: "var(--fg-secondary)",
            }}
          >
            · {it}
          </div>
        ))}
      </div>
    </div>
  );
}
