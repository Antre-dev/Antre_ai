import React, { useRef, useState } from "react";
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Platform,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { sendChat } from "@/lib/api";
import { getSettings, useSettings } from "@/lib/settings";
import { colors } from "@/theme";

interface Msg {
  id: number;
  role: "user" | "antre";
  text: string;
  images?: string[];
}

let nextId = 1;

export default function ChatScreen() {
  const { serverUrl } = useSettings();
  const [messages, setMessages] = useState<Msg[]>([
    {
      id: nextId++,
      role: "antre",
      text: "Hey — I'm the agent running on your laptop. Ask me anything.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<ScrollView>(null);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setError(null);
    setMessages((m) => [...m, { id: nextId++, role: "user", text }]);
    setBusy(true);
    try {
      const reply = await sendChat(text);
      const images = (reply.images ?? []).map((img) => resolveUrl(img, serverUrl));
      setMessages((m) => [...m, { id: nextId++, role: "antre", text: reply.response, images }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setMessages((m) => [
        ...m,
        { id: nextId++, role: "antre", text: `⚠️ ${e instanceof Error ? e.message : "Something failed."}` },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <Text style={styles.title}>CHAT</Text>
      <ScrollView
        ref={scrollRef}
        style={styles.list}
        contentContainerStyle={styles.listContent}
        onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
      >
        {messages.map((m) => (
          <View key={m.id} style={[styles.bubble, m.role === "user" ? styles.userBubble : styles.antreBubble]}>
            <Text style={m.role === "user" ? styles.userText : styles.antreText}>{m.text}</Text>
            {m.images?.map((src, i) => (
              <Image key={i} source={{ uri: src }} style={styles.image} resizeMode="contain" />
            ))}
          </View>
        ))}
        {busy && (
          <View style={styles.typing}>
            <ActivityIndicator size="small" color={colors.accent} />
            <Text style={styles.typingText}>Antre is working…</Text>
          </View>
        )}
        {error ? <Text style={styles.error}>{error}</Text> : null}
      </ScrollView>

      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder="Message Antre…"
            placeholderTextColor={colors.textDim}
            multiline
            editable={!busy}
            onSubmitEditing={send}
            returnKeyType="send"
          />
          <TouchableOpacity style={styles.sendBtn} onPress={send} disabled={busy || !input.trim()}>
            <Ionicons name="arrow-up" size={20} color={colors.bg} />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function resolveUrl(img: string, base: string): string {
  if (img.startsWith("http")) return img;
  return `${base}${img.startsWith("/") ? "" : "/"}${img}`;
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
  list: { flex: 1 },
  listContent: { padding: 16, gap: 10 },
  bubble: { borderRadius: 14, padding: 12, maxWidth: "85%" },
  userBubble: { alignSelf: "flex-end", backgroundColor: colors.accentDim },
  antreBubble: { alignSelf: "flex-start", backgroundColor: colors.card, borderWidth: 1, borderColor: colors.cardBorder },
  userText: { color: colors.text, fontSize: 15, lineHeight: 21 },
  antreText: { color: colors.text, fontSize: 15, lineHeight: 21 },
  image: { width: "100%", height: 180, borderRadius: 10, marginTop: 8, backgroundColor: colors.bg },
  typing: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 4 },
  typingText: { color: colors.textDim, fontSize: 13 },
  error: { color: colors.error, fontSize: 12, marginTop: 4 },
  inputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 10,
    padding: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.cardBorder,
    backgroundColor: colors.card,
  },
  input: {
    flex: 1,
    minHeight: 40,
    maxHeight: 120,
    borderRadius: 12,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    color: colors.text,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 15,
  },
  sendBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
});
