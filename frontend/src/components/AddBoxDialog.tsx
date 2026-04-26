import { Plus } from "lucide-react";
import { useState } from "react";

import { useCreateBox } from "../hooks/useBoxes";

export default function AddBoxDialog() {
  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [user, setUser] = useState("ubuntu");
  const create = useCreateBox();
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!name || !host) return;
        create.mutate({ name, host, user });
        setName("");
        setHost("");
      }}
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1.4fr 0.8fr auto",
        gap: 8,
        alignItems: "center",
      }}
    >
      <input
        placeholder="name (e.g. spark-01)"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <input
        className="mono"
        placeholder="host or ip (10.0.0.5)"
        value={host}
        onChange={(e) => setHost(e.target.value)}
      />
      <input
        className="mono"
        placeholder="user"
        value={user}
        onChange={(e) => setUser(e.target.value)}
      />
      <button type="submit" className="primary" disabled={!name || !host}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <Plus size={14} /> add
        </span>
      </button>
    </form>
  );
}
