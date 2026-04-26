import { KeyRound } from "lucide-react";
import { ReactNode, useState } from "react";

import { useAdvisorSetup, useAdvisorStatus } from "../hooks/useAdvisor";
import { Card } from "./Card";

export default function SetupGate({ children }: { children: ReactNode }) {
  const status = useAdvisorStatus();
  const setup = useAdvisorSetup();
  const [key, setKey] = useState("");
  if (status.isLoading) return <Card>connecting…</Card>;
  if (status.data?.configured) return <>{children}</>;
  return (
    <Card ai>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
        <KeyRound size={16} style={{ color: "var(--accent-ai)" }} />
        <h3>Connect to Anthropic</h3>
      </div>
      <p
        style={{
          color: "var(--fg-secondary)",
          fontSize: 13,
          marginBottom: 14,
          maxWidth: 560,
        }}
      >
        sparkd uses Claude to translate models and box capabilities into vLLM recipes
        and mods. Your key is stored in the OS keyring (Keychain / Secret Service /
        Credential Manager) — never in this repo or its database.
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input
          type="password"
          className="mono"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="sk-ant-..."
          style={{ flex: 1, maxWidth: 480 }}
        />
        <button
          className="ai"
          disabled={!key || setup.isPending}
          onClick={() => setup.mutate({ anthropic_api_key: key })}
        >
          save key
        </button>
      </div>
    </Card>
  );
}
