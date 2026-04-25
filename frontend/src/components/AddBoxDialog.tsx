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
        create.mutate({ name, host, user });
        setName("");
        setHost("");
      }}
      style={{ display: "flex", gap: 8, marginBottom: 12 }}
    >
      <input placeholder="name" value={name} onChange={(e) => setName(e.target.value)} />
      <input placeholder="host" value={host} onChange={(e) => setHost(e.target.value)} />
      <input placeholder="user" value={user} onChange={(e) => setUser(e.target.value)} />
      <button type="submit" disabled={!name || !host}>
        add
      </button>
    </form>
  );
}
