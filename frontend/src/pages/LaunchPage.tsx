import { useState } from "react";

import LiveLog from "../components/LiveLog";
import { useBoxes } from "../hooks/useBoxes";
import { useCreateLaunch, useLaunches, useStopLaunch } from "../hooks/useLaunches";
import { useRecipes } from "../hooks/useRecipes";

export default function LaunchPage() {
  const { data: boxes } = useBoxes();
  const { data: recipes } = useRecipes();
  const create = useCreateLaunch();
  const stop = useStopLaunch();
  const [box, setBox] = useState("");
  const [recipe, setRecipe] = useState("");
  const launches = useLaunches();
  return (
    <div>
      <h1>Launch</h1>
      <div style={{ display: "flex", gap: 8 }}>
        <select value={box} onChange={(e) => setBox(e.target.value)}>
          <option value="">-- box --</option>
          {(boxes ?? []).map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <select value={recipe} onChange={(e) => setRecipe(e.target.value)}>
          <option value="">-- recipe --</option>
          {(recipes ?? []).map((r) => (
            <option key={r.name} value={r.name}>
              {r.name}
            </option>
          ))}
        </select>
        <button
          disabled={!box || !recipe}
          onClick={() => create.mutate({ recipe, box_id: box })}
        >
          launch
        </button>
      </div>
      <h2>Active launches</h2>
      <ul>
        {(launches.data ?? []).map((l) => (
          <li key={l.id}>
            <code>{l.recipe_name}</code> on <code>{l.box_id}</code> — {l.state}{" "}
            <button onClick={() => stop.mutate(l.id)}>stop</button>
            <LiveLog launchId={l.id} />
          </li>
        ))}
      </ul>
    </div>
  );
}
