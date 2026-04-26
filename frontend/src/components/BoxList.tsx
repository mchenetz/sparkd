import { Trash2 } from "lucide-react";

import { Box, useDeleteBox } from "../hooks/useBoxes";
import { Pill } from "./Card";

export default function BoxList({ boxes }: { boxes: Box[] }) {
  const del = useDeleteBox();
  return (
    <table>
      <thead>
        <tr>
          <th style={{ width: "30%" }}>name</th>
          <th>host</th>
          <th>user</th>
          <th>repo</th>
          <th style={{ width: 1 }}></th>
        </tr>
      </thead>
      <tbody>
        {boxes.map((b) => (
          <tr key={b.id}>
            <td>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <Pill tone="info">DGX</Pill>
                <span style={{ fontWeight: 500 }}>{b.name}</span>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "var(--fg-faint)",
                  }}
                >
                  {b.id.slice(0, 8)}
                </span>
              </div>
            </td>
            <td>
              <code style={{ color: "var(--fg-secondary)" }}>
                {b.host}:{b.port}
              </code>
            </td>
            <td>
              <code style={{ color: "var(--fg-muted)" }}>{b.user}</code>
            </td>
            <td>
              <code style={{ color: "var(--fg-muted)" }}>{b.repo_path}</code>
            </td>
            <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
              <button
                className="ghost"
                title="delete"
                onClick={() => del.mutate(b.id)}
              >
                <Trash2 size={14} />
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
