import { Plus, X } from "lucide-react";
import { useState } from "react";

export default function StringListEditor({
  value,
  onChange,
  placeholder = "value",
  mono = false,
}: {
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  mono?: boolean;
}) {
  const [draft, setDraft] = useState("");
  return (
    <div style={{ display: "grid", gap: 6 }}>
      {value.map((v, i) => (
        <div
          key={i}
          style={{
            display: "grid",
            gridTemplateColumns: "1fr auto",
            gap: 6,
            alignItems: "center",
          }}
        >
          <input
            className={mono ? "mono" : undefined}
            value={v}
            onChange={(e) => {
              const next = [...value];
              next[i] = e.target.value;
              onChange(next);
            }}
          />
          <button
            className="ghost"
            title="remove"
            onClick={() => onChange(value.filter((_, j) => j !== i))}
          >
            <X size={14} />
          </button>
        </div>
      ))}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto",
          gap: 6,
          alignItems: "center",
          paddingTop: value.length > 0 ? 8 : 0,
          borderTop:
            value.length > 0 ? "1px dashed var(--border-subtle)" : "none",
        }}
      >
        <input
          className={mono ? "mono" : undefined}
          placeholder={placeholder}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && draft) {
              e.preventDefault();
              onChange([...value, draft]);
              setDraft("");
            }
          }}
        />
        <button
          className="ghost"
          disabled={!draft}
          onClick={() => {
            if (!draft) return;
            onChange([...value, draft]);
            setDraft("");
          }}
        >
          <Plus size={14} />
        </button>
      </div>
    </div>
  );
}
