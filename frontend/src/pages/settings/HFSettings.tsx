import { Check, ExternalLink, KeyRound, Trash2 } from "lucide-react";
import { useState } from "react";

import { Card, Pill } from "../../components/Card";
import {
  useClearHFToken,
  useHFTokenStatus,
  useSaveHFToken,
} from "../../hooks/useHFToken";

export default function HFSettings() {
  const status = useHFTokenStatus();
  const save = useSaveHFToken();
  const clear = useClearHFToken();
  const [token, setToken] = useState("");

  const configured = status.data?.configured ?? false;

  return (
    <div style={{ display: "grid", gap: 16, maxWidth: 720 }}>
      <Card>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
          <KeyRound size={16} style={{ color: "var(--accent-ai)" }} />
          <h3 style={{ margin: 0 }}>Hugging Face access token</h3>
          {configured && <Pill tone="healthy">saved</Pill>}
        </div>
        <p
          style={{
            color: "var(--fg-secondary)",
            fontSize: 13,
            marginBottom: 12,
            maxWidth: 600,
          }}
        >
          Optional. Without a token sparkd talks to the public Hub API anonymously
          (subject to rate limits). With a token, gated and private repos are
          accessible and rate limits relax. The token is stored in your OS
          keyring — never written to a file or sent anywhere except
          huggingface.co.
        </p>

        <div style={{ display: "grid", gap: 10 }}>
          <input
            type="password"
            className="mono"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder={configured ? "•••••••• (saved)" : "hf_xxxxxxxxxxxxxxxxxxxxx"}
          />
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button
              className="primary"
              disabled={!token || save.isPending}
              onClick={async () => {
                await save.mutateAsync(token);
                setToken("");
              }}
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Check size={13} /> save token
              </span>
            </button>
            {configured && (
              <button
                className="danger"
                disabled={clear.isPending}
                onClick={() => clear.mutate()}
              >
                <span
                  style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                >
                  <Trash2 size={13} /> remove
                </span>
              </button>
            )}
            <span style={{ flex: 1 }} />
            <a
              href="https://huggingface.co/settings/tokens"
              target="_blank"
              rel="noreferrer"
              style={{ borderBottom: "none" }}
            >
              <button className="ghost">
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <ExternalLink size={13} /> create one
                </span>
              </button>
            </a>
          </div>
          {save.isSuccess && (
            <span style={{ fontSize: 12, color: "var(--signal-healthy)" }}>
              saved to OS keyring.
            </span>
          )}
          {save.error ? (
            <span
              style={{
                fontSize: 12,
                color: "var(--signal-danger)",
                fontFamily: "var(--font-mono)",
              }}
            >
              {save.error instanceof Error
                ? save.error.message
                : String(save.error)}
            </span>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
