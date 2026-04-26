import { Check, Copy, FilePlus2, X } from "lucide-react";
import { ReactNode, useState } from "react";
import { useNavigate } from "react-router-dom";

import { RecipeDraft } from "../hooks/useAdvisor";
import { Recipe, useSaveRecipe } from "../hooks/useRecipes";
import { Card, Pill } from "./Card";

const SLUG_RE = /^[a-zA-Z0-9][a-zA-Z0-9_\-.]{0,63}$/;

type Status = "same" | "changed" | "added" | "removed" | "empty";
const TONE: Record<Status, { bg: string; bar: string; fg: string }> = {
  same: { bg: "transparent", bar: "transparent", fg: "var(--fg-secondary)" },
  changed: {
    bg: "rgba(255,181,71,0.06)",
    bar: "var(--signal-warn)",
    fg: "var(--fg-primary)",
  },
  added: {
    bg: "rgba(77,255,166,0.06)",
    bar: "var(--signal-healthy)",
    fg: "var(--fg-primary)",
  },
  removed: {
    bg: "rgba(255,89,97,0.06)",
    bar: "var(--signal-danger)",
    fg: "var(--fg-faint)",
  },
  empty: { bg: "transparent", bar: "transparent", fg: "var(--fg-faint)" },
};

/** Build a "proposed" recipe view that never empties fields the user already
 *  has — the AI sometimes returns blank strings/objects, and we don't want
 *  that to look like the AI is asking to delete a description / mods set. */
function mergeForView(base: Recipe, proposed: RecipeDraft): Recipe {
  return {
    name: base.name,
    model: proposed.model || base.model,
    description: proposed.description || base.description || "",
    args: proposed.args ?? {},
    env: proposed.env ?? {},
    mods: base.mods, // mods aren't carried by the recipe-draft schema
  };
}

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

  const proposedRecipe = mergeForView(base, proposed);

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
              <FilePlus2 size={13} />{" "}
              {creatingNew ? "cancel new" : "create new recipe"}
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
          <div style={{ display: "flex", alignItems: "stretch" }}>
            <input
              autoFocus
              className="mono"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="my-recipe-tuned"
              style={{
                flex: 1,
                borderTopRightRadius: 0,
                borderBottomRightRadius: 0,
              }}
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
          {!newSlugValid && newName ? (
            <span
              style={{
                color: "var(--signal-danger)",
                fontFamily: "var(--font-mono)",
                fontSize: 11,
              }}
            >
              alphanumeric · _ - .  (no spaces)
            </span>
          ) : (
            <span />
          )}
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

      <DiffGrid base={base} proposed={proposedRecipe} proposedName={creatingNew ? newName : base.name} />

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

/** One unified grid so every row aligns horizontally between left/right.
 *  Column 1 is "current" (base), column 2 is "proposed". Section headings
 *  span both columns. */
function DiffGrid({
  base,
  proposed,
  proposedName,
}: {
  base: Recipe;
  proposed: Recipe;
  proposedName: string;
}) {
  const argKeys = unionKeys(base.args, proposed.args);
  const envKeys = unionKeys(base.env, proposed.env);
  const modsLeft = base.mods.join("\n");
  const modsRight = proposed.mods.join("\n");
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 8,
        background: "var(--bg-overlay)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-sm)",
        padding: 12,
      }}
    >
      <Header tone="neutral" label="current" subtitle={base.name} />
      <Header tone="ai" label="proposed" subtitle={proposedName} />

      <SectionRow label="model" />
      <ScalarCell value={base.model} status={statusOfPair(base.model, proposed.model, "left")} />
      <ScalarCell value={proposed.model} status={statusOfPair(proposed.model, base.model, "right")} />

      <SectionRow label="description" />
      <ScalarCell
        value={base.description || ""}
        status={statusOfPair(base.description || "", proposed.description || "", "left")}
        emptyHint
      />
      <ScalarCell
        value={proposed.description || ""}
        status={statusOfPair(proposed.description || "", base.description || "", "right")}
        emptyHint
      />

      {argKeys.length > 0 && <SectionRow label="args" />}
      {argKeys.map((k) => (
        <DictRowPair
          key={`args-${k}`}
          k={k}
          left={base.args[k]}
          right={proposed.args[k]}
        />
      ))}

      {envKeys.length > 0 && <SectionRow label="env" />}
      {envKeys.map((k) => (
        <DictRowPair
          key={`env-${k}`}
          k={k}
          left={base.env[k]}
          right={proposed.env[k]}
        />
      ))}

      {(base.mods.length > 0 || proposed.mods.length > 0) && (
        <SectionRow label="mods" />
      )}
      {(base.mods.length > 0 || proposed.mods.length > 0) && (
        <>
          <ListCell items={base.mods} other={proposed.mods} />
          <ListCell items={proposed.mods} other={base.mods} />
        </>
      )}
    </div>
  );
}

function unionKeys(
  a: Record<string, string>,
  b: Record<string, string>,
): string[] {
  return Array.from(new Set([...Object.keys(a), ...Object.keys(b)])).sort();
}

function statusOfPair(value: string, other: string, side: "left" | "right"): Status {
  if (value === other) return "same";
  if (!value && other) return side === "left" ? "removed" : "added";
  if (value && !other) return side === "left" ? "added" : "removed";
  return "changed";
}

function Header({
  tone,
  label,
  subtitle,
}: {
  tone: "ai" | "neutral";
  label: string;
  subtitle: string;
}) {
  return (
    <div
      style={{
        padding: "8px 10px",
        borderBottom: "1px solid var(--border-subtle)",
        display: "flex",
        alignItems: "baseline",
        gap: 10,
      }}
    >
      <Pill tone={tone}>{label}</Pill>
      <code style={{ fontSize: 12, color: "var(--fg-muted)" }}>{subtitle}</code>
    </div>
  );
}

function SectionRow({ label }: { label: string }) {
  return (
    <div
      style={{
        gridColumn: "1 / -1",
        padding: "10px 4px 4px",
        fontFamily: "var(--font-mono)",
        fontSize: 10.5,
        color: "var(--fg-muted)",
        letterSpacing: "0.16em",
        textTransform: "uppercase",
      }}
    >
      {label}
    </div>
  );
}

function ScalarCell({
  value,
  status,
  emptyHint,
}: {
  value: string;
  status: Status;
  emptyHint?: boolean;
}) {
  const t = TONE[!value && emptyHint ? "empty" : status];
  return (
    <div
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: 12.5,
        color: t.fg,
        padding: "6px 10px",
        background: t.bg,
        borderLeft: `2px solid ${t.bar}`,
        borderRadius: 2,
        wordBreak: "break-word",
        whiteSpace: "pre-wrap",
        minHeight: 28,
      }}
    >
      {value || (emptyHint ? <em style={{ opacity: 0.6 }}>(empty)</em> : "—")}
    </div>
  );
}

function DictRowPair({
  k,
  left,
  right,
}: {
  k: string;
  left: string | undefined;
  right: string | undefined;
}) {
  const status: Status =
    left === undefined && right !== undefined
      ? "added"
      : right === undefined && left !== undefined
      ? "removed"
      : left !== right
      ? "changed"
      : "same";
  return (
    <>
      <DictCell k={k} value={left} status={status} side="left" />
      <DictCell k={k} value={right} status={status} side="right" />
    </>
  );
}

function DictCell({
  k,
  value,
  status,
  side,
}: {
  k: string;
  value: string | undefined;
  status: Status;
  side: "left" | "right";
}) {
  // Determine the per-cell tone — "removed"/"added" only stylize the missing side
  let cellStatus: Status = status;
  if (status === "added" && side === "left") cellStatus = "removed";
  if (status === "removed" && side === "right") cellStatus = "added";
  const t = TONE[cellStatus];
  const present = value !== undefined;
  return (
    <div
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: 12,
        padding: "5px 10px",
        background: t.bg,
        borderLeft: `2px solid ${t.bar}`,
        borderRadius: 2,
        color: t.fg,
        display: "grid",
        gridTemplateColumns: "minmax(0, max-content) 1fr",
        gap: 8,
        wordBreak: "break-all",
        opacity: present ? 1 : 0.55,
      }}
    >
      <span style={{ color: present ? "var(--accent-ai)" : "inherit" }}>{k}</span>
      <span>
        {present ? (
          value || <em style={{ opacity: 0.6 }}>(empty)</em>
        ) : (
          <span style={{ color: "var(--fg-faint)" }}>—</span>
        )}
      </span>
    </div>
  );
}

function ListCell({
  items,
  other,
}: {
  items: string[];
  other: string[];
}): ReactNode {
  const otherSet = new Set(other);
  const itemsSet = new Set(items);
  const all = Array.from(new Set([...items, ...other])).sort();
  return (
    <div
      style={{
        background: "var(--bg-overlay)",
        padding: "5px 10px",
        borderLeft: "2px solid transparent",
        borderRadius: 2,
        fontFamily: "var(--font-mono)",
        fontSize: 12,
        display: "grid",
        gap: 2,
      }}
    >
      {all.map((m) => {
        const here = itemsSet.has(m);
        const there = otherSet.has(m);
        let status: Status = "same";
        if (here && !there) status = "added";
        else if (!here && there) status = "removed";
        const t = TONE[status];
        return (
          <div
            key={m}
            style={{
              padding: "2px 6px",
              background: t.bg,
              borderLeft: `2px solid ${t.bar}`,
              borderRadius: 2,
              color: here ? t.fg : "var(--fg-faint)",
              opacity: here ? 1 : 0.55,
              textDecoration: here ? "none" : "line-through",
            }}
          >
            · {m}
          </div>
        );
      })}
    </div>
  );
}
