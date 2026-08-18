import React, { useCallback, useEffect, useRef, useState } from "react";
import { SafeAreaView, StyleSheet, Text } from "react-native";
import StatusCard from "@/components/StatusCard";
import ActivityFeed from "@/components/ActivityFeed";
import { ActivityEvent, getHistory, getStatus, ping, setMode, Status } from "@/lib/api";
import { useActivity } from "@/lib/activity";
import { useSettings } from "@/lib/settings";
import { colors } from "@/theme";

const MAX_EVENTS = 100;

export default function HomeScreen() {
  const { serverUrl } = useSettings();
  const [status, setStatus] = useState<Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [latency, setLatency] = useState<number | undefined>();
  const [autoMode, setAutoMode] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [events, setEvents] = useState<ActivityEvent[]>([]);

  const refreshStatus = useCallback(async () => {
    try {
      const { status: s, latencyMs } = await ping();
      setStatus(s);
      setLatency(latencyMs);
      setAutoMode(s.auto);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // Poll status every 8s + on mount.
  useEffect(() => {
    if (!serverUrl) {
      setError("No server URL — open Settings and enter it.");
      setLoading(false);
      return;
    }
    refreshStatus();
    const t = setInterval(refreshStatus, 8000);
    return () => clearInterval(t);
  }, [serverUrl, refreshStatus]);

  // Live activity stream — appends events, capped.
  const { connected } = useActivity(
    useCallback((e: ActivityEvent) => {
      setEvents((prev) => [e, ...prev].slice(0, MAX_EVENTS));
    }, []),
  );

  // Seed with recent history on first load.
  useEffect(() => {
    if (!serverUrl) return;
    getHistory(MAX_EVENTS)
      .then(({ events: h }) => setEvents(h.reverse()))
      .catch(() => {});
  }, [serverUrl]);

  const toggleAuto = useCallback(async (next: boolean) => {
    setToggling(true);
    try {
      const r = await setMode(next);
      setAutoMode(r.auto);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setToggling(false);
    }
  }, []);

  return (
    <SafeAreaView style={styles.safe}>
      <Text style={styles.title}>REMOTE MONITOR</Text>
      <StatusCard
        status={status}
        loading={loading}
        error={error}
        latencyMs={latency}
        autoMode={autoMode}
        onToggleAuto={toggleAuto}
        toggling={toggling}
      />
      <ActivityFeed events={events} connected={connected} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  title: {
    color: colors.textDim,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 3,
    paddingHorizontal: 18,
    paddingTop: 12,
  },
});
