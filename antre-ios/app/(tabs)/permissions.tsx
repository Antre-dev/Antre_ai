import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  AppState,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
} from "react-native";
import * as LocalAuthentication from "expo-local-authentication";
import PermissionCard from "@/components/PermissionCard";
import {
  approvePermission,
  denyPermission,
  getPendingPermissions,
  PendingPermission,
} from "@/lib/api";
import { getSettings, useSettings } from "@/lib/settings";
import { colors } from "@/theme";

const POLL_MS = 5000;

export default function PermissionsScreen() {
  const { serverUrl } = useSettings();
  const [requests, setRequests] = useState<PendingPermission[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [actingId, setActingId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    if (!serverUrl) {
      setError("No server URL — open Settings.");
      return;
    }
    try {
      const { requests: r } = await getPendingPermissions();
      setRequests(r);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [serverUrl]);

  // Poll while mounted, and refresh when the app comes back to foreground.
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, POLL_MS);
    const sub = AppState.addEventListener("change", (s) => {
      if (s === "active") refresh();
    });
    return () => {
      clearInterval(t);
      sub.remove();
    };
  }, [refresh]);

  const faceIdAuth = useCallback(async (): Promise<boolean> => {
    const settings = await getSettings();
    const hasHardware = await LocalAuthentication.hasHardwareAsync();
    if (!hasHardware) {
      Alert.alert("No biometrics", "This device has no Face ID hardware.");
      return false;
    }
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    if (!enrolled) {
      Alert.alert("Face ID not set up", "Enroll Face ID in Settings, then try again.");
      return false;
    }
    const res = await LocalAuthentication.authenticateAsync({
      promptMessage: "Approve this action on your laptop",
      cancelLabel: "Deny",
      disableDeviceFallback: !settings.allowPasscodeFallback,
    });
    return res.success;
  }, []);

  const act = useCallback(
    async (id: string, decision: "approve" | "deny") => {
      if (actingId) return;
      if (decision === "approve") {
        const ok = await faceIdAuth();
        if (!ok) return; // user cancelled or failed — leave it pending
      }
      setActingId(id);
      try {
        if (decision === "approve") await approvePermission(id);
        else await denyPermission(id);
        setRequests((prev) => prev.filter((r) => r.id !== id));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setActingId(null);
      }
    },
    [actingId, faceIdAuth],
  );

  return (
    <SafeAreaView style={styles.safe}>
      <Text style={styles.title}>PERMISSIONS</Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <ScrollView
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={async () => {
              setRefreshing(true);
              await refresh();
              setRefreshing(false);
            }}
            tintColor={colors.accent}
          />
        }
      >
        {requests.length === 0 ? (
          <Text style={styles.empty}>
            No pending requests.{"\n"}
            Anything sensitive on the laptop shows up here for Face ID approval.
          </Text>
        ) : (
          requests.map((r) => (
            <PermissionCard
              key={r.id}
              request={r}
              acting={actingId === r.id}
              onApprove={() => act(r.id, "approve")}
              onDeny={() => act(r.id, "deny")}
            />
          ))
        )}
      </ScrollView>
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
    paddingBottom: 4,
  },
  error: { color: colors.error, fontSize: 12, paddingHorizontal: 16, paddingTop: 8 },
  empty: {
    color: colors.textDim,
    fontSize: 14,
    textAlign: "center",
    lineHeight: 22,
    marginTop: 80,
    paddingHorizontal: 40,
  },
});
