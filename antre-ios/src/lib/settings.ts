// Tiny persisted-settings store. Values live in expo-secure-store so the
// server URL survives app restarts. React components subscribe via the hook.

import React from "react";
import * as SecureStore from "expo-secure-store";

export interface AppSettings {
  /** Base URL of the Antre web app, e.g. https://antre-laptop.tailXXXX.ts.net */
  serverUrl: string;
  /** Allow passcode fallback when Face ID is unavailable. */
  allowPasscodeFallback: boolean;
}

const DEFAULTS: AppSettings = {
  serverUrl: "",
  allowPasscodeFallback: false,
};

const KEYS = {
  serverUrl: "antre.serverUrl",
  allowPasscodeFallback: "antre.allowPasscodeFallback",
};

let cached: AppSettings | null = null;
const listeners = new Set<() => void>();

function notify() {
  for (const l of listeners) l();
}

function normalize(raw: Partial<AppSettings>): AppSettings {
  return {
    serverUrl: (raw.serverUrl ?? DEFAULTS.serverUrl).trim().replace(/\/+$/, ""),
    allowPasscodeFallback: raw.allowPasscodeFallback ?? DEFAULTS.allowPasscodeFallback,
  };
}

export async function loadSettings(): Promise<AppSettings> {
  try {
    const url = (await SecureStore.getItemAsync(KEYS.serverUrl)) ?? "";
    const pass = (await SecureStore.getItemAsync(KEYS.allowPasscodeFallback)) === "1";
    cached = normalize({ serverUrl: url, allowPasscodeFallback: pass });
  } catch {
    cached = normalize({});
  }
  return cached!;
}

export async function getSettings(): Promise<AppSettings> {
  if (!cached) await loadSettings();
  return cached!;
}

export function getSettingsSync(): AppSettings {
  return cached ?? DEFAULTS;
}

export async function saveSettings(patch: Partial<AppSettings>): Promise<AppSettings> {
  const next = normalize({ ...(await getSettings()), ...patch });
  await SecureStore.setItemAsync(KEYS.serverUrl, next.serverUrl);
  await SecureStore.setItemAsync(
    KEYS.allowPasscodeFallback,
    next.allowPasscodeFallback ? "1" : "0",
  );
  cached = next;
  notify();
  return next;
}

/** React hook — re-renders whenever settings change. */
export function useSettings(): AppSettings {
  return React.useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    getSettingsSync,
  );
}
