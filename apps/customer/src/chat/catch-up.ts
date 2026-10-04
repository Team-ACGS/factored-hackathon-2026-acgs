export interface Visibility extends EventTarget {
  readonly visibilityState: DocumentVisibilityState;
}

export function watchReturn(page: Visibility, network: EventTarget, onReturn: () => void): () => void {
  let away = page.visibilityState === "hidden";
  const visibility = () => {
    if (page.visibilityState === "hidden") {
      away = true;
      return;
    }
    if (away) {
      away = false;
      onReturn();
    }
  };
  page.addEventListener("visibilitychange", visibility);
  network.addEventListener("online", onReturn);
  return () => {
    page.removeEventListener("visibilitychange", visibility);
    network.removeEventListener("online", onReturn);
  };
}
