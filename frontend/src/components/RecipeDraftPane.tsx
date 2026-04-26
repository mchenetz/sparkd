import { RecipeDraft } from "../hooks/useAdvisor";
import { useSaveRecipe } from "../hooks/useRecipes";

export default function RecipeDraftPane({ draft }: { draft: RecipeDraft }) {
  const save = useSaveRecipe();
  return (
    <div style={{ border: "1px solid #ccc", padding: 12, marginTop: 12 }}>
      <h3>{draft.name}</h3>
      <p>
        <b>Model:</b> {draft.model}
      </p>
      <p>{draft.description}</p>
      <table>
        <tbody>
          {Object.entries(draft.args).map(([k, v]) => (
            <tr key={k}>
              <td>
                <code>{k}</code>
              </td>
              <td>
                <code>{v}</code>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        <i>{draft.rationale}</i>
      </p>
      <button
        onClick={() =>
          save.mutate({
            name: draft.name,
            model: draft.model,
            args: draft.args,
            env: draft.env,
            mods: [],
          })
        }
      >
        save recipe
      </button>
    </div>
  );
}
