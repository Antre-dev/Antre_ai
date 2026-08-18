// Live activity feed over SSE (server-sent events).
// Wraps react-native-sse with auto-reconnect + backoff, and exposes the
// connection state so the Home screen can show "live" vs "reconnecting".

import { useEffect, useRef, useState } from "react";
import EventSource from "react-native-sse";
import { ActivityEvent } from "./api";
import { getSettings } from "./settings";

export interface ActivityState {
  connected: boolean;
  lastEvent: ActivityEvent | null;
  /** error text, or null when healthy */
  error: string | null;
}

/** Subscribe to the live feed. `onEvent` fires for every parsed event. */
export function useActivity(onEvent: (e: ActivityEvent) => void): ActivityState {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastRef = useRef<ActivityEvent | null>(null);
  const cbRef = useRef(onEvent);
  cbRef.current = onEvent;

  useEffect(() => {
    let es: EventSource | null = null;
    let closed = false;
    let retry = 1000;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const connect = async () => {
      const { serverUrl } = await getSettings();
      if (!serverUrl) {
        setError("No server URL configured.");
        setConnected(false);
        timer = setTimeout(connect, 3000);
        return;
      }
      try {
        es = new EventSource(`${serverUrl}/activity/stream`, {
          pollingInterval: 0, // real SSE, not polling
          timeoutBeforeConnection: 8000,
        });
        es.addEventListener("message", (event) => {
          try {
            const data = JSON.parse((event as any).data ?? "{}") as ActivityEvent;
            lastRef.current = data;
            cbRef.current(data);
          } catch {
            /* malformed event — ignore */
          }
        });
        es.addEventListener("open", () => {
          setConnected(true);
          setError(null);
          retry = 1000;
        });
        es.addEventListener("error", () => {
          setConnected(false);
        });
        es.addEventListener("close", () => {
          setConnected(false);
          if (!closed) {
            setError("Disconnected — reconnecting…");
            timer = setTimeout(connect, retry);
            retry = Math.min(retry * 2, 15000);
          }
        });
      } catch {
        setConnected(false);
        setError("Connection failed — retrying…");
        timer = setTimeout(connect, retry);
        retry = Math.min(retry * 2, 15000);
      }
    };

    connect();

    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      es?.removeAllEventListeners();
      es?.close();
    };
  }, []);

  return { connected, lastEvent: lastRef.current, error };
}
