import React from "react";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "@/theme";

const ICONS: Record<string, [keyof typeof Ionicons.glyphMap, keyof typeof Ionicons.glyphMap]> = {
  index: ["pulse-outline", "pulse"],
  chat: ["chatbubble-ellipses-outline", "chatbubble-ellipses"],
  permissions: ["shield-checkmark-outline", "shield-checkmark"],
  settings: ["settings-outline", "settings"],
};

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.card,
          borderTopColor: colors.cardBorder,
        },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textDim,
      }}
    >
      {(Object.keys(ICONS) as Array<keyof typeof ICONS>).map((name) => {
        const [active, inactive] = ICONS[name]!;
        return (
          <Tabs.Screen
            key={name}
            name={name}
            options={{
              title: name === "index" ? "Home" : name.charAt(0).toUpperCase() + name.slice(1),
              tabBarIcon: ({ focused, color, size }) => (
                <Ionicons name={focused ? active : inactive} size={size} color={color} />
              ),
            }}
          />
        );
      })}
    </Tabs>
  );
}
