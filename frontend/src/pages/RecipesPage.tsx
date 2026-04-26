import { useState } from "react";

import { Recipe, useDeleteRecipe, useRecipes, useSaveRecipe } from "../hooks/useRecipes";

export default function RecipesPage() {
  const { data } = useRecipes();
  const save = useSaveRecipe();
  const del = useDeleteRecipe();
  const [name, setName] = useState("");
  const [model, setModel] = useState("");
  return (
    <div>
      <h1>Recipes</h1>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate({ name, model, args: {}, env: {}, mods: [] } as Recipe);
          setName("");
          setModel("");
        }}
        style={{ display: "flex", gap: 8, marginBottom: 12 }}
      >
        <input placeholder="name" value={name} onChange={(e) => setName(e.target.value)} />
        <input
          placeholder="model id"
          value={model}
          onChange={(e) => setModel(e.target.value)}
        />
        <button type="submit" disabled={!name || !model}>
          add
        </button>
      </form>
      <ul>
        {(data ?? []).map((r) => (
          <li key={r.name}>
            <code>{r.name}</code> — {r.model}{" "}
            <a href={`/optimize?recipe=${encodeURIComponent(r.name)}`}>optimize</a>{" "}
            <button onClick={() => del.mutate(r.name)}>delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
