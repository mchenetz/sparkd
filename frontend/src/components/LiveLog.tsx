import { useEffect, useRef, useState } from "react";

import { openWS } from "../api/client";

export default function LiveLog({ launchId }: { launchId: string }) {
  const [lines, setLines] = useState<{ channel: string; line: string }[]>([]);
  const ref = useRef<HTMLPreElement>(null);
  useEffect(() => {
    const ws = openWS(`/ws/launches/${launchId}`);
    ws.onmessage = (ev) =>
      setLines((l) => [...l, JSON.parse(ev.data)].slice(-500));
    return () => ws.close();
  }, [launchId]);
  useEffect(() => {
    ref.current?.scrollTo(0, ref.current.scrollHeight);
  }, [lines]);
  return (
    <pre
      ref={ref}
      style={{ height: 240, overflow: "auto", background: "#111", color: "#eee", padding: 8 }}
    >
      {lines.map((l, i) => (
        <div key={i}>{l.line}</div>
      ))}
    </pre>
  );
}
