import { describe, expect, it } from "vitest";

import { createLocaleStore } from "./store";

function memory(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => void values.set(key, value),
  };
}

describe("locale store", () => {
  it("starts from the browser language when nothing was chosen", () => {
    expect(createLocaleStore(memory(), ["pt-BR"]).current()).toBe("pt-BR");
  });

  it("remembers the language chosen on a signed-out screen", () => {
    const storage = memory();
    createLocaleStore(storage, ["en-US"]).chooseSignedOut("es");

    expect(createLocaleStore(storage, ["en-US"]).current()).toBe("es");
  });

  it("does not remember the signed-in language for signed-out screens", () => {
    const store = createLocaleStore(memory(), ["en-US"]);
    const heard: string[] = [];
    store.subscribe(() => heard.push(store.current()));

    store.set("pt-BR");

    expect(heard).toEqual(["pt-BR"]);
    expect(store.signedOut()).toBe("en");
  });

  it("falls back to the browser when storage is unavailable", () => {
    const broken = {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("denied");
      },
    };
    const store = createLocaleStore(broken, ["es-MX"]);
    store.chooseSignedOut("pt-BR");

    expect(store.current()).toBe("pt-BR");
    expect(store.signedOut()).toBe("es");
  });
});
