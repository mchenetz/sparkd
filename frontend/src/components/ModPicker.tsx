import { Plus, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useMods } from "../hooks/useMods";

export default function ModPicker({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const mods = useMods();
  const [pick, setPick] = useState("");
  const available = (mods.data ?? []).map((m) => m.name);
  const remaining = available.filter((n) => !selected.includes(n));
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {selected.length === 0 ? (
        <div
          style={{
            color: "var(--fg-faint)",
            fontStyle: "italic",
            fontSize: 13,
          }}
        >
          no mods attached
        </div>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {selected.map((name) => (
            <span
              key={name}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "4px 6px 4px 10px",
                background: "rgba(255,119,51,0.08)",
                border: "1px solid rgba(255,119,51,0.25)",
                borderRadius: 999,
                fontSize: 12,
                fontFamily: "var(--font-mono)",
                color: "var(--accent-ai)",
              }}
            >
              <Link
                to={`/mods/${encodeURIComponent(name)}`}
                style={{ color: "inherit", borderBottom: "none" }}
              >
                {name}
              </Link>
              <button
                className="ghost"
                title="remove"
                onClick={() => onChange(selected.filter((n) => n !== name))}
                style={{ padding: "0 2px", color: "var(--accent-ai)" }}
              >
                <X size={11} />
              </button>
            </span>
          ))}
        </div>
      )}
      {remaining.length > 0 && (
        <div style={{ display: "flex", gap: 6 }}>
          <select
            value={pick}
            onChange={(e) => setPick(e.target.value)}
            style={{ flex: 1 }}
          >
            <option value="">— add a mod —</option>
            {remaining.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <button
            className="ghost"
            disabled={!pick}
            onClick={() => {
              if (!pick) return;
              onChange([...selected, pick]);
              setPick("");
            }}
          >
            <Plus size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
