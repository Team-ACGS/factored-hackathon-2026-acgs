import { isLocale, resolveLocale, type Locale } from "./locale";

export interface LocaleStore {
  current: () => Locale;
  set: (locale: Locale) => void;
  subscribe: (listener: () => void) => () => void;
  signedOut: () => Locale;
  chooseSignedOut: (locale: Locale) => void;
}

interface Storage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const signedOutKey = "clara.locale";

export function createLocaleStore(storage: Storage, browserLanguages: readonly string[]): LocaleStore {
  const listeners = new Set<() => void>();

  function read(): string | null {
    try {
      return storage.getItem(signedOutKey);
    } catch {
      return null;
    }
  }

  function write(locale: Locale): boolean {
    try {
      storage.setItem(signedOutKey, locale);
      return true;
    } catch {
      return false;
    }
  }

  function signedOut(): Locale {
    const stored = read();
    return isLocale(stored) ? stored : resolveLocale(browserLanguages);
  }

  let current = signedOut();

  function set(locale: Locale) {
    if (locale === current) return;
    current = locale;
    for (const listener of listeners) listener();
  }

  return {
    current: () => current,
    set,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    signedOut,
    chooseSignedOut(locale) {
      write(locale);
      set(locale);
    },
  };
}
