import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { ping } from "@/lib/api";
import { loadSettings, saveSettings, useSettings } from "@/lib/settings";
import { colors } from "@/theme";

export default function SettingsScreen() {
  const settings = useSettings();
  const [url, setUrl] = useState(settings.serverUrl);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testOk, setTestOk] = useState(false);

  useEffect(() => {
    loadSettings().then(() => setUrl(settings.serverUrl));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    setSaving(true);
    await saveSettings({ serverUrl: url.trim() });
    setSaving(false);
    Alert.alert("Saved", "Server URL updated.");
  };

  const test = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const { latencyMs, status } = await ping();
      setTestOk(true);
      setTestResult(
        `Connected in ${latencyMs}ms — Antre is ${status.busy ? "busy" : "idle"}, ${status.active_tools} active tool(s).`,
      );
    } catch (e) {
      setTestOk(false);
      setTestResult(e instanceof Error ? e.message : String(e));
    } finally {
      setTesting(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <Text style={styles.title}>SETTINGS</Text>
      <ScrollView contentContainerStyle={styles.content}>
        <Section label="CONNECTION">
          <Text style={styles.hint}>
            Your laptop's Tailscale name or LAN IP, with the port — e.g.{" "}
            {"https://antre-laptop.tailXXXX.ts.net"}
          </Text>
          <TextInput
            style={styles.input}
            value={url}
            onChangeText={setUrl}
            placeholder="https://…"
            placeholderTextColor={colors.textDim}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
          />
          <View style={styles.btnRow}>
            <TouchableOpacity style={[styles.btn, styles.btnPrimary]} onPress={save} disabled={saving}>
              {saving ? (
                <ActivityIndicator size="small" color={colors.bg} />
              ) : (
                <Text style={[styles.btnText, { color: colors.bg }]}>SAVE</Text>
              )}
            </TouchableOpacity>
            <TouchableOpacity style={[styles.btn, styles.btnGhost]} onPress={test} disabled={testing || !url}>
              {testing ? (
                <ActivityIndicator size="small" color={colors.accent} />
              ) : (
                <Text style={[styles.btnText, { color: colors.accent }]}>TEST</Text>
              )}
            </TouchableOpacity>
          </View>
          {testResult ? (
            <Text style={[styles.testResult, { color: testOk ? colors.ok : colors.error }]}>
              {testResult}
            </Text>
          ) : null}
        </Section>

        <Section label="SECURITY">
          <View style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowLabel}>Passcode fallback</Text>
              <Text style={styles.rowHint}>Allow iPhone passcode when Face ID fails</Text>
            </View>
            <Switch
              value={settings.allowPasscodeFallback}
              onValueChange={(v) => { void saveSettings({ allowPasscodeFallback: v }); }}
              trackColor={{ false: colors.cardBorder, true: colors.accentDim }}
              thumbColor={settings.allowPasscodeFallback ? colors.accent : "#5B6472"}
            />
          </View>
          <Text style={styles.rowHint}>
            Approving a sensitive action always prompts for Face ID first.
          </Text>
        </Section>

        <Section label="ABOUT">
          <InfoRow label="App" value="Antre Remote v0.1.0" />
          <InfoRow label="Agent" value="Antre demo 0.1" />
          <InfoRow label="Build" value="Expo SDK 57 · sideload via SideStore" />
          <Text style={styles.rowHint}>
            Your laptop runs the Antre web app; this phone connects over Tailscale.
          </Text>
        </Section>
      </ScrollView>
    </SafeAreaView>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionLabel}>{label}</Text>
      <View style={styles.card}>{children}</View>
    </View>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
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
  content: { padding: 16, paddingBottom: 40, gap: 20 },
  section: { gap: 8 },
  sectionLabel: { color: colors.textDim, fontSize: 11, fontWeight: "700", letterSpacing: 2 },
  card: {
    backgroundColor: colors.card,
    borderColor: colors.cardBorder,
    borderWidth: 1,
    borderRadius: 14,
    padding: 14,
    gap: 12,
  },
  hint: { color: colors.textDim, fontSize: 12, lineHeight: 18 },
  input: {
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderRadius: 10,
    color: colors.text,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
  btnRow: { flexDirection: "row", gap: 10 },
  btn: { flex: 1, height: 42, borderRadius: 10, alignItems: "center", justifyContent: "center" },
  btnPrimary: { backgroundColor: colors.accent },
  btnGhost: { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.accentDim },
  btnText: { fontSize: 13, fontWeight: "800", letterSpacing: 1 },
  testResult: { fontSize: 12, lineHeight: 18 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 10 },
  rowLabel: { color: colors.text, fontSize: 14, fontWeight: "600" },
  rowHint: { color: colors.textDim, fontSize: 12, lineHeight: 17, marginTop: 2 },
  rowValue: { color: colors.textDim, fontSize: 13 },
});
