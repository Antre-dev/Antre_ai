// Small formatting + display helpers shared across screens.

export function formatUptime(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export function timeAgo(iso?: string): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Math.max(0, Date.now() - then);
  const s = Math.floor(diff / 1000);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function formatDurationMs(ms?: number): string {
  if (ms == null) return "";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

/** Icon name (Ionicons) + color for an activity category. */
export function categoryStyle(category?: string): { icon: string; color: string } {
  switch (category) {
    case "terminal":
      return { icon: "terminal-outline", color: "#34D399" };
    case "browser":
      return { icon: "globe-outline", color: "#22D3EE" };
    case "search":
      return { icon: "search-outline", color: "#A78BFA" };
    case "memory":
      return { icon: "book-outline", color: "#FBBF24" };
    case "files":
      return { icon: "document-text-outline", color: "#F87171" };
    case "system":
      return { icon: "time-outline", color: "#8B98A9" };
    default:
      return { icon: "pulse-outline", color: "#8B98A9" };
  }
}

/** One-line summary of an event, e.g. the SSH command or browser URL. */
export function eventSummary(e: { type: string; tool?: string; command?: string; url?: string; action?: string; args?: string; text?: string }): string {
  if (e.command) return e.command;
  if (e.url) return e.action === "goto" ? e.url : `${e.action ?? "browse"} → ${e.url}`;
  if (e.text) return e.text;
  if (e.type === "tool.start" || e.type === "tool.done") {
    const args = e.args ?? "";
    try {
      const parsed = JSON.parse(args) as Record<string, unknown>;
      const first = Object.values(parsed)[0];
      return typeof first === "string" ? first : args.slice(0, 120);
    } catch {
      return args.slice(0, 120);
    }
  }
  return "";
}
