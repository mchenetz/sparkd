import { Boxes, Settings as SettingsIcon, Sparkles } from "lucide-react";
import { useState } from "react";

import PageHeader from "../components/PageHeader";
import Tabs from "../components/Tabs";
import AISettings from "./settings/AISettings";
import HFSettings from "./settings/HFSettings";

export default function SettingsPage() {
  const [tab, setTab] = useState("ai");
  return (
    <>
      <PageHeader
        eyebrow={
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <SettingsIcon size={11} /> Settings
          </span>
        }
        title="Configuration"
        subtitle="Local-only sparkd preferences. Keys are stored in your OS keyring; non-secret state lives in ~/.sparkd."
      />
      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          {
            id: "ai",
            label: (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Sparkles size={13} style={{ color: "var(--accent-ai)" }} />
                AI
              </span>
            ),
          },
          {
            id: "hf",
            label: (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Boxes size={13} />
                Hugging Face
              </span>
            ),
          },
        ]}
      />
      {tab === "ai" && <AISettings />}
      {tab === "hf" && <HFSettings />}
    </>
  );
}
