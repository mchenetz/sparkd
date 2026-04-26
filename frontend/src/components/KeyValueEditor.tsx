import { Plus, X } from "lucide-react";
import { useState } from "react";

export default function KeyValueEditor({
  value,
  onChange,
  keyPlaceholder = "key",
  valuePlaceholder = "value",
  monoKey = false,
}: {
  value: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
  keyPlaceholder?: string;
  valuePlaceholder?: string;
  monoKey?: boolean;
}) {
  const [k, setK] = useState("");
  const [v, setV] = useState("");
  const entries = Object.entries(value);
  return (
    <div style={{ display: "grid", gap: 6 }}>
      {entries.map(([key, val]) => (
        <div
          key={key}
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr auto",
            gap: 6,
            alignItems: "center",
          }}
        >
          <input
            className={monoKey ? "mono" : undefined}
            value={key}
            onChange={(e) => {
              const newKey = e.target.value;
              if (!newKey || newKey === key) return;
              const next: Record<string, string> = {};
              for (const [ek, ev] of entries) next[ek === key ? newKey : ek] = ev;
              onChange(next);
            }}
          />
          <input
            className={monoKey ? "mono" : undefined}
            value={val}
            onChange={(e) => onChange({ ...value, [key]: e.target.value })}
          />
          <button
            className="ghost"
            title="remove"
            onClick={() => {
              const next = { ...value };
              delete next[key];
              onChange(next);
            }}
          >
            <X size={14} />
          </button>
        </div>
      ))}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr auto",
          gap: 6,
          alignItems: "center",
          paddingTop: entries.length > 0 ? 8 : 0,
          borderTop:
            entries.length > 0 ? "1px dashed var(--border-subtle)" : "none",
        }}
      >
        <input
          className={monoKey ? "mono" : undefined}
          placeholder={keyPlaceholder}
          value={k}
          onChange={(e) => setK(e.target.value)}
        />
        <input
          className={monoKey ? "mono" : undefined}
          placeholder={valuePlaceholder}
          value={v}
          onChange={(e) => setV(e.target.value)}
        />
        <button
          className="ghost"
          disabled={!k}
          onClick={() => {
            if (!k) return;
            onChange({ ...value, [k]: v });
            setK("");
            setV("");
          }}
        >
          <Plus size={14} />
        </button>
      </div>
    </div>
  );
}
