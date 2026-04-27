import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Pill } from "./Card";

type Props = {
  /** Current value. "" means no chip is set. */
  value: string;
  /** Called with the new value. "" to clear. */
  onChange: (next: string) => void;
  /** Existing values to autocomplete from. */
  suggestions: string[];
  placeholder?: string;
  /** Visual tone for the chip pill. Default "info". */
  chipTone?: "info" | "neutral";
};

/**
 * Single-value chip input with autocomplete. Type to filter `suggestions`,
 * Tab/Enter to commit (selected suggestion or typed novel value), and the
 * input is replaced with a removable pill. Click the pill to edit.
 *
 * Why custom (vs. a third-party tag-input lib): keeps the bundle small and
 * matches the project's hand-rolled aesthetic — `Pill` token, monospace,
 * no extra dependencies.
 */
export default function ChipInput({
  value,
  onChange,
  suggestions,
  placeholder,
  chipTone = "info",
}: Props) {
  const [editing, setEditing] = useState(value === "");
  const [draft, setDraft] = useState(value);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setDraft(value);
    setEditing(value === "");
  }, [value]);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const filtered = suggestions
    .filter((s) => s.toLowerCase().includes(draft.toLowerCase()))
    .slice(0, 8);
  const exactMatch = suggestions.includes(draft);

  function commit(next: string) {
    onChange(next);
    setEditing(false);
    setOpen(false);
  }

  function clear() {
    onChange("");
    setDraft("");
    setEditing(true);
  }

  if (!editing && value) {
    return (
      <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
        <button
          type="button"
          onClick={() => setEditing(true)}
          style={{
            background: "transparent",
            border: "none",
            padding: 0,
            cursor: "text",
          }}
          aria-label={`edit ${value}`}
        >
          <Pill tone={chipTone}>
            {value}
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => {
                e.stopPropagation();
                clear();
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  clear();
                }
              }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                marginLeft: 4,
                cursor: "pointer",
              }}
              aria-label={`remove ${value}`}
            >
              <X size={11} />
            </span>
          </Pill>
        </button>
      </span>
    );
  }

  return (
    <div style={{ position: "relative" }}>
      <input
        ref={inputRef}
        className="mono"
        value={draft}
        placeholder={placeholder}
        onChange={(e) => {
          setDraft(e.target.value);
          setOpen(true);
          setHighlight(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === "Tab") {
            const picked =
              open && filtered.length > 0 && filtered[highlight] !== undefined
                ? filtered[highlight]
                : draft.trim();
            if (picked) {
              e.preventDefault();
              commit(picked);
            }
          } else if (e.key === "Escape") {
            setOpen(false);
          } else if (e.key === "ArrowDown") {
            e.preventDefault();
            setHighlight((h) => Math.min(h + 1, filtered.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setHighlight((h) => Math.max(h - 1, 0));
          }
        }}
      />
      {open && (filtered.length > 0 || (draft && !exactMatch)) && (
        <ul
          role="listbox"
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            zIndex: 20,
            margin: "2px 0 0",
            padding: 4,
            listStyle: "none",
            background: "var(--bg-elev-2)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-sm)",
            maxHeight: 200,
            overflowY: "auto",
          }}
        >
          {filtered.map((s, i) => (
            <li
              key={s}
              role="option"
              aria-selected={i === highlight}
              onMouseDown={(e) => {
                e.preventDefault();
                commit(s);
              }}
              onMouseEnter={() => setHighlight(i)}
              style={{
                padding: "4px 8px",
                cursor: "pointer",
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                background:
                  i === highlight ? "var(--bg-overlay)" : "transparent",
                borderRadius: 4,
              }}
            >
              {s}
            </li>
          ))}
          {draft && !exactMatch && (
            <li
              role="option"
              aria-selected={false}
              onMouseDown={(e) => {
                e.preventDefault();
                commit(draft.trim());
              }}
              style={{
                padding: "4px 8px",
                cursor: "pointer",
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--fg-muted)",
                borderTop:
                  filtered.length > 0
                    ? "1px solid var(--border-subtle)"
                    : "none",
                marginTop: filtered.length > 0 ? 4 : 0,
                paddingTop: filtered.length > 0 ? 6 : 4,
              }}
            >
              ↵ create &ldquo;{draft.trim()}&rdquo;
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
