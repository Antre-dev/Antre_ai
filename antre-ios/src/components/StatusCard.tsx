import React from "react";
import { ActivityIndicator, StyleSheet, Switch, Text, View } from "react-native";
import { Status } from "../lib/api";
import { formatUptime } from "../lib/format";
import { colors } from "../theme";

interface Props {
  status: Status | null;
  loading: boolean;
  error: string | null;
  latencyMs?: number;
  autoMode: boolean;
  onToggleAuto: (next: boolean) => void;
  toggling: boolean;
}

/** Connection + system status card for the Home tab. */
export default function StatusCard({
  status,
  loading,
  error,
  latencyMs,
  autoMode,
  onToggleAuto,
  toggling,
}: Props) {
  return (
    <View style={styles.card}>
      <View style={styles.topRow}>
        <View>
          <Text style={styles.antre}>ANTRE</Text>
          <Text style={styles.sub}>homelab agent · laptop</Text>
        </View>
        {status?.busy ? (
          <View style={styles.busyPill}>
            <ActivityIndicator size="small" color={colors.accent} />
            <Text style={styles.busyText}>WORKING</Text>
          </View>
        ) : (
          <View style={styles.idlePill}>
            <View style={styles.idleDot} />
            <Text style={styles.busyText}>IDLE</Text>
          </View>
        )}
      </View>

      <View style={styles.grid}>
        <Stat label="UPTIME" value={status ? formatUptime(status.uptime_seconds) : "—"} />
        <Stat label="MEMORY" value={status ? String(status.memory_count) : "—"} />
        <Stat label="SHOTS" value={status ? String(status.screenshot_count) : "—"} />
        <Stat label="LATENCY" value={latencyMs != null ? `${latencyMs}ms` : "—"} />
      </View>

      <View style={styles.autoRow}>
        <View style={{ flex: 1 }}>
          <Text style={styles.autoLabel}>Auto mode</Text>
          <Text style={styles.autoHint}>
            lets me run routine tools without asking
          </Text>
        </View>
        <Switch
          value={autoMode}
          disabled={!status || toggling}
          onValueChange={onToggleAuto}
          trackColor={{ false: colors.cardBorder, true: colors.accentDim }}
          thumbColor={autoMode ? colors.accent : "#5B6472"}
        />
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}
      {loading && !status ? <Text style={styles.hint}>connecting…</Text> : null}
    </View>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderColor: colors.cardBorder,
    borderWidth: 1,
    borderRadius: 16,
    padding: 16,
    marginHorizontal: 16,
    marginTop: 16,
  },
  topRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  antre: { color: colors.text, fontSize: 20, fontWeight: "800", letterSpacing: 4 },
  sub: { color: colors.textDim, fontSize: 12, marginTop: 2 },
  busyPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(34,211,238,0.1)",
    borderColor: colors.accentDim,
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  idlePill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(52,211,153,0.1)",
    borderColor: "#1F7A5A",
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  idleDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.ok },
  busyText: { color: colors.text, fontSize: 11, fontWeight: "700", letterSpacing: 1 },
  grid: {
    flexDirection: "row",
    marginTop: 16,
    backgroundColor: colors.bg,
    borderRadius: 12,
    paddingVertical: 12,
  },
  stat: { flex: 1, alignItems: "center" },
  statValue: { color: colors.text, fontSize: 16, fontWeight: "700", fontVariant: ["tabular-nums"] },
  statLabel: { color: colors.textDim, fontSize: 10, letterSpacing: 1, marginTop: 2 },
  autoRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 16,
    paddingTop: 14,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.cardBorder,
  },
  autoLabel: { color: colors.text, fontSize: 14, fontWeight: "600" },
  autoHint: { color: colors.textDim, fontSize: 12, marginTop: 2 },
  error: { color: colors.error, fontSize: 12, marginTop: 12 },
  hint: { color: colors.textDim, fontSize: 12, marginTop: 8 },
});
