import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { ActivityEvent } from "../lib/api";
import { categoryStyle, eventSummary, formatDurationMs, timeAgo } from "../lib/format";
import { colors } from "../theme";

/**
 * Live feed of what Antre is doing. Newest at the top.
 * `events` is the parent's state — this component just renders it.
 */
export default function ActivityFeed({ events, connected }: { events: ActivityEvent[]; connected: boolean }) {
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>LIVE ACTIVITY</Text>
        <View style={styles.liveRow}>
          <View style={[styles.dot, connected ? styles.dotOn : styles.dotOff]} />
          <Text style={styles.liveText}>{connected ? "LIVE" : "OFFLINE"}</Text>
        </View>
      </View>

      {events.length === 0 ? (
        <View style={styles.empty}>
          <Ionicons name="pulse-outline" size={28} color={colors.textDim} />
          <Text style={styles.emptyText}>
            {connected ? "Waiting for activity…" : "Connect to see the live feed."}
          </Text>
        </View>
      ) : (
        <ScrollView style={styles.list}>
          {events.map((e, i) => (
            <ActivityRow key={e.id ?? `${e.type}-${i}`} event={e} />
          ))}
        </ScrollView>
      )}
    </View>
  );
}

function ActivityRow({ event }: { event: ActivityEvent }) {
  const { icon, color } = categoryStyle(event.category);
  const summary = eventSummary(event);
  const isDone = event.type === "tool.done";
  const isStart = event.type === "tool.start";
  const isError = event.status === "error";

  return (
    <View style={styles.row}>
      <View style={[styles.iconWrap, { borderColor: color }]}>
        <Ionicons name={icon as any} size={15} color={color} />
      </View>
      <View style={styles.rowBody}>
        <View style={styles.rowTop}>
          <Text style={[styles.tool, { color }]}>
            {event.tool ?? event.type.toUpperCase()}
          </Text>
          <Text style={styles.meta}>
            {timeAgo(event.ts)}
            {isDone && formatDurationMs(event.duration_ms) ? ` · ${formatDurationMs(event.duration_ms)}` : ""}
          </Text>
        </View>
        {summary ? <Text style={styles.summary} numberOfLines={2}>{summary}</Text> : null}
        {isStart ? <Text style={styles.running}>running…</Text> : null}
        {isError ? <Text style={styles.errorText}>failed</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
  },
  title: { color: colors.textDim, fontSize: 12, fontWeight: "700", letterSpacing: 2 },
  liveRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  dotOn: { backgroundColor: colors.ok },
  dotOff: { backgroundColor: colors.error },
  liveText: { color: colors.textDim, fontSize: 11, fontWeight: "600", letterSpacing: 1 },
  list: { flex: 1 },
  row: {
    flexDirection: "row",
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.cardBorder,
  },
  iconWrap: {
    width: 28,
    height: 28,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
  },
  rowBody: { flex: 1 },
  rowTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  tool: { fontSize: 12, fontWeight: "700", letterSpacing: 0.5, textTransform: "uppercase" },
  meta: { color: colors.textDim, fontSize: 11 },
  summary: {
    color: colors.text,
    fontSize: 13,
    marginTop: 2,
    fontFamily: "Menlo",
  },
  running: { color: colors.accent, fontSize: 11, marginTop: 2 },
  errorText: { color: colors.error, fontSize: 11, marginTop: 2, fontWeight: "600" },
  empty: { alignItems: "center", paddingTop: 48, gap: 8 },
  emptyText: { color: colors.textDim, fontSize: 13 },
});
