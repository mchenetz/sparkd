import { ModDraft } from "../hooks/useAdvisor";
import { useSaveMod } from "../hooks/useMods";

export default function ModDraftPane({ draft }: { draft: ModDraft }) {
  const save = useSaveMod();
  return (
    <div style={{ border: "1px solid #ccc", padding: 12, marginTop: 12 }}>
      <h3>{draft.name}</h3>
      <p>{draft.description}</p>
      <p>
        targets: <code>{draft.target_models.join(", ")}</code>
      </p>
      {Object.entries(draft.files).map(([f, c]) => (
        <details key={f}>
          <summary>{f}</summary>
          <pre style={{ background: "#f5f5f5", padding: 8 }}>{c}</pre>
        </details>
      ))}
      <p>
        <i>{draft.rationale}</i>
      </p>
      <button
        onClick={() =>
          save.mutate({
            name: draft.name,
            target_models: draft.target_models,
            description: draft.description,
            files: draft.files,
            enabled: true,
          })
        }
      >
        save mod
      </button>
    </div>
  );
}
