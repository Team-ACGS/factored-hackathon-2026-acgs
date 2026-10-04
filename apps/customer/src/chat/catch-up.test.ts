import { describe, expect, it, vi } from "vitest";

import { watchReturn, type Visibility } from "./catch-up";

class Page extends EventTarget implements Visibility {
  visibilityState: DocumentVisibilityState = "visible";

  turn(state: DocumentVisibilityState) {
    this.visibilityState = state;
    this.dispatchEvent(new Event("visibilitychange"));
  }
}

describe("catching up", () => {
  it("asks for what was missed when the page comes back to the foreground", () => {
    const page = new Page();
    const onReturn = vi.fn();
    watchReturn(page, new EventTarget(), onReturn);

    page.turn("visible");
    page.turn("hidden");
    page.turn("hidden");
    page.turn("visible");

    expect(onReturn).toHaveBeenCalledTimes(1);
  });

  it("asks again when the network comes back, and stops when the chat closes", () => {
    const page = new Page();
    const network = new EventTarget();
    const onReturn = vi.fn();
    const stop = watchReturn(page, network, onReturn);

    network.dispatchEvent(new Event("online"));
    stop();
    network.dispatchEvent(new Event("online"));
    page.turn("hidden");
    page.turn("visible");

    expect(onReturn).toHaveBeenCalledTimes(1);
  });
});
