import { useSyncExternalStore } from "react";

import { createClaraSession, memoryStorage, type SessionStorage } from "./session";

function browserStorage(): SessionStorage {
  try {
    return window.sessionStorage;
  } catch {
    return memoryStorage();
  }
}

export const claraSession = createClaraSession(browserStorage());

export function useClaraSession() {
  return useSyncExternalStore(claraSession.subscribe, claraSession.current);
}

const launcherListeners = new Set<() => void>();
let launcherOpen = false;

function setLauncher(open: boolean) {
  launcherOpen = open;
  for (const listener of launcherListeners) listener();
}

export const launcher = {
  open: () => setLauncher(true),
  close: () => setLauncher(false),
  isOpen: () => launcherOpen,
  subscribe: (listener: () => void) => {
    launcherListeners.add(listener);
    return () => launcherListeners.delete(listener);
  },
};

export function useLauncherOpen() {
  return useSyncExternalStore(launcher.subscribe, launcher.isOpen);
}
