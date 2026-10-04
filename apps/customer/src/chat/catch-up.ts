export const FIRST_RETRY_MS = 1_000;
export const MAX_RETRY_MS = 30_000;

export function retryDelay(failures: number): number {
  return Math.min(MAX_RETRY_MS, FIRST_RETRY_MS * 2 ** failures);
}

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
