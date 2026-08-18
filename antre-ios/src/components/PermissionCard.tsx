import React from "react";
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { PendingPermission } from "../lib/api";
import { timeAgo } from "../lib/format";
import { colors } from "../theme";

interface Props {
  request: PendingPermission;
  acting: boolean;
  onApprove: () => void;
  onDeny: () => void;
}

const LEVEL_COLORS: Record<number, string> = {
  1: colors.ok,
  2: colors.accent,
  3: colors.warn,
  4: "#FB923C",
  5: colors.error,
};

/** A single pending approval request, with Face ID / deny actions. */
export default function PermissionCard({ request, acting, onApprove, onDeny }: Props) {
  const lvl = Math.max(1, Math.min(5, request.danger_level ?? 3));
  const color = LEVEL_COLORS[lvl] ?? colors.warn;

  return (
    <View style={styles.card}>
      <View style={styles.topRow}>
        <View style={[styles.levelTag, { borderColor: color }]}>
          <Text style={[styles.levelText, { color }]}>LEVEL {lvl}</Text>
        </View>
        <Text style={styles.time}>{timeAgo(request.created_at)}</Text>
      </View>

      <Text style={styles.tool}>{request.tool}</Text>
      <Text style={styles.summary}>{request.summary}</Text>

      <View style={styles.actions}>
        <TouchableOpacity
          style={[styles.btn, styles.denyBtn]}
          onPress={onDeny}
          disabled={acting}
        >
          {acting ? (
            <ActivityIndicator size="small" color={colors.error} />
          ) : (
            <Text style={[styles.btnText, { color: colors.error }]}>DENY</Text>
          )}
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.btn, styles.approveBtn]}
          onPress={onApprove}
          disabled={acting}
        >
          {acting ? (
            <ActivityIndicator size="small" color={colors.bg} />
          ) : (
            <>
              <Ionicons name="scan-outline" size={14} color={colors.bg} />
              <Text style={[styles.btnText, { color: colors.bg }]}>APPROVE</Text>
            </>
          )}
        </TouchableOpacity>
      </View>
      <Text style={styles.faceIdHint}>Approve unlocks with Face ID</Text>
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
    marginTop: 12,
  },
  topRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  levelTag: { borderWidth: 1, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  levelText: { fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  time: { color: colors.textDim, fontSize: 11 },
  tool: { color: colors.accent, fontSize: 14, fontWeight: "700", marginTop: 10, textTransform: "uppercase" },
  summary: { color: colors.text, fontSize: 14, marginTop: 4, lineHeight: 20, fontFamily: "Menlo" },
  actions: { flexDirection: "row", gap: 10, marginTop: 14 },
  btn: {
    flex: 1,
    height: 44,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 6,
  },
  denyBtn: { backgroundColor: "rgba(248,113,113,0.08)", borderWidth: 1, borderColor: "rgba(248,113,113,0.35)" },
  approveBtn: { backgroundColor: colors.accent },
  btnText: { fontSize: 13, fontWeight: "800", letterSpacing: 1 },
  faceIdHint: { color: colors.textDim, fontSize: 11, marginTop: 8, textAlign: "center" },
});
