import { Settings as SettingsIcon } from "lucide-react";
import { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useAdvisorStatus } from "../hooks/useAdvisor";
import { Card } from "./Card";

export default function SetupGate({ children }: { children: ReactNode }) {
  const status = useAdvisorStatus();
  if (status.isLoading) return <Card>connecting…</Card>;
  if (status.data?.configured) return <>{children}</>;
  return (
    <Card ai>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
        <SettingsIcon size={16} style={{ color: "var(--accent-ai)" }} />
        <h3>AI provider not configured</h3>
      </div>
      <p
        style={{
          color: "var(--fg-secondary)",
          fontSize: 13,
          marginBottom: 14,
          maxWidth: 560,
        }}
      >
        Pick a provider (Claude, OpenAI, Gemini, Mistral, local vLLM, …) and a
        model on the Settings page. Keys are stored in your OS keyring.
      </p>
      <Link to="/settings" style={{ borderBottom: "none" }}>
        <button className="ai">open Settings · AI</button>
      </Link>
    </Card>
  );
}
